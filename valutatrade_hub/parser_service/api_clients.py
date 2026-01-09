import requests
import time
from typing import Dict, Optional, Any
from abc import ABC, abstractmethod
from datetime import datetime

from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.decorators import retry_on_failure
from valutatrade_hub.logging_config import get_logger

logger = get_logger("parser.api")

class BaseApiClient(ABC):
    
    def __init__(self, config: ParserConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "ValutaTradeHub/1.0 (Educational Project)"
        })
    
    @abstractmethod
    def fetch_rates(self) -> Dict[str, float]:
        pass
    
    def _make_request(self, url: str, params: Optional[Dict] = None) -> Dict[str, Any]:
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
            
        except requests.exceptions.Timeout:
            raise ApiRequestError(
                f"Таймаут запроса ({self.config.REQUEST_TIMEOUT} сек)",
                service=self.__class__.__name__
            )
        except requests.exceptions.ConnectionError:
            raise ApiRequestError(
                "Ошибка соединения",
                service=self.__class__.__name__
            )
        except requests.exceptions.RequestException as e:
            raise ApiRequestError(
                f"Ошибка запроса: {str(e)}",
                service=self.__class__.__name__
            )
        except ValueError as e:
            raise ApiRequestError(
                f"Ошибка парсинга JSON: {str(e)}",
                service=self.__class__.__name__
            )


class CoinGeckoClient(BaseApiClient):
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def fetch_rates(self) -> Dict[str, float]:
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
            )


class ExchangeRateApiClient(BaseApiClient):
    
    @retry_on_failure(max_retries=2, delay=2.0)
    def fetch_rates(self) -> Dict[str, float]:
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
            base_currency = data.get("base_code", self.config.BASE_CURRENCY)
            
            all_rates = data.get("rates", {})
            
            for fiat_currency in self.config.FIAT_CURRENCIES:
                if fiat_currency in all_rates:
                    rate = all_rates[fiat_currency]
                    
                    if base_currency != self.config.BASE_CURRENCY:
                        usd_rate = all_rates.get("USD", 1.0)
                        rate = rate / usd_rate
                    
                    pair_key = f"{fiat_currency}_{self.config.BASE_CURRENCY}"
                    rates[pair_key] = float(rate)
            
            for pair, rate in list(rates.items()):
                from_curr, to_curr = pair.split("_")
                if from_curr != to_curr and rate != 0:
                    reverse_pair = f"{to_curr}_{from_curr}"
                    rates[reverse_pair] = 1.0 / rate
            
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
            )