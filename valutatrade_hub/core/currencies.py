import re
from abc import ABC, abstractmethod
from pathlib import Path


class CurrencyNotFoundError(Exception):
    """
    Исключение для неизвестной валюты
    """
    def __init__(self, currency_code: str):
        self.currency_code = currency_code
        message = f"Неизвестная валюта '{currency_code}'"
        super().__init__(message)
    pass


class Currency(ABC):
    """
    Абстрактный базовый класс для валют
    """
    def __init__(self, name: str, code: str):
        """
        Инициализация валюты
        """
        self._validate_code(code)
        self._validate_name(name)

        self._name = name
        self._code = code.upper()

    @property
    def name(self) -> str:
        """
        Возвращает имя валюты
        """
        return self._name

    @property
    def code(self) -> str:
        """
        Возвращает код валюты
        """
        return self._code

    @abstractmethod
    def get_display_info(self) -> str:
        """
        Возвращает строковое представление для UI/логов
        """
        pass

    def _validate_code(self, code: str) -> None:
        """
        Валидирует код валюты
        """
        if not code or not isinstance(code, str):
            raise ValueError("Код валюты должен быть непустой строкой")

        code_upper = code.upper().strip()

        if len(code_upper) < 2 or len(code_upper) > 8:
            raise ValueError("Код валюты должен содержать от 2 до 8 символов")

        if not re.match(r'^[A-Z0-9]+$', code_upper):
            raise ValueError("Код валюты должен содержать только буквы A-Z и цифры 0-9")

    def _validate_name(self, name: str) -> None:
        """
        Валидирует имя валюты
        """
        if not name or not isinstance(name, str):
            raise ValueError("Имя валюты должно быть непустой строкой")

        if len(name.strip()) == 0:
            raise ValueError("Имя валюты не может состоять только из пробелов")

    def __repr__(self) -> str:
        """
        Строковое представление для отладки
        """
        return f"{self.__class__.__name__}(name='{self._name}', code='{self._code}')"


class FiatCurrency(Currency):
    """
    Класс для фиатных валют
    """
    def __init__(self, name: str, code: str, issuing_country: str):
        """
        Инициализация фиатной валюты
        """
        super().__init__(name, code)
        self._issuing_country = issuing_country

    @property
    def issuing_country(self) -> str:
        """
        Возвращает страну/зону эмиссии
        """
        return self._issuing_country

    def get_display_info(self) -> str:
        """
        Возвращает строковое представление для UI/логов
        """
        return f"[FIAT] {self._code} — {self._name} (Issuing: {self._issuing_country})"


class CryptoCurrency(Currency):
    """
    Класс для криптовалют
    """
    def __init__(self, name: str, code: str, algorithm: str = "Unknown", market_cap: float = 0.0):
        """
        Инициализация криптовалюты
        """
        super().__init__(name, code)
        self._algorithm = algorithm
        self._market_cap = market_cap

    @property
    def algorithm(self) -> str:
        """
        Возвращает алгоритм
        """
        return self._algorithm

    @property
    def market_cap(self) -> float:
        """
        Возвращает рыночную капитализацию
        """
        return self._market_cap

    @market_cap.setter
    def market_cap(self, value: float) -> None:
        """
        Устанавливает рыночную капитализацию
        """
        if value < 0:
            raise ValueError("Рыночная капитализация не может быть отрицательной")
        self._market_cap = value

    def get_display_info(self) -> str:
        """
        Возвращает строковое представление для UI/логов
        """
        mcap_str = f"{self._market_cap:.2e}" if self._market_cap > 0 else "N/A"
        return f"[CRYPTO] {self._code} — {self._name} (Algo: {self._algorithm}, MCAP: {mcap_str})"

class CurrencyRegistry:
    """
    Реестр доступных валют
    """
    # Кэш валют
    _currencies: dict[str, Currency] = {}
    _initialized: bool = False

    # Известные фиатные валюты (для инициализации)
    _KNOWN_FIAT: dict[str, tuple] = {
        "USD": ("US Dollar", "United States"),
        "EUR": ("Euro", "Eurozone"),
        "GBP": ("British Pound", "United Kingdom"),
        "JPY": ("Japanese Yen", "Japan"),
        "CNY": ("Chinese Yuan", "China"),
        "RUB": ("Russian Ruble", "Russia"),
        "CHF": ("Swiss Franc", "Switzerland"),
        "CAD": ("Canadian Dollar", "Canada"),
        "AUD": ("Australian Dollar", "Australia"),
        "NZD": ("New Zealand Dollar", "New Zealand"),
    }

    # Известные криптовалюты (для инициализации)
    _KNOWN_CRYPTO: dict[str, tuple] = {
        "BTC": ("Bitcoin", "SHA-256"),
        "ETH": ("Ethereum", "Ethash"),
        "SOL": ("Solana", "Proof of History"),
        "BNB": ("Binance Coin", "BEP-2/BEP-20"),
        "XRP": ("Ripple", "RPCA"),
        "ADA": ("Cardano", "Ouroboros"),
        "DOGE": ("Dogecoin", "Scrypt"),
        "DOT": ("Polkadot", "Nominated Proof-of-Stake"),
        "MATIC": ("Polygon", "Plasma"),
        "AVAX": ("Avalanche", "Snowman"),
    }

    @classmethod
    def _initialize(cls) -> None:
        """Инициализирует реестр базовым набором валют."""
        if cls._initialized:
            return

        # Добавляем известные фиатные валюты
        for code, (name, country) in cls._KNOWN_FIAT.items():
            cls._currencies[code] = FiatCurrency(name, code, country)

        # Добавляем известные криптовалюты
        for code, (name, algorithm) in cls._KNOWN_CRYPTO.items():
            cls._currencies[code] = CryptoCurrency(name, code, algorithm)

        cls._initialized = True

    @classmethod
    def get_currency(cls, code: str) -> Currency:
        """
        Возвращает валюту по коду.
        """
        code_upper = code.upper()
        cls._initialize()

        # Если валюта уже в реестре, возвращаем её
        if code_upper in cls._currencies:
            return cls._currencies[code_upper]

        # Пытаемся определить тип валюты и создать её динамически
        try:
            # Проверяем, есть ли эта валюта в кэше курсов
            from valutatrade_hub.core.utils import get_exchange_rate
            rate = get_exchange_rate(code_upper, "USD")

            if rate is not None:
                # Валюта есть в кэше курсов, создаём её динамически
                if len(code_upper) == 3 and code_upper.isalpha():
                    # Скорее всего фиатная валюта (3 буквы)
                    currency = FiatCurrency(
                        name=f"Currency {code_upper}",  # Временное имя
                        code=code_upper,
                        issuing_country="Unknown"
                    )
                else:
                    # Скорее всего криптовалюта
                    currency = CryptoCurrency(
                        name=f"Crypto {code_upper}",  # Временное имя
                        code=code_upper,
                        algorithm="Unknown",
                        market_cap=0.0
                    )

                # Сохраняем в реестр
                cls._currencies[code_upper] = currency
                return currency

        except ImportError:
            pass

        # Если не смогли создать динамически, пробуем загрузить из конфигурации Parser Service
        try:
            from valutatrade_hub.parser_service.config import ParserConfig
            config = ParserConfig()

            # Проверяем фиатные валюты
            if code_upper in config.FIAT_CURRENCIES:
                currency = FiatCurrency(
                    name=f"Currency {code_upper}",
                    code=code_upper,
                    issuing_country="Unknown"
                )
                cls._currencies[code_upper] = currency
                return currency

            # Проверяем криптовалюты
            if code_upper in config.CRYPTO_CURRENCIES:
                currency = CryptoCurrency(
                    name=f"Crypto {code_upper}",
                    code=code_upper,
                    algorithm="Unknown",
                    market_cap=0.0
                )
                cls._currencies[code_upper] = currency
                return currency

        except ImportError:
            pass

        # Если всё ещё не нашли, создаём как Unknown валюту, чтобы не падать при обработке портфелей
        currency = Currency(
            name=f"Unknown Currency {code_upper}",
            code=code_upper
        )
        cls._currencies[code_upper] = currency
        return currency

    @classmethod
    def get_all_currencies(cls) -> dict[str, Currency]:
        """
        Возвращает все доступные валюты.
        Загружает дополнительные валюты из кэша курсов.
        """
        cls._initialize()

        # Загружаем дополнительные валюты из кэша курсов
        try:
            from valutatrade_hub.core.utils import get_cache_info
            cache_info = get_cache_info()

            if cache_info["rates_count"] > 0:
                # Загружаем курсы из файла
                import json

                from valutatrade_hub.infra.settings import SettingsLoader

                settings = SettingsLoader()
                rates_file = settings.get_data_file_path("rates.json")

                if Path(rates_file).exists():
                    with open(rates_file, encoding='utf-8') as f:
                        data = json.load(f)

                    # Добавляем валюты из кэша
                    if "pairs" in data:
                        for pair in data["pairs"].keys():
                            # Парсим пару типа "BTC_USD"
                            if "_" in pair:
                                from_curr, to_curr = pair.split("_", 1)

                                # Добавляем обе валюты
                                for code in [from_curr, to_curr]:
                                    if code not in cls._currencies:
                                        try:
                                            cls.get_currency(code)  # Автоматически создаст
                                        except Exception:
                                            pass

        except (ImportError, FileNotFoundError, json.JSONDecodeError, KeyError):
            pass

        return cls._currencies.copy()

    @classmethod
    def get_all_codes(cls) -> list:
        """
        Возвращает список всех доступных кодов валют
        """
        return list(cls._currencies.keys())

    @classmethod
    def register_currency(cls, currency: Currency) -> None:
        """
        Регистрирует новую валюту в реестре
        """
        cls._initialize()
        cls._currencies[currency.code] = currency

    @classmethod
    def is_fiat(cls, code: str) -> bool:
        """
        Проверяет, является ли валюта фиатной
        """
        try:
            currency = cls.get_currency(code)
            return isinstance(currency, FiatCurrency)
        except CurrencyNotFoundError:
            return False

    @classmethod
    def is_crypto(cls, code: str) -> bool:
        """
        Проверяет, является ли валюта криптовалютой
        """
        try:
            currency = cls.get_currency(code)
            return isinstance(currency, CryptoCurrency)
        except CurrencyNotFoundError:
            return False
    @classmethod
    def update_from_cache(cls) -> None:
        """Обновляет реестр из кэша курсов."""
        # Очищаем кэш (кроме базовых валют)
        cls._initialize()  # Сначала инициализируем базовый набор

        try:
            # Загружаем курсы из файла
            import json

            from valutatrade_hub.infra.settings import SettingsLoader

            settings = SettingsLoader()
            rates_file = settings.get_data_file_path("rates.json")

            if Path(rates_file).exists():
                with open(rates_file, encoding='utf-8') as f:
                    data = json.load(f)

                # Добавляем валюты из кэша
                if "pairs" in data:
                    for pair in data["pairs"].keys():
                        if "_" in pair:
                            from_curr, to_curr = pair.split("_", 1)

                            # Добавляем обе валюты
                            for code in [from_curr, to_curr]:
                                if code not in cls._currencies:
                                    # Пытаемся определить тип валюты
                                    if len(code) == 3 and code.isalpha():
                                        # Фиатная валюта
                                        cls._currencies[code] = FiatCurrency(
                                            name=f"Currency {code}",
                                            code=code,
                                            issuing_country="Unknown"
                                        )
                                    else:
                                        # Криптовалюта
                                        cls._currencies[code] = CryptoCurrency(
                                            name=f"Crypto {code}",
                                            code=code,
                                            algorithm="Unknown",
                                            market_cap=0.0
                                        )

        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass
