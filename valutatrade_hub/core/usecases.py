import hashlib
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any, List
from pathlib import Path

from valutatrade_hub.decorators import log_action, retry_on_failure
from valutatrade_hub.core.models import User, Portfolio, Wallet
from valutatrade_hub.core.currencies import CurrencyRegistry, Currency, FiatCurrency, CryptoCurrency
from valutatrade_hub.core.exceptions import (
    InsufficientFundsError,
    CurrencyNotFoundError,
    ApiRequestError,
    AuthenticationError,
    PortfolioNotFoundError,
    ValidationError,
    RateUnavailableError
)
from valutatrade_hub.core.utils import (
    validate_currency,
    validate_amount,
    get_exchange_rate
)
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.infra.database import DatabaseManager


class SessionManager:

    _current_user: Optional[User] = None
    
    @classmethod
    def get_current_user(cls) -> Optional[User]:
        return cls._current_user
    
    @classmethod
    def set_current_user(cls, user: Optional[User]) -> None:
        cls._current_user = user
    
    @classmethod
    def is_logged_in(cls) -> bool:
        return cls._current_user is not None

    @classmethod
    def require_login(cls) -> None:
        if not cls.is_logged_in():
            raise AuthenticationError("Сначала выполните команду login")

class UserManager:
    
    _db = DatabaseManager()
    _settings = SettingsLoader()

    @staticmethod
    def get_next_user_id() -> int:
        users = UserManager._db.read_collection("users")
        if not users:
            return 1
        return max(user["user_id"] for user in users) + 1
    
    @staticmethod
    def find_user_by_username(username: str) -> Optional[dict]:
        return UserManager._db.find_one("users", {"username": username})
    
    @staticmethod
    @log_action("REGISTER", verbose=True)
    def register(username: str, password: str) -> Tuple[bool, str]:
        if len(password) < 4:
            raise ValidationError("password", "Пароль должен быть не короче 4 символов")
        
        if UserManager.find_user_by_username(username):
            raise ValidationError("username", f"Имя пользователя '{username}' уже занято")
        
        user_id = UserManager.get_next_user_id()
        
        salt = hashlib.sha256(f"{username}{time.time()}".encode()).hexdigest()[:8]
        hashed_password = hashlib.sha256(f"{password}{salt}".encode()).hexdigest()
        
        user_data = {
            "user_id": user_id,
            "username": username,
            "hashed_password": hashed_password,
            "salt": salt,
            "registration_date": datetime.now().isoformat()
        }
        
        success = UserManager._db.insert_one("users", user_data)
        
        if success:
            PortfolioManager.create_portfolio(user_id)
            return True, f"Пользователь '{username}' зарегистрирован (id={user_id}). Войдите: login --username {username} --password ****"
        
        return False, "Ошибка при сохранении пользователя"
    
    @staticmethod
    @log_action("LOGIN", verbose=True)
    def login(username: str, password: str) -> Tuple[bool, str, Optional[User]]:
        user_data = UserManager.find_user_by_username(username)
        if not user_data:
            raise AuthenticationError(f"Пользователь '{username}' не найден")
        
        hashed_input = hashlib.sha256(
            f"{password}{user_data['salt']}".encode()
        ).hexdigest()
        
        if hashed_input != user_data["hashed_password"]:
            raise AuthenticationError("Неверный пароль")
        
        user = User.from_dict(user_data)
        return True, f"Вы вошли как '{username}'", user


class PortfolioManager:
    
    _db = DatabaseManager()
    _settings = SettingsLoader()

    @staticmethod
    def create_portfolio(user_id: int) -> bool:
        portfolio_data = {
            "user_id": user_id,
            "wallets": {}
        }
        
        portfolios = load_json("data/portfolios.json")
        portfolios.append(portfolio_data)
        
        return PortfolioManager._db.insert_one("portfolios", portfolio_data)
    
    @staticmethod
    def find_portfolio(user_id: int) -> Optional[dict]:
        return PortfolioManager._db.find_one("portfolios", {"user_id": user_id})
    
    @staticmethod
    def get_user_portfolio(user_id: int) -> Optional[Portfolio]:
        portfolio_data = PortfolioManager.find_portfolio(user_id)
        if not portfolio_data:
            raise PortfolioNotFoundError(user_id)
        
        return Portfolio.from_dict(portfolio_data)
    
    @staticmethod
    def save_portfolio(portfolio: Portfolio) -> bool:
        return PortfolioManager._db.update_one(
            "portfolios",
            {"user_id": portfolio.user_id},
            portfolio.to_dict()
        )

    @staticmethod
    @log_action("SHOW_PORTFOLIO", verbose=False)
    def show_portfolio(user_id: int, base_currency: str = "USD") -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        try:
            CurrencyRegistry.get_currency(base_currency)
        except CurrencyNotFoundError:
            raise CurrencyNotFoundError(base_currency)
        
        portfolio = PortfolioManager.get_user_portfolio(user_id)

        wallets = portfolio.wallets
        
        if not wallets:
            return True, "Портфель пуст", {"total_value": 0.0, "wallets": []}
        
        wallet_info = []
        total_value = 0.0
        
        for currency_code, wallet in wallets.items():
            if wallet.balance > 0:
                try:
                    currency = CurrencyRegistry.get_currency(currency_code)
                    display_name = currency.name
                    
                    rate = get_exchange_rate(currency_code, base_currency)
                    
                    if rate is not None:
                        value_in_base = wallet.balance * rate
                        total_value += value_in_base
                        
                        wallet_info.append({
                            "currency": currency_code,
                            "display_name": display_name,
                            "balance": wallet.balance,
                            "value_in_base": value_in_base,
                            "rate": rate,
                            "type": "fiat" if isinstance(currency, FiatCurrency) else "crypto"
                        })
                    else:
                        wallet_info.append({
                            "currency": currency_code,
                            "display_name": display_name,
                            "balance": wallet.balance,
                            "value_in_base": None,
                            "rate": None,
                            "type": "fiat" if isinstance(currency, FiatCurrency) else "crypto"
                        })
                except CurrencyNotFoundError:
                    wallet_info.append({
                        "currency": currency_code,
                        "display_name": "Unknown",
                        "balance": wallet.balance,
                        "value_in_base": None,
                        "rate": None,
                        "type": "unknown"
                    })
        
        message_lines = [f"Портфель пользователя (база: {base_currency}):"]
        
        for info in wallet_info:
            if info["value_in_base"] is not None:
                line = f"  - {info['currency']} ({info['display_name']}): {info['balance']:.4f} → {info['value_in_base']:.2f} {base_currency}"
            else:
                line = f"  - {info['currency']} ({info['display_name']}): {info['balance']:.4f} → Курс недоступен"
            message_lines.append(line)
        
        message_lines.append("-" * 40)
        message_lines.append(f"ИТОГО: {total_value:,.2f} {base_currency}")
        
        return True, "\n".join(message_lines), {
            "total_value": total_value,
            "wallets": wallet_info,
            "base_currency": base_currency
        }


class TradeManager:
    
    _db = DatabaseManager()
    _settings = SettingsLoader()

    @staticmethod
    @log_action("BUY", verbose=True)
    def buy(user_id: int, currency_code: str, amount: float) -> Tuple[bool, str]:
        try:
            currency = CurrencyRegistry.get_currency(currency_code)
        except CurrencyNotFoundError:
            raise CurrencyNotFoundError(currency_code)
        
        if not validate_amount(amount):
            raise ValidationError("amount", "'amount' должен быть положительным числом")
        
        portfolio = PortfolioManager.get_user_portfolio(user_id)
        
        rate = get_exchange_rate("USD", currency_code)
        if not rate:
            raise RateUnavailableError("USD", currency_code)
        
        cost_usd = amount * rate
        
        usd_wallet = portfolio.get_wallet("USD")
        if not usd_wallet or usd_wallet.balance < cost_usd:
            available = usd_wallet.balance if usd_wallet else 0.0
            raise InsufficientFundsError("USD", available, cost_usd)
        
        try:
            target_wallet = portfolio.get_wallet(currency_code)
            old_balance = target_wallet.balance if target_wallet else 0.0
            
            usd_wallet.withdraw(cost_usd)
            
            if not target_wallet:
                portfolio.add_currency(currency_code, 0.0)
                target_wallet = portfolio.get_wallet(currency_code)
            
            target_wallet.deposit(amount)
            
            PortfolioManager.save_portfolio(portfolio)
            
            message = (f"Покупка выполнена: {amount:.4f} {currency_code} ({currency.name}) по курсу {1/rate:.2f} USD/{currency_code}\n"
                      f"Изменения в портфеле:\n"
                      f"- {currency_code}: было {old_balance:.4f} → стало {target_wallet.balance:.4f}\n"
                      f"Оценочная стоимость покупки: {cost_usd:.2f} USD")
            
            return True, message
            
        except ValueError as e:
            raise ValidationError("operation", str(e))
    
    @staticmethod
    @log_action("SELL", verbose=True)
    def sell(user_id: int, currency_code: str, amount: float) -> Tuple[bool, str]:
        try:
            currency = CurrencyRegistry.get_currency(currency_code)
        except CurrencyNotFoundError:
            raise CurrencyNotFoundError(currency_code)
        
        if not validate_amount(amount):
            raise ValidationError("amount", "'amount' должен быть положительным числом")
        
        portfolio = PortfolioManager.get_user_portfolio(user_id)
        
        source_wallet = portfolio.get_wallet(currency_code)
        if not source_wallet:
            raise ValidationError("currency", f"У вас нет кошелька '{currency_code}'")
        
        if source_wallet.balance < amount:
            raise InsufficientFundsError(currency_code, source_wallet.balance, amount)
        
        rate = get_exchange_rate(currency_code, "USD")
        if not rate:
            raise RateUnavailableError(currency_code, "USD")
        
        try:
            old_balance = source_wallet.balance
            
            revenue_usd = amount * rate
            
            source_wallet.withdraw(amount)
            
            usd_wallet = portfolio.get_wallet("USD")
            if not usd_wallet:
                portfolio.add_currency("USD", 0.0)
                usd_wallet = portfolio.get_wallet("USD")
            
            usd_wallet.deposit(revenue_usd)
            
            PortfolioManager.save_portfolio(portfolio)
            
            message = (f"Продажа выполнена: {amount:.4f} {currency_code} ({currency.name}) по курсу {rate:.2f} USD/{currency_code}\n"
                      f"Изменения в портфеле:\n"
                      f"- {currency_code}: было {old_balance:.4f} → стало {source_wallet.balance:.4f}\n"
                      f"Оценочная выручка: {revenue_usd:.2f} USD")
            
            return True, message
            
        except ValueError as e:
            raise ValidationError("operation", str(e))

class RateManager:
    
    _db = DatabaseManager()
    _settings = SettingsLoader()

    @staticmethod
    @retry_on_failure(max_retries=2, delay=1.0)
    @log_action("GET_RATE", verbose=False)
    def get_rate(from_currency: str, to_currency: str) -> Tuple[bool, str, Optional[float]]:
        try:
            from_currency_obj = CurrencyRegistry.get_currency(from_currency)
            to_currency_obj = CurrencyRegistry.get_currency(to_currency)
        except CurrencyNotFoundError as e:
            raise CurrencyNotFoundError(e.currency_code)
        
        rates_data = RateManager._db.read_collection("rates")
        
        cache_key = f"{from_currency}_{to_currency}"
        
        if (RateManager._settings.enable_rate_cache and 
            cache_key in rates_data and 
            "updated_at" in rates_data[cache_key]):
            
            try:
                updated_at = datetime.fromisoformat(rates_data[cache_key]["updated_at"])
                ttl_seconds = RateManager._settings.rates_ttl_seconds
                
                if datetime.now() - updated_at < timedelta(seconds=ttl_seconds):
                    rate = rates_data[cache_key]["rate"]
                    message = RateManager._format_rate_message(
                        from_currency, to_currency, rate, updated_at, from_cache=True
                    )
                    return True, message, rate
            except (ValueError, KeyError):
                pass
        
        try:
            rate = get_exchange_rate(from_currency, to_currency)
            if rate is None:
                raise RateUnavailableError(from_currency, to_currency)
            
            rates_data[cache_key] = {
                "rate": rate,
                "updated_at": datetime.now().isoformat(),
                "from_currency": from_currency,
                "to_currency": to_currency
            }
            
            rates_data["last_refresh"] = datetime.now().isoformat()
            rates_data["source"] = "stub" if RateManager._settings.fake_api_mode else "api"
            
            RateManager._db.write_collection("rates", rates_data)
            
            message = RateManager._format_rate_message(
                from_currency, to_currency, rate, datetime.now(), from_cache=False
            )
            
            return True, message, rate
            
        except Exception as e:
            raise ApiRequestError(
                reason=str(e),
                service="ExchangeRateAPI"
            )
    
    @staticmethod
    def _format_rate_message(from_currency: str, to_currency: str, rate: float, 
                            timestamp: datetime, from_cache: bool = False) -> str:
        try:
            from_curr = CurrencyRegistry.get_currency(from_currency)
            to_curr = CurrencyRegistry.get_currency(to_currency)
            from_name = from_curr.name
            to_name = to_curr.name
        except CurrencyNotFoundError:
            from_name = from_currency
            to_name = to_currency
        
        cache_info = " (из кеша)" if from_cache else ""
        timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        
        message = (f"Курс {from_currency} ({from_name}) → {to_currency} ({to_name}): {rate:.8f}"
                  f"{cache_info}\n"
                  f"Обновлено: {timestamp_str}")
        
        if rate != 0:
            reverse_rate = 1 / rate
            message += f"\nОбратный курс {to_currency} → {from_currency}: {reverse_rate:.8f}"
        
        return message
    
    @staticmethod
    def list_supported_currencies() -> str:
        currencies = CurrencyRegistry.get_all_currencies()
        
        fiat_currencies = []
        crypto_currencies = []
        
        for code, currency in currencies.items():
            info = currency.get_display_info()
            if isinstance(currency, FiatCurrency):
                fiat_currencies.append(f"  {info}")
            else:
                crypto_currencies.append(f"  {info}")
        
        result = ["Поддерживаемые валюты:"]
        
        if fiat_currencies:
            result.append("\nФиатные валюты:")
            result.extend(fiat_currencies)
        
        if crypto_currencies:
            result.append("\nКриптовалюты:")
            result.extend(crypto_currencies)
        
        result.append(f"\nВсего валют: {len(currencies)}")
        
        return "\n".join(result)