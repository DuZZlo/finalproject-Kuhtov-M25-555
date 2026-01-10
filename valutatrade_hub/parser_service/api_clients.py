import time
from abc import ABC, abstractmethod
from typing import Any

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.decorators import retry_on_failure
from valutatrade_hub.logging_config import get_logger
from valutatrade_hub.parser_service.config import ParserConfig

logger = get_logger("parser.api")

class BaseApiClient(ABC):
    """
    Базовый класс для API клиентов
    """
    def __init__(self, config: ParserConfig):
        """
        Инициализация клиента
        """
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "ValutaTradeHub/1.0 (Educational Project)"
        })

    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        """
        Получает курсы валют от API
        """
        pass

    def _make_request(self, url: str, params: dict | None = None) -> dict[str, Any]:
        """
        Выполняет HTTP запрос с обработкой ошибок
        """
        try:
            logger.debug(f"Выполнение запроса к {url}")
            start_time = time.time()

            response = self.session.get(
                url,
                params=params,
                timeout=self.config.REQUEST_TIMEOUT
            )

            response_time = time.time() - start_time
            logger.debug(f"Ответ получен за {response_time:.2f} сек, статус: {response.status_code}")

            if response.status_code != 200:
                raise ApiRequestError(
                    f"HTTP {response.status_code}: {response.reason}",
                    service=self.__class__.__name__
                )

            return response.json()

        except requests.exceptions.Timeout as e:
            # Исправлено: добавлено from e
            raise ApiRequestError(
                f"Таймаут запроса ({self.config.REQUEST_TIMEOUT} сек)",
                service=self.__class__.__name__
            ) from e
        except requests.exceptions.ConnectionError as e:
            # Исправлено: добавлено from e
            raise ApiRequestError(
                "Ошибка соединения",
                service=self.__class__.__name__
            ) from e
        except requests.exceptions.RequestException as e:
            # Исправлено: добавлено from e
            raise ApiRequestError(
                f"Ошибка запроса: {str(e)}",
                service=self.__class__.__name__
            ) from e
        except ValueError as e:
            # Исправлено: добавлено from e
            raise ApiRequestError(
                f"Ошибка парсинга JSON: {str(e)}",
                service=self.__class__.__name__
            ) from e


class CoinGeckoClient(BaseApiClient):
    """
    Клиент для работы с CoinGecko API
    """
    @retry_on_failure(max_retries=3, delay=1.0)
    def fetch_rates(self) -> dict[str, float]:
        """
        Получает курсы криптовалют от CoinGecko
        """
        logger.info("Запрос курсов криптовалют от CoinGecko...")

        url = self.config.coingecko_request_url

        try:
            data = self._make_request(url)

            rates = {}
            base_currency = self.config.BASE_CURRENCY

            for crypto_code in self.config.CRYPTO_CURRENCIES:
                crypto_id = self.config.get_crypto_id(crypto_code)

                if crypto_id in data:
                    if base_currency.lower() in data[crypto_id]:
                        rate = data[crypto_id][base_currency.lower()]
                        pair_key = f"{crypto_code}_{base_currency}"
                        rates[pair_key] = float(rate)
                    else:
                        logger.warning(f"Курс {base_currency} для {crypto_code} не найден в ответе")
                else:
                    logger.warning(f"Криптовалюта {crypto_code} (ID: {crypto_id}) не найдена в ответе")

            if not rates:
                raise ApiRequestError(
                    "Не удалось получить ни одного курса криптовалют",
                    service="CoinGecko"
                )

            logger.info(f"Получено {len(rates)} курсов криптовалют от CoinGecko")
            return rates

        except ApiRequestError:
            raise
        except Exception as e:
            raise ApiRequestError(
                f"Неожиданная ошибка при обработке ответа CoinGecko: {str(e)}",
                service="CoinGecko"
            ) from e


class ExchangeRateApiClient(BaseApiClient):
    """
    Клиент для работы с ExchangeRate-API
    """
    @retry_on_failure(max_retries=2, delay=2.0)
    def fetch_rates(self) -> dict[str, float]:
        """
        Получает курсы фиатных валют от ExchangeRate-API.
        """
        logger.info("Запрос курсов фиатных валют от ExchangeRate-API...")

        url = self.config.exchangerate_request_url

        try:
            data = self._make_request(url)

            if data.get("result") != "success":
                error_type = data.get("error-type", "unknown")
                raise ApiRequestError(
                    f"API вернуло ошибку: {error_type}",
                    service="ExchangeRate-API"
                )

            rates = {}

            # API возвращает conversion_rates
            all_rates = data.get("conversion_rates", {})
            # Или rates
            if not all_rates:
                all_rates = data.get("rates", {})

            for fiat_currency in self.config.FIAT_CURRENCIES:
                if fiat_currency in all_rates:
                    rate_from_usd = all_rates[fiat_currency]

                    if rate_from_usd != 0:
                        rate_to_usd = 1.0 / rate_from_usd

                        pair_key = f"{fiat_currency}_USD"
                        rates[pair_key] = float(rate_to_usd)

                        reverse_pair = f"USD_{fiat_currency}"
                        rates[reverse_pair] = float(rate_from_usd)

            rates["USD_USD"] = 1.0

            if not rates:
                raise ApiRequestError(
                    "Не удалось получить ни одного курса фиатных валют",
                    service="ExchangeRate-API"
                )

            logger.info(f"Получено {len(rates)} курсов фиатных валют от ExchangeRate-API")
            return rates

        except ApiRequestError:
            raise
        except Exception as e:
            raise ApiRequestError(
                f"Неожиданная ошибка при обработке ответа ExchangeRate-API: {str(e)}",
                service="ExchangeRate-API"
            ) from e
