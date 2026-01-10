import hashlib
import json
import os
import time
from datetime import datetime, timedelta
from typing import Any

from valutatrade_hub.core.currencies import CryptoCurrency, CurrencyRegistry, FiatCurrency
from valutatrade_hub.core.exceptions import (
    AuthenticationError,
    CurrencyNotFoundError,
    InsufficientFundsError,
    PortfolioNotFoundError,
    RateUnavailableError,
    ValidationError,
)
from valutatrade_hub.core.models import Portfolio, User
from valutatrade_hub.core.utils import (
    get_cache_info,
    get_exchange_rate,
    validate_amount,
)
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader


class SessionManager:
    """
    Менеджер сессий для хранения текущего пользователя
    """
    _current_user: User | None = None
    _settings = SettingsLoader()

    @classmethod
    def get_current_user(cls) -> User | None:
        """Возвращает текущего пользователя, загружая из файла при необходимости."""
        if cls._current_user is None:
            cls._load_session_from_file()
        return cls._current_user

    @classmethod
    def set_current_user(cls, user: User | None) -> None:
        """Устанавливает текущего пользователя и сохраняет сессию."""
        cls._current_user = user
        cls._save_session_to_file(user)

    @classmethod
    def is_logged_in(cls) -> bool:
        """Проверяет, залогинен ли пользователь."""
        return cls.get_current_user() is not None

    @classmethod
    def require_login(cls) -> None:
        """Проверяет авторизацию, выбрасывает исключение если не залогинен."""
        if not cls.is_logged_in():
            raise AuthenticationError("Сначала выполните команду login")

    @classmethod
    def _get_session_file_path(cls) -> str:
        """Возвращает путь к файлу сессии."""
        return cls._settings.get_data_file_path("session.json")

    @classmethod
    def _load_session_from_file(cls) -> None:
        """Загружает сессию из файла."""
        session_file = cls._get_session_file_path()

        try:
            if os.path.exists(session_file):
                with open(session_file, encoding='utf-8') as f:
                    session_data = json.load(f)

                # Проверяем срок действия сессии (24 часа)
                if "expires_at" in session_data:
                    expires_at = datetime.fromisoformat(session_data["expires_at"])
                    if datetime.now() > expires_at:
                        # Сессия истекла
                        cls._clear_session_file()
                        return

                # Восстанавливаем пользователя из сессии
                if "user_id" in session_data and "username" in session_data:
                    # Создаем минимальный объект User для сессии
                    cls._current_user = User(
                        user_id=session_data["user_id"],
                        username=session_data["username"],
                        hashed_password="",  # Пароль не храним в сессии
                        salt="",
                        registration_date=datetime.fromisoformat(
                            session_data.get("registration_date", datetime.now().isoformat())
                        )
                    )

        except (OSError, json.JSONDecodeError, ValueError, KeyError) as e:
            # Если файл поврежден, очищаем его
            print(f"Warning: Session file corrupted: {e}")
            cls._clear_session_file()

    @classmethod
    def _save_session_to_file(cls, user: User | None) -> None:
        """Сохраняет сессию в файл."""
        session_file = cls._get_session_file_path()

        try:
            if user is None:
                # Выход из системы - удаляем файл сессии
                cls._clear_session_file()
                return

            # Создаем данные сессии
            session_data = {
                "user_id": user.user_id,
                "username": user.username,
                "registration_date": user.registration_date.isoformat(),
                "expires_at": (datetime.now() + timedelta(hours=24)).isoformat(),  # 24 часа
                "created_at": datetime.now().isoformat()
            }

            # Сохраняем в файл
            os.makedirs(os.path.dirname(session_file), exist_ok=True)
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)

        except (OSError, TypeError) as e:
            print(f"Error saving session: {e}")

    @classmethod
    def _clear_session_file(cls) -> None:
        """Очищает файл сессии."""
        session_file = cls._get_session_file_path()
        try:
            if os.path.exists(session_file):
                os.remove(session_file)
        except OSError as e:
            print(f"Error clearing session file: {e}")
        finally:
            cls._current_user = None

    @classmethod
    def logout(cls) -> None:
        """Выход из системы."""
        cls._clear_session_file()

class UserManager:
    """
    Менеджер пользователей
    """
    _db = DatabaseManager()
    _settings = SettingsLoader()

    @staticmethod
    @log_action("REGISTER", verbose=True)
    def register(username: str, password: str) -> tuple[bool, str]:
        """
        Регистрирует нового пользователя
        """
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
    def login(username: str, password: str) -> tuple[bool, str, User | None]:
        """
        Авторизует пользователя
        """
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

    @staticmethod
    def get_next_user_id() -> int:
        """
        Генерирует следующий ID пользователя
        """
        users = UserManager._db.read_collection("users")
        if not users:
            return 1
        return max(user["user_id"] for user in users) + 1

    @staticmethod
    def find_user_by_username(username: str) -> dict | None:
        """
        Находит пользователя по имени
        """
        return UserManager._db.find_one("users", {"username": username})


class PortfolioManager:
    """
    Менеджер портфелей
    """
    _db = DatabaseManager()
    _settings = SettingsLoader()

    @staticmethod
    def create_portfolio(user_id: int) -> bool:
        """
        Создаёт пустой портфель для пользователя
        """
        portfolio_data = {
            "user_id": user_id,
            "wallets": {}
        }

        return PortfolioManager._db.insert_one("portfolios", portfolio_data)

    @staticmethod
    def find_portfolio(user_id: int) -> dict | None:
        """
        Находит портфель пользователя
        """
        return PortfolioManager._db.find_one("portfolios", {"user_id": user_id})

    @staticmethod
    def get_user_portfolio(user_id: int) -> Portfolio | None:
        """
        Загружает портфель пользователя
        """
        portfolio_data = PortfolioManager.find_portfolio(user_id)
        if not portfolio_data:
            raise PortfolioNotFoundError(user_id)

        return Portfolio.from_dict(portfolio_data)

    @staticmethod
    def save_portfolio(portfolio: Portfolio) -> bool:
        """
        Сохраняет портфель
        """
        return PortfolioManager._db.update_one(
            "portfolios",
            {"user_id": portfolio.user_id},
            portfolio.to_dict()
        )

    @staticmethod
    @log_action("SHOW_PORTFOLIO", verbose=False)
    def show_portfolio(user_id: int, base_currency: str = "USD") -> tuple[bool, str, dict[str, Any] | None]:
        """
        Показывает все кошельки и итоговую стоимость в базовой валюте
        """
        try:
            CurrencyRegistry.get_currency(base_currency)
        except CurrencyNotFoundError:
            raise

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

        cache_info = get_cache_info()
        if not cache_info["is_valid"]:
            message_lines.append("\nВнимание: данные о курсах могут быть устаревшими.")
            message_lines.append("Используйте 'update-rates' для обновления курсов.")

        return True, "\n".join(message_lines), {
            "total_value": total_value,
            "wallets": wallet_info,
            "base_currency": base_currency,
            "cache_info": cache_info
        }


class TradeManager:
    """
    Менеджер торговых операций
    """
    _db = DatabaseManager()
    _settings = SettingsLoader()

    @staticmethod
    @log_action("BUY", verbose=True)
    def buy(user_id: int, currency_code: str, amount: float) -> tuple[bool, str]:
        """
        Покупает валюту
        """
        try:
            currency = CurrencyRegistry.get_currency(currency_code)
        except CurrencyNotFoundError as e:
            raise CurrencyNotFoundError(currency_code) from e

        if not validate_amount(amount):
            raise ValidationError("amount", "'amount' должен быть положительным числом")

        cache_info = get_cache_info()
        if not cache_info["is_valid"]:
            print("Внимание: данные о курсах могут быть устаревшими.")
            print("Используйте 'update-rates' для получения актуальных курсов.")

        portfolio = PortfolioManager.get_user_portfolio(user_id)

        rate = get_exchange_rate(currency_code, "USD")
        if not rate:
            raise RateUnavailableError(currency_code, "USD")

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

            if cache_info["last_refresh"]:
                message += f"\nКурс актуален на: {cache_info['last_refresh']}"

            return True, message

        except ValueError as e:
            raise ValidationError("operation", str(e)) from e

    @staticmethod
    @log_action("SELL", verbose=True)
    def sell(user_id: int, currency_code: str, amount: float) -> tuple[bool, str]:
        """
        Продаёт валюту
        """
        try:
            currency = CurrencyRegistry.get_currency(currency_code)
        except CurrencyNotFoundError as e:
            raise CurrencyNotFoundError(currency_code) from e

        if not validate_amount(amount):
            raise ValidationError("amount", "'amount' должен быть положительным числом")

        cache_info = get_cache_info()
        if not cache_info["is_valid"]:
            print("Внимание: данные о курсах могут быть устаревшими.")
            print("Используйте 'update-rates' для получения актуальных курсов.")

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

            if cache_info["last_refresh"]:
                message += f"\nКурс актуален на: {cache_info['last_refresh']}"

            return True, message

        except ValueError as e:
            raise ValidationError("operation", str(e)) from e

    @staticmethod
    @log_action("DEPOSIT", verbose=True)
    def deposit(user_id: int, currency: str, amount: float) -> tuple[bool, str]:
        """
        Пополняет баланс кошелька.

        Args:
            user_id: ID пользователя
            currency: Код валюты
            amount: Сумма пополнения

        Returns:
            Кортеж (успех, сообщение)

        Raises:
            CurrencyNotFoundError: Если валюта неизвестна
            ValidationError: Если данные невалидны
        """
        try:
            CurrencyRegistry.get_currency(currency)
        except CurrencyNotFoundError:
            raise CurrencyNotFoundError(currency) from None

        if not validate_amount(amount):
            raise ValidationError("amount", "'amount' должен быть положительным числом")

        portfolio = PortfolioManager.get_user_portfolio(user_id)

        try:
            # Получаем или создаем кошелёк
            wallet = portfolio.get_wallet(currency)
            if not wallet:
                portfolio.add_currency(currency, 0.0)
                wallet = portfolio.get_wallet(currency)

            old_balance = wallet.balance
            wallet.deposit(amount)

            # Сохраняем изменения
            PortfolioManager.save_portfolio(portfolio)

            message = (f"Баланс пополнен: +{amount:.4f} {currency}\n"
                      f"Кошелёк {currency}: было {old_balance:.4f} → стало {wallet.balance:.4f}")

            return True, message

        except ValueError as e:
            raise ValidationError("operation", str(e)) from None

    @staticmethod
    @log_action("WITHDRAW", verbose=True)
    def withdraw(user_id: int, currency: str, amount: float) -> tuple[bool, str]:
        """
        Снимает средства с кошелька.
        """
        try:
            CurrencyRegistry.get_currency(currency)
        except CurrencyNotFoundError:
            raise CurrencyNotFoundError(currency) from None

        if not validate_amount(amount):
            raise ValidationError("amount", "'amount' должен быть положительным числом")

        portfolio = PortfolioManager.get_user_portfolio(user_id)

        wallet = portfolio.get_wallet(currency)
        if not wallet:
            raise ValidationError("currency", f"У вас нет кошелька '{currency}'")

        if wallet.balance < amount:
            raise InsufficientFundsError(currency, wallet.balance, amount)

        try:
            old_balance = wallet.balance
            withdrawn = wallet.withdraw(amount)

            # Сохраняем изменения
            PortfolioManager.save_portfolio(portfolio)

            message = (f"Средства сняты: -{withdrawn:.4f} {currency}\n"
                      f"Кошелёк {currency}: было {old_balance:.4f} → стало {wallet.balance:.4f}")

            return True, message

        except ValueError as e:
            raise ValidationError("operation", str(e)) from None

    @staticmethod
    @log_action("TRANSFER", verbose=True)
    def transfer(user_id: int, from_currency: str, to_currency: str, amount: float) -> tuple[bool, str]:
        """
        Переводит средства между валютами по текущему курсу
        """
        # Команда объединяет sell и buy
        try:
            # Сначала продаем исходную валюту
            sell_success, sell_message = TradeManager.sell(user_id, from_currency, amount)
            if not sell_success:
                return False, f"Ошибка при продаже: {sell_message}"

            # Затем покупаем целевую валюту на полученные USD
            return True, (f"Перевод {amount:.4f} {from_currency} → {to_currency}\n"
                         f"{sell_message}")

        except Exception as e:
            return False, f"Ошибка при переводе: {e}"

    @staticmethod
    @log_action("BALANCE", verbose=False)
    def get_balance(user_id: int, currency: str | None = None) -> tuple[bool, str, dict[str, Any] | None]:
        """
        Показывает баланс кошелька или всех кошельков
        """
        portfolio = PortfolioManager.get_user_portfolio(user_id)

        if currency:
            # Показать баланс конкретной валюты
            currency_upper = currency.upper()
            wallet = portfolio.get_wallet(currency_upper)

            if not wallet:
                return False, f"У вас нет кошелька '{currency}'", None

            try:
                curr = CurrencyRegistry.get_currency(currency_upper)
                display_name = curr.name
            except CurrencyNotFoundError:
                display_name = "Unknown"

            message = (f"Баланс {currency_upper} ({display_name}):\n"
                      f"  Текущий: {wallet.balance:.4f} {currency_upper}")

            # Добавляем стоимость в USD
            if currency_upper != "USD":
                rate = get_exchange_rate(currency_upper, "USD")
                if rate:
                    value_usd = wallet.balance * rate
                    message += f"\n  В USD: {value_usd:.2f} USD (курс: {rate:.4f})"

            return True, message, {
                "currency": currency_upper,
                "balance": wallet.balance,
                "display_name": display_name
            }
        else:
            # Показать все кошельки
            wallets = portfolio.wallets
            message_lines = ["Ваши кошельки:"]
            total_usd = 0.0

            for curr_code, wallet in sorted(wallets.items()):
                if wallet.balance > 0:
                    try:
                        curr = CurrencyRegistry.get_currency(curr_code)
                        display_name = curr.name
                    except CurrencyNotFoundError:
                        display_name = "Unknown"

                    line = f"  {curr_code} ({display_name}): {wallet.balance:.4f}"

                    # Добавляем стоимость в USD
                    if curr_code == "USD":
                        # USD уже в USD
                        value_usd = wallet.balance
                        total_usd += value_usd
                    else:
                        # Конвертируем в USD
                        rate = get_exchange_rate(curr_code, "USD")
                        if rate:
                            value_usd = wallet.balance * rate
                            total_usd += value_usd

                    message_lines.append(line)

            message_lines.append("-" * 40)
            message_lines.append(f"Общая стоимость: {total_usd:.2f} USD")

            return True, "\n".join(message_lines), {
                "total_usd": total_usd,
                "wallets_count": len([w for w in wallets.values() if w.balance > 0])
            }


class RateManager:
    @staticmethod
    def get_rate(from_currency: str, to_currency: str) -> tuple[bool, str, float | None]:
        """
        Получает курс валюты из кеша
        """
        try:
            from_curr = CurrencyRegistry.get_currency(from_currency)
            to_curr = CurrencyRegistry.get_currency(to_currency)
        except CurrencyNotFoundError as e:
            return False, f"Неизвестная валюта: {e.currency_code}", None

        rate = get_exchange_rate(from_currency, to_currency)

        if rate is None:
            return False, f"Курс {from_currency}→{to_currency} недоступен в кеше. Выполните 'update-rates'.", None

        cache_info = get_cache_info()

        timestamp = cache_info.get("last_refresh", "неизвестно")
        source = cache_info.get("source", "кеш")

        message = f"Курс {from_currency} ({from_curr.name}) → {to_currency} ({to_curr.name}): {rate:.8f}"
        message += f"\nИсточник: {source}"
        message += f"\nОбновлено: {timestamp}"

        if rate != 0:
            reverse_rate = 1 / rate
            message += f"\nОбратный курс {to_currency} → {from_currency}: {reverse_rate:.8f}"

        if not cache_info.get("is_valid", False):
            message += "\n\nВнимание: данные могут быть устаревшими."
            message += "\nИспользуйте 'update-rates' для обновления курсов."

        return True, message, rate

    @staticmethod
    def list_supported_currencies() -> str:
        """
        Возвращает список поддерживаемых валют
        """
        CurrencyRegistry.update_from_cache()
        currencies = CurrencyRegistry.get_all_currencies()

        fiat_currencies = []
        crypto_currencies = []
        unknown_currencies = []

        for code, currency in currencies.items():
            info = currency.get_display_info()
            if isinstance(currency, FiatCurrency):
                fiat_currencies.append(f"  {info}")
            elif isinstance(currency, CryptoCurrency):
                crypto_currencies.append(f"  {info}")
            else:
                unknown_currencies.append(f"  {code} - {currency.name}")

        result = ["Поддерживаемые валюты:"]

        if fiat_currencies:
            result.append("\nФиатные валюты:")
            result.extend(fiat_currencies)

        if crypto_currencies:
            result.append("\nКриптовалюты:")
            result.extend(crypto_currencies)

        if unknown_currencies:
            result.append("\nПрочие валюты:")
            result.extend(unknown_currencies)

        result.append(f"\nВсего валют: {len(currencies)}")

        cache_info = get_cache_info()
        if cache_info["exists"]:
            result.append(f"\nКурсов в кеше: {cache_info['rates_count']}")
            result.append(f"Последнее обновление: {cache_info['last_refresh'] or 'никогда'}")
            if not cache_info["is_valid"]:
                result.append("Кеш устарел. Используйте 'update-rates'.")
        else:
            result.append("\nКеш курсов пуст. Используйте 'update-rates'.")

        return "\n".join(result)
