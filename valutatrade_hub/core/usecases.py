import hashlib
import time
from datetime import datetime
from typing import Dict, Optional, Tuple, Any
from pathlib import Path

from valutatrade_hub.core.models import User, Portfolio, Wallet
from valutatrade_hub.core.utils import load_json, save_json, validate_currency, validate_amount, get_exchange_rate


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


class UserManager:
    
    @staticmethod
    def get_next_user_id() -> int:
        users = load_json("data/users.json")
        if not users:
            return 1
        return max(user["user_id"] for user in users) + 1
    
    @staticmethod
    def find_user_by_username(username: str) -> Optional[dict]:
        users = load_json("data/users.json")
        for user in users:
            if user["username"] == username:
                return user
        return None
    
    @staticmethod
    def register(username: str, password: str) -> Tuple[bool, str]:
        if len(password) < 4:
            return False, "Пароль должен быть не короче 4 символов"
        
        if UserManager.find_user_by_username(username):
            return False, f"Имя пользователя '{username}' уже занято"
        
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
        
        users = load_json("data/users.json")
        users.append(user_data)
        
        if save_json(users, "data/users.json"):
            PortfolioManager.create_portfolio(user_id)
            return True, f"Пользователь '{username}' зарегистрирован (id={user_id}). Войдите: login --username {username} --password ****"
        
        return False, "Ошибка при сохранении пользователя"
    
    @staticmethod
    def login(username: str, password: str) -> Tuple[bool, str, Optional[User]]:
        user_data = UserManager.find_user_by_username(username)
        if not user_data:
            return False, f"Пользователь '{username}' не найден", None
        
        hashed_input = hashlib.sha256(
            f"{password}{user_data['salt']}".encode()
        ).hexdigest()
        
        if hashed_input != user_data["hashed_password"]:
            return False, "Неверный пароль", None

        user = User.from_dict(user_data)
        return True, f"Вы вошли как '{username}'", user


class PortfolioManager:
    
    @staticmethod
    def create_portfolio(user_id: int) -> bool:
        portfolio_data = {
            "user_id": user_id,
            "wallets": {}
        }
        
        portfolios = load_json("data/portfolios.json")
        portfolios.append(portfolio_data)
        
        return save_json(portfolios, "data/portfolios.json")
    
    @staticmethod
    def find_portfolio(user_id: int) -> Optional[dict]:
        portfolios = load_json("data/portfolios.json")
        for portfolio in portfolios:
            if portfolio["user_id"] == user_id:
                return portfolio
        return None
    
    @staticmethod
    def get_user_portfolio(user_id: int) -> Optional[Portfolio]:
        portfolio_data = PortfolioManager.find_portfolio(user_id)
        if not portfolio_data:
            return None
        
        return Portfolio.from_dict(portfolio_data)
    
    @staticmethod
    def save_portfolio(portfolio: Portfolio) -> bool:
        portfolios = load_json("data/portfolios.json")
        
        for i, p in enumerate(portfolios):
            if p["user_id"] == portfolio.user_id:
                portfolios[i] = portfolio.to_dict()
                return save_json(portfolios, "data/portfolios.json")

        portfolios.append(portfolio.to_dict())
        return save_json(portfolios, "data/portfolios.json")

    @staticmethod
    def show_portfolio(user_id: int, base_currency: str = "USD") -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        if not validate_currency(base_currency):
            return False, f"Неизвестная базовая валюта '{base_currency}'", None
        
        portfolio = PortfolioManager.get_user_portfolio(user_id)
        if not portfolio:
            return False, "Портфель не найден", None
        
        wallets = portfolio.wallets
        
        if not wallets:
            return True, "Портфель пуст", {"total_value": 0.0, "wallets": []}
        
        wallet_info = []
        total_value = 0.0
        
        for currency_code, wallet in wallets.items():
            if wallet.balance > 0:
                rate = get_exchange_rate(currency_code, base_currency)
                
                if rate is not None:
                    value_in_base = wallet.balance * rate
                    total_value += value_in_base
                    
                    wallet_info.append({
                        "currency": currency_code,
                        "balance": wallet.balance,
                        "value_in_base": value_in_base,
                        "rate": rate
                    })
                else:
                    wallet_info.append({
                        "currency": currency_code,
                        "balance": wallet.balance,
                        "value_in_base": None,
                        "rate": None
                    })

        message_lines = [f"Портфель пользователя (база: {base_currency}):"]
        
        for info in wallet_info:
            if info["value_in_base"] is not None:
                line = f"  - {info['currency']}: {info['balance']:.4f} → {info['value_in_base']:.2f} {base_currency}"
            else:
                line = f"  - {info['currency']}: {info['balance']:.4f} → Курс недоступен"
            message_lines.append(line)
        
        message_lines.append("-" * 40)
        message_lines.append(f"ИТОГО: {total_value:,.2f} {base_currency}")
        
        return True, "\n".join(message_lines), {
            "total_value": total_value,
            "wallets": wallet_info,
            "base_currency": base_currency
        }


class TradeManager:
    
    @staticmethod
    def buy(user_id: int, currency: str, amount: float) -> Tuple[bool, str]:
        if not validate_currency(currency):
            return False, f"Неверный код валюты: '{currency}'"
        
        if not validate_amount(amount):
            return False, "'amount' должен быть положительным числом"
        
        portfolio = PortfolioManager.get_user_portfolio(user_id)
        if not portfolio:
            return False, "Портфель не найден"
        
        rate = get_exchange_rate("USD", currency)
        if not rate:
            return False, f"Не удалось получить курс для {currency}→USD"
        
        cost_usd = amount * rate
        
        usd_wallet = portfolio.get_wallet("USD")
        if not usd_wallet or usd_wallet.balance < cost_usd:
            return False, f"Недостаточно средств. Нужно: {cost_usd:.2f} USD"
        
        try:
            usd_wallet.withdraw(cost_usd)
            
            target_wallet = portfolio.get_wallet(currency)
            if not target_wallet:
                portfolio.add_currency(currency, 0.0)
                target_wallet = portfolio.get_wallet(currency)
            
            target_wallet.deposit(amount)
            
            PortfolioManager.save_portfolio(portfolio)
            
            message = (f"Покупка выполнена: {amount:.4f} {currency} по курсу {1/rate:.2f} USD/{currency}\n"
                      f"Изменения в портфеле:\n"
                      f"- {currency}: было {target_wallet.balance - amount:.4f} → стало {target_wallet.balance:.4f}\n"
                      f"Оценочная стоимость покупки: {cost_usd:.2f} USD")
            
            return True, message
            
        except ValueError as e:
            return False, str(e)
    
    @staticmethod
    def sell(user_id: int, currency: str, amount: float) -> Tuple[bool, str]:
        if not validate_currency(currency):
            return False, f"Неверный код валюты: '{currency}'"
        
        if not validate_amount(amount):
            return False, "'amount' должен быть положительным числом"
        
        portfolio = PortfolioManager.get_user_portfolio(user_id)
        if not portfolio:
            return False, "Портфель не найден"
        
        source_wallet = portfolio.get_wallet(currency)
        if not source_wallet:
            return False, f"У вас нет кошелька '{currency}'"
        
        if source_wallet.balance < amount:
            return False, (f"Недостаточно средств: доступно {source_wallet.balance:.4f} {currency}, "
                          f"требуется {amount:.4f} {currency}")
        
        from valutatrade_hub.core.utils import get_exchange_rate
        rate = get_exchange_rate(currency, "USD")
        if not rate:
            return False, f"Не удалось получить курс для {currency}→USD"
        
        try:
            revenue_usd = amount * rate
            
            source_wallet.withdraw(amount)
            
            usd_wallet = portfolio.get_wallet("USD")
            if not usd_wallet:
                portfolio.add_currency("USD", 0.0)
                usd_wallet = portfolio.get_wallet("USD")
            
            usd_wallet.deposit(revenue_usd)
            
            PortfolioManager.save_portfolio(portfolio)
            
            message = (f"Продажа выполнена: {amount:.4f} {currency} по курсу {rate:.2f} USD/{currency}\n"
                      f"Изменения в портфеле:\n"
                      f"- {currency}: было {source_wallet.balance + amount:.4f} → стало {source_wallet.balance:.4f}\n"
                      f"Оценочная выручка: {revenue_usd:.2f} USD")
            
            return True, message
            
        except ValueError as e:
            return False, str(e)

class RateManager:
    
    @staticmethod
    def get_rate(from_currency: str, to_currency: str) -> Tuple[bool, str, Optional[float]]:
        if not validate_currency(from_currency):
            return False, f"Неверный код исходной валюты: '{from_currency}'", None
        
        if not validate_currency(to_currency):
            return False, f"Неверный код целевой валюты: '{to_currency}'", None
        
        rate = get_exchange_rate(from_currency, to_currency)
        if rate is None:
            return False, f"Курс {from_currency}→{to_currency} недоступен. Повторите попытку позже.", None
        
        reverse_rate = get_exchange_rate(to_currency, from_currency)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"Курс {from_currency}→{to_currency}: {rate:.8f} (обновлено: {timestamp})"
        
        if reverse_rate:
            message += f"\nОбратный курс {to_currency}→{from_currency}: {reverse_rate:.8f}"
        
        return True, message, rate