import hashlib
from datetime import datetime
from typing import Optional
import time
from typing import Dict, Optional
from valutatrade_hub.core.utils import get_exchange_rate, get_available_currencies

class User:

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: Optional[datetime] = None
    ):
        self._user_id = user_id
        self._username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date or datetime.now()
    
    @property
    def user_id(self) -> int:
        return self._user_id
    
    @property
    def username(self) -> str:
        return self._username
    
    @username.setter
    def username(self, value: str):
        if not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value.strip()
    
    @property
    def hashed_password(self) -> str:
        return self._hashed_password
    
    @property
    def salt(self) -> str:
        return self._salt
    
    @property
    def registration_date(self) -> datetime:
        return self._registration_date
    
    def get_user_info(self) -> dict:
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
            "salt": self._salt
        }
    
    def change_password(self, new_password: str) -> None:
        if len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        
        self._hashed_password = self._hash_password(new_password, self._salt)
    
    def verify_password(self, password: str) -> bool:
        hashed_input = self._hash_password(password, self._salt)
        return hashed_input == self._hashed_password
    
    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        hasher = hashlib.sha256()
        hasher.update(f"{password}{salt}".encode('utf-8'))
        return hasher.hexdigest()
    
    @classmethod
    def create_user(cls, user_id: int, username: str, password: str) -> 'User':
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
        
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        registration_date = datetime.fromisoformat(data["registration_date"])
        
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            hashed_password=data["hashed_password"],
            salt=data["salt"],
            registration_date=registration_date
        )
    
    def __repr__(self) -> str:
        return (f"User(user_id={self._user_id}, "
                f"username='{self._username}', "
                f"registration_date={self._registration_date.strftime('%Y-%m-%d %H:%M:%S')})")


class Wallet:
    
    def __init__(self, currency_code: str, balance: float = 0.0):
        self.currency_code = currency_code
        self._balance = balance
    
    @property
    def currency_code(self) -> str:
        return self._currency_code
    
    @currency_code.setter
    def currency_code(self, value: str):
        if not value.strip():
            raise ValueError("Код валюты не может быть пустым")
        self._currency_code = value.strip().upper()
    
    @property
    def balance(self) -> float:
        return self._balance
    
    @balance.setter
    def balance(self, value: float):
        if not isinstance(value, (int, float)):
            raise TypeError(f"Баланс должен быть числом, получено {type(value).__name__}")
        
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        
        self._balance = float(value)
    
    def deposit(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Сумма пополнения должна быть положительной")
        
        self.balance += amount
        print(f"Кошелёк {self.currency_code}: пополнено {amount:.2f}. Новый баланс: {self.balance:.2f}")
    
    def withdraw(self, amount: float) -> float:
        if amount <= 0:
            raise ValueError("Сумма снятия должна быть положительной")
        
        if amount > self.balance:
            raise ValueError(f"Недостаточно средств. Доступно: {self.balance:.2f}, запрошено: {amount:.2f}")

        self.balance -= amount
        print(f"Кошелёк {self.currency_code}: снято {amount:.2f}. Новый баланс: {self.balance:.2f}")
        return amount
    
    def get_balance_info(self) -> dict:
        return {
            "currency_code": self.currency_code,
            "balance": self.balance,
            "balance_formatted": f"{self.balance:.2f} {self.currency_code}"
        }
    
    def to_dict(self) -> dict:
        return {
            "currency_code": self.currency_code,
            "balance": self.balance
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Wallet':
        return cls(
            currency_code=data["currency_code"],
            balance=data["balance"]
        )
    
    def __repr__(self) -> str:
        return f"Wallet(currency='{self.currency_code}', balance={self.balance:.2f})"


class Portfolio:
    
    def __init__(self, user_id: int, wallets: Optional[Dict[str, Wallet]] = None):
        self._user_id = user_id
        self._wallets = wallets or {}

        if "USD" not in self._wallets:
            self._wallets["USD"] = Wallet("USD", 0.0)
    
    @property
    def user_id(self) -> int:
        return self._user_id
    
    @property
    def wallets(self) -> Dict[str, Wallet]:
        return self._wallets.copy()
    
    def add_currency(self, currency_code: str, initial_balance: float = 0.0) -> Wallet:
        currency_code = currency_code.upper()
        
        # Проверяем, что валюта доступна
        if not get_exchange_rate(currency_code, "USD"):
            raise ValueError(
                f"Валюта '{currency_code}' недоступна для торговли. "
                f"Доступные валюты: {', '.join(get_available_currencies())}"
            )
        
        if currency_code in self._wallets:
            raise ValueError(f"Кошелёк с валютой '{currency_code}' уже существует")
        
        wallet = Wallet(currency_code, initial_balance)
        self._wallets[currency_code] = wallet
        
        print(f"Добавлен кошелёк {currency_code} с начальным балансом {initial_balance:.2f}")
        return wallet
    
    def get_wallet(self, currency_code: str) -> Optional[Wallet]:
        currency_code = currency_code.upper()
        return self._wallets.get(currency_code)
    
    def get_total_value(self, base_currency: str = "USD") -> float:
        base_currency = base_currency.upper()

        if not get_exchange_rate(base_currency, "USD"):
            raise ValueError(
                f"Базовая валюта '{base_currency}' недоступна. "
                f"Доступные валюты: {', '.join(get_available_currencies())}"
            )
        
        total_value = 0.0
        
        for currency_code, wallet in self._wallets.items():
            if wallet.balance > 0:
                rate = get_exchange_rate(currency_code, base_currency)
                if rate:
                    value_in_base = wallet.balance * rate
                    total_value += value_in_base
        
        return total_value
    
    def to_dict(self) -> dict:
        wallets_dict = {}
        for currency_code, wallet in self._wallets.items():
            wallets_dict[currency_code] = wallet.to_dict()
        
        return {
            "user_id": self._user_id,
            "wallets": wallets_dict
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Portfolio':
        wallets = {}
        for currency_code, wallet_data in data.get("wallets", {}).items():
            wallets[currency_code] = Wallet.from_dict(wallet_data)
        
        return cls(
            user_id=data["user_id"],
            wallets=wallets
        )
    
    def __repr__(self) -> str:
        wallet_count = len(self._wallets)
        total_usd = self.get_total_value("USD")
        return f"Portfolio(user_id={self._user_id}, wallets={wallet_count}, total_value={total_usd:.2f} USD)"