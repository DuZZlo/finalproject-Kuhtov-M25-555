import re
from abc import ABC, abstractmethod


class CurrencyNotFoundError(Exception):
    pass


class Currency(ABC):

    def __init__(self, name: str, code: str):
        self._validate_code(code)
        self._validate_name(name)

        self._name = name
        self._code = code.upper()

    @property
    def name(self) -> str:
        return self._name

    @property
    def code(self) -> str:
        return self._code

    @abstractmethod
    def get_display_info(self) -> str:
        pass

    def _validate_code(self, code: str) -> None:
        if not code or not isinstance(code, str):
            raise ValueError("Код валюты должен быть непустой строкой")

        code_upper = code.upper().strip()

        if len(code_upper) < 2 or len(code_upper) > 5:
            raise ValueError("Код валюты должен содержать от 2 до 5 символов")

        if not re.match(r'^[A-Z]+$', code_upper):
            raise ValueError("Код валюты должен содержать только буквы A-Z")

    def _validate_name(self, name: str) -> None:
        if not name or not isinstance(name, str):
            raise ValueError("Имя валюты должно быть непустой строкой")

        if len(name.strip()) == 0:
            raise ValueError("Имя валюты не может состоять только из пробелов")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self._name}', code='{self._code}')"


class FiatCurrency(Currency):

    def __init__(self, name: str, code: str, issuing_country: str):
        super().__init__(name, code)
        self._issuing_country = issuing_country

    @property
    def issuing_country(self) -> str:
        """Возвращает страну/зону эмиссии."""
        return self._issuing_country

    def get_display_info(self) -> str:
        return f"[FIAT] {self._code} — {self._name} (Issuing: {self._issuing_country})"


class CryptoCurrency(Currency):

    def __init__(self, name: str, code: str, algorithm: str, market_cap: float = 0.0):
        super().__init__(name, code)
        self._algorithm = algorithm
        self._market_cap = market_cap

    @property
    def algorithm(self) -> str:
        return self._algorithm

    @property
    def market_cap(self) -> float:
        return self._market_cap

    @market_cap.setter
    def market_cap(self, value: float) -> None:
        if value < 0:
            raise ValueError("Рыночная капитализация не может быть отрицательной")
        self._market_cap = value

    def get_display_info(self) -> str:
        mcap_str = f"{self._market_cap:.2e}" if self._market_cap > 0 else "N/A"
        return f"[CRYPTO] {self._code} — {self._name} (Algo: {self._algorithm}, MCAP: {mcap_str})"

class CurrencyRegistry:

    _currencies: dict[str, Currency] = {
        "USD": FiatCurrency("US Dollar", "USD", "United States"),
        "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
        "GBP": FiatCurrency("British Pound", "GBP", "United Kingdom"),
        "JPY": FiatCurrency("Japanese Yen", "JPY", "Japan"),
        "CNY": FiatCurrency("Chinese Yuan", "CNY", "China"),
        "RUB": FiatCurrency("Russian Ruble", "RUB", "Russia"),

        "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", market_cap=1.12e12),
        "ETH": CryptoCurrency("Ethereum", "ETH", "Ethash", market_cap=4.5e11),
        "USDT": CryptoCurrency("Tether", "USDT", "Omni/Ethereum", market_cap=1.1e11),
        "BNB": CryptoCurrency("Binance Coin", "BNB", "BEP-2/BEP-20", market_cap=8.5e10),
        "XRP": CryptoCurrency("Ripple", "XRP", "RPCA", market_cap=3.8e10),
    }

    @classmethod
    def get_currency(cls, code: str) -> Currency:
        code_upper = code.upper()

        if code_upper not in cls._currencies:
            raise CurrencyNotFoundError(f"Неизвестная валюта '{code}'")

        return cls._currencies[code_upper]

    @classmethod
    def get_all_currencies(cls) -> dict[str, Currency]:
        return cls._currencies.copy()

    @classmethod
    def get_all_codes(cls) -> list:
        return list(cls._currencies.keys())

    @classmethod
    def register_currency(cls, currency: Currency) -> None:
        cls._currencies[currency.code] = currency

    @classmethod
    def is_fiat(cls, code: str) -> bool:
        try:
            currency = cls.get_currency(code)
            return isinstance(currency, FiatCurrency)
        except CurrencyNotFoundError:
            return False

    @classmethod
    def is_crypto(cls, code: str) -> bool:
        try:
            currency = cls.get_currency(code)
            return isinstance(currency, CryptoCurrency)
        except CurrencyNotFoundError:
            return False
