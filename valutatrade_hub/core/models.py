import hashlib
import time
from datetime import datetime

from valutatrade_hub.core.currencies import CurrencyRegistry
from valutatrade_hub.core.exceptions import CurrencyNotFoundError, InsufficientFundsError


class User:
    """
    Класс пользователя системы
    """
    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime | None = None
    ):
        self._user_id = user_id
        self._username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date or datetime.now()

    @property
    def user_id(self) -> int:
        """
        Геттер для идентификатора пользователя
        """
        return self._user_id

    @property
    def username(self) -> str:
        """
        Геттер для имени пользователя
        """
        return self._username

    @username.setter
    def username(self, value: str):
        """
        Сеттер для имени пользователя с проверкой
        """
        if not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value.strip()

    @property
    def hashed_password(self) -> str:
        """
        Геттер для хешированного пароля
        """
        return self._hashed_password

    @property
    def salt(self) -> str:
        """
        Геттер для соли
        """
        return self._salt

    @property
    def registration_date(self) -> datetime:
        """
        Геттер для даты регистрации
        """
        return self._registration_date

    def get_user_info(self) -> dict:
        """
        Возвращает информацию о пользователе (без пароля)
        """
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
            "salt": self._salt
        }

    def change_password(self, new_password: str) -> None:
        """
        Изменяет пароль пользователя
        """
        if len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")

        self._hashed_password = self._hash_password(new_password, self._salt)

    def verify_password(self, password: str) -> bool:
        """
        Проверяет введённый пароль на совпадение
        """
        hashed_input = self._hash_password(password, self._salt)
        return hashed_input == self._hashed_password

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        """
        Хеширует пароль с использованием соли
        """
        hasher = hashlib.sha256()
        hasher.update(f"{password}{salt}".encode())
        return hasher.hexdigest()

    @classmethod
    def create_user(cls, user_id: int, username: str, password: str) -> 'User':
        """
        Создаёт нового пользователя с автоматической генерацией соли
        """
        if len(password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")

        salt = hashlib.sha256(f"{username}{time.time()}".encode()).hexdigest()[:8]

        hashed_password = cls._hash_password(password, salt)

        return cls(
            user_id=user_id,
            username=username,
            hashed_password=hashed_password,
            salt=salt
        )

    def to_dict(self) -> dict:
        """
        Конвертирует объект User в словарь для сохранения в JSON
        """
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        """
        Создаёт объект User из словаря (например, из JSON)
        """
        registration_date = datetime.fromisoformat(data["registration_date"])

        return cls(
            user_id=data["user_id"],
            username=data["username"],
            hashed_password=data["hashed_password"],
            salt=data["salt"],
            registration_date=registration_date
        )

    def __repr__(self) -> str:
        """
        Строковое представление объекта (без пароля)
        """
        return (f"User(user_id={self._user_id}, "
                f"username='{self._username}', "
                f"registration_date={self._registration_date.strftime('%Y-%m-%d %H:%M:%S')})")


class Wallet:
    def __init__(self, currency_code: str, balance: float = 0.0):
        """
        Инициализация кошелька
        """
        self.currency_code = currency_code
        self._balance = balance

    @property
    def currency_code(self) -> str:
        """
        Геттер для кода валюты
        """
        return self._currency_code

    @currency_code.setter
    def currency_code(self, value: str):
        """
        Сеттер для кода валюты с проверкой
        """
        if not value.strip():
            raise ValueError("Код валюты не может быть пустым")
        self._currency_code = value.strip().upper()

    @property
    def balance(self) -> float:
        """
        Геттер для баланса
        """
        return self._balance

    @balance.setter
    def balance(self, value: float):
        """
        Сеттер для баланса с проверкой
        """
        if not isinstance(value, (int | float)):
            raise TypeError(f"Баланс должен быть числом, получено {type(value).__name__}")

        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")

        self._balance = float(value)

    def deposit(self, amount: float) -> None:
        """
        Пополнение баланса
        """
        if amount <= 0:
            raise ValueError("Сумма пополнения должна быть положительной")

        self.balance += amount
        print(f"Кошелёк {self.currency_code}: пополнено {amount:.2f}. Новый баланс: {self.balance:.2f}")

    def withdraw(self, amount: float) -> float:
        """
        Снятие средств с кошелька
        """
        if amount <= 0:
            raise ValueError("Сумма снятия должна быть положительной")

        if amount > self.balance:
            raise InsufficientFundsError(self.currency_code, self.balance, amount)

        self.balance -= amount
        return amount

    def get_balance_info(self) -> dict:
        """
        Возвращает информацию о текущем балансе
        """
        return {
            "currency_code": self.currency_code,
            "balance": self.balance,
            "balance_formatted": f"{self.balance:.2f} {self.currency_code}"
        }

    def to_dict(self) -> dict:
        """
        Конвертирует объект Wallet в словарь для сохранения в JSON
        """
        return {
            "currency_code": self.currency_code,
            "balance": self.balance
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Wallet':
        """
        Создаёт объект Wallet из словаря
        """
        return cls(
            currency_code=data["currency_code"],
            balance=data["balance"]
        )

    def __repr__(self) -> str:
        """
        Строковое представление объекта
        """
        return f"Wallet(currency='{self.currency_code}', balance={self.balance:.2f})"


class Portfolio:
    """
    Класс управления всеми кошельками одного пользователя
    """
    def __init__(self, user_id: int, wallets: dict[str, Wallet] | None = None):
        """
        Инициализация портфеля
        """
        self._user_id = user_id
        self._wallets = wallets or {}

        if "USD" not in self._wallets:
            self._wallets["USD"] = Wallet("USD", 0.0)

    @property
    def user_id(self) -> int:
        """
        Геттер для идентификатора пользователя
        """
        return self._user_id

    @property
    def wallets(self) -> dict[str, Wallet]:
        """
        Геттер, который возвращает копию словаря кошельков
        """
        return self._wallets.copy()

    def add_currency(self, currency_code: str, initial_balance: float = 0.0) -> Wallet:
        """
        Добавляет новый кошелёк в портфель
        """
        currency_code = currency_code.upper()

        # Проверяем, что валюта доступна через CurrencyRegistry
        try:
            CurrencyRegistry.get_currency(currency_code)
        except CurrencyNotFoundError:
            # Получаем список доступных валют
            available_codes = CurrencyRegistry.get_all_codes()
            raise ValueError(
                f"Валюта '{currency_code}' недоступна для торговли. "
                f"Доступные валюты: {', '.join(available_codes)}"
            ) from None

        # Проверяем уникальность кода валюты
        if currency_code in self._wallets:
            raise ValueError(f"Кошелёк с валютой '{currency_code}' уже существует")

        # Создаём новый кошелёк
        wallet = Wallet(currency_code, initial_balance)
        self._wallets[currency_code] = wallet

        return wallet

    def get_wallet(self, currency_code: str) -> Wallet | None:
        """
        Возвращает объект Wallet по коду валюты
        """
        currency_code = currency_code.upper()
        return self._wallets.get(currency_code)

    def get_total_value(self, base_currency: str = "USD") -> float:
        """
        Рассчитывает общую стоимость портфеля в указанной валюте
        """
        base_currency = base_currency.upper()

        # Проверяем, что базовая валюта доступна через CurrencyRegistry
        try:
            CurrencyRegistry.get_currency(base_currency)
        except CurrencyNotFoundError:
            available_codes = CurrencyRegistry.get_all_codes()
            raise ValueError(
                f"Базовая валюта '{base_currency}' недоступна. "
                f"Доступные валюты: {', '.join(available_codes)}"
            ) from None

        total_value = 0.0

        # Импортируем здесь, чтобы избежать циклического импорта
        from valutatrade_hub.core.utils import get_exchange_rate

        for currency_code, wallet in self._wallets.items():
            if wallet.balance > 0:
                rate = get_exchange_rate(currency_code, base_currency)
                if rate:
                    value_in_base = wallet.balance * rate
                    total_value += value_in_base

        return total_value

    def to_dict(self) -> dict:
        """
        Конвертирует объект Portfolio в словарь для сохранения в JSON
        """
        wallets_dict = {}
        for currency_code, wallet in self._wallets.items():
            wallets_dict[currency_code] = wallet.to_dict()

        return {
            "user_id": self._user_id,
            "wallets": wallets_dict
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Portfolio':
        """
        Создаёт объект Portfolio из словаря
        """
        wallets = {}
        for currency_code, wallet_data in data.get("wallets", {}).items():
            wallets[currency_code] = Wallet.from_dict(wallet_data)

        return cls(
            user_id=data["user_id"],
            wallets=wallets
        )

    def __repr__(self) -> str:
        """
        Строковое представление объекта
        """
        wallet_count = len(self._wallets)
        total_usd = self.get_total_value("USD")
        return f"Portfolio(user_id={self._user_id}, wallets={wallet_count}, total_value={total_usd:.2f} USD)"
