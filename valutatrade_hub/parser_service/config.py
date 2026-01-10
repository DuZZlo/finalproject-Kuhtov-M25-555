import os
from dataclasses import dataclass, field


@dataclass
class ParserConfig:
    """
    Конфигурация для Parser Service
    """
    EXCHANGERATE_API_KEY: str = "94274108c3fc10ee4505560e"

    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    BASE_CURRENCY: str = "USD"

    FIAT_CURRENCIES: tuple[str, ...] = ("EUR", "GBP", "JPY", "CNY", "RUB", "CHF", "CAD", "AUD", "NZD")
    CRYPTO_CURRENCIES: tuple[str, ...] = ("BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "DOT", "AVAX")

    CRYPTO_ID_MAP: dict[str, str] = field(default_factory=lambda: {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "BNB": "binancecoin",
        "XRP": "ripple",
        "ADA": "cardano",
        "DOGE": "dogecoin",
        "DOT": "polkadot",
        "AVAX": "avalanche-2",
    })

    RATES_FILE_PATH: str = "data/rates.json"
    HISTORY_FILE_PATH: str = "data/exchange_rates.json"

    REQUEST_TIMEOUT: int = 10
    RETRY_ATTEMPTS: int = 3
    RETRY_DELAY: float = 1.0

    UPDATE_INTERVAL_MINUTES: int = 5
    CACHE_TTL_MINUTES: int = 10

    COINGECKO_RATE_LIMIT: int = 50  # запросов в минуту
    EXCHANGERATE_RATE_LIMIT: int = 1500  # запросов в день

    def __post_init__(self):
        """
        Дополнительная валидация после инициализации
        """
        env_key = os.getenv("EXCHANGERATE_API_KEY")
        if env_key:
            self.EXCHANGERATE_API_KEY = env_key

        for crypto in self.CRYPTO_CURRENCIES:
            if crypto not in self.CRYPTO_ID_MAP:
                raise ValueError(f"Не найден ID для криптовалюты {crypto} в CRYPTO_ID_MAP")

    @property
    def coingecko_request_url(self) -> str:
        """
        Возвращает URL для запроса к CoinGecko
        """
        ids = [self.CRYPTO_ID_MAP[crypto] for crypto in self.CRYPTO_CURRENCIES]
        vs_currencies = self.BASE_CURRENCY.lower()

        return f"{self.COINGECKO_URL}?ids={','.join(ids)}&vs_currencies={vs_currencies}"

    @property
    def exchangerate_request_url(self) -> str:
        """
        Возвращает URL для запроса к ExchangeRate-API
        """
        return f"{self.EXCHANGERATE_API_URL}/{self.EXCHANGERATE_API_KEY}/latest/{self.BASE_CURRENCY}"

    def get_crypto_id(self, crypto_code: str) -> str:
        """
        Возвращает ID криптовалюты для CoinGecko
        """
        if crypto_code not in self.CRYPTO_ID_MAP:
            raise ValueError(f"Неизвестная криптовалюта: {crypto_code}")
        return self.CRYPTO_ID_MAP[crypto_code]

    def get_all_currency_pairs(self) -> dict[str, str]:
        """
        Возвращает все отслеживаемые валютные пары
        """
        pairs = {}

        # Криптовалюты к USD
        for crypto in self.CRYPTO_CURRENCIES:
            pair = f"{crypto}_{self.BASE_CURRENCY}"
            pairs[pair] = f"Криптовалюта {crypto} к {self.BASE_CURRENCY}"

        # Фиатные валюты к USD
        for fiat in self.FIAT_CURRENCIES:
            if fiat != self.BASE_CURRENCY:
                pair = f"{fiat}_{self.BASE_CURRENCY}"
                pairs[pair] = f"Фиатная валюта {fiat} к {self.BASE_CURRENCY}"

        return pairs
