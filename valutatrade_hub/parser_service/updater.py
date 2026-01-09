import time
from datetime import datetime

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.logging_config import get_logger
from valutatrade_hub.parser_service.api_clients import CoinGeckoClient, ExchangeRateApiClient
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage

logger = get_logger("parser.updater")


class RatesUpdater:

    def __init__(self, config: ParserConfig | None = None):
        self.config = config or ParserConfig()
        self.storage = RatesStorage(self.config)

        self.clients = {
            "coingecko": CoinGeckoClient(self.config),
            "exchangerate": ExchangeRateApiClient(self.config)
        }

        logger.info(f"Инициализирован RatesUpdater для {len(self.config.CRYPTO_CURRENCIES)} "
                   f"крипто и {len(self.config.FIAT_CURRENCIES)} фиатных валют")

    def update_rates(self, source: str | None = None) -> dict[str, dict]:
        logger.info("Начало обновления курсов" + (f" из источника: {source}" if source else ""))

        start_time = time.time()
        results = {
            "total_rates": 0,
            "sources": {},
            "errors": [],
            "timestamp": datetime.now().isoformat()
        }

        all_rates = {}

        clients_to_use = {}
        if source:
            if source in self.clients:
                clients_to_use[source] = self.clients[source]
            else:
                raise ValueError(f"Неизвестный источник: {source}. Доступные: {list(self.clients.keys())}")
        else:
            clients_to_use = self.clients.copy()

        for client_name, client in clients_to_use.items():
            try:
                logger.info(f"Получение курсов от {client_name}...")
                client_start_time = time.time()

                rates = client.fetch_rates()
                client_time = time.time() - client_start_time

                all_rates.update(rates)

                results["sources"][client_name] = {
                    "rates_count": len(rates),
                    "time_seconds": round(client_time, 2),
                    "status": "success"
                }

                logger.info(f"Успешно получено {len(rates)} курсов от {client_name} "
                          f"за {client_time:.2f} сек")

            except ApiRequestError as e:
                error_msg = f"Ошибка при получении курсов от {client_name}: {e}"
                logger.error(error_msg)

                results["sources"][client_name] = {
                    "rates_count": 0,
                    "status": "error",
                    "error": str(e)
                }
                results["errors"].append(error_msg)

            except Exception as e:
                error_msg = f"Неожиданная ошибка от {client_name}: {e}"
                logger.error(error_msg, exc_info=True)

                results["sources"][client_name] = {
                    "rates_count": 0,
                    "status": "error",
                    "error": str(e)
                }
                results["errors"].append(error_msg)

        if all_rates:
            try:
                self.storage.save_current_rates(
                    rates=all_rates,
                    source="ParserService",
                    metadata={
                        "sources": list(clients_to_use.keys()),
                        "request_count": len(clients_to_use)
                    }
                )

                self.storage.save_to_history(
                    rates=all_rates,
                    source="ParserService",
                    request_metadata={
                        "clients": list(clients_to_use.keys()),
                        "total_time": round(time.time() - start_time, 2)
                    }
                )

                results["total_rates"] = len(all_rates)
                results["status"] = "success"
                logger.info(f"Успешно обновлено {len(all_rates)} курсов "
                          f"за {time.time() - start_time:.2f} сек")

            except Exception as e:
                error_msg = f"Ошибка при сохранении курсов: {e}"
                logger.error(error_msg, exc_info=True)

                results["status"] = "error"
                results["errors"].append(error_msg)
        else:
            error_msg = "Не удалось получить ни одного курса"
            logger.error(error_msg)

            results["status"] = "error"
            results["errors"].append(error_msg)

        results["total_time"] = round(time.time() - start_time, 2)
        return results

    def get_update_summary(self, results: dict) -> str:
        if results["status"] == "error" and not results.get("total_rates", 0):
            return "Обновление не удалось. Не получено ни одного курса."

        summary_lines = []

        if results["status"] == "success":
            summary_lines.append("Обновление успешно завершено")
        else:
            summary_lines.append("Обновление завершено с ошибками")

        summary_lines.append(f"Всего курсов: {results['total_rates']}")
        summary_lines.append(f"Общее время: {results['total_time']} сек")

        for source, info in results.get("sources", {}).items():
            status = "+" if info.get("status") == "success" else "-"
            rates_count = info.get("rates_count", 0)
            time_sec = info.get("time_seconds", 0)

            if info.get("status") == "success":
                summary_lines.append(f"  {status} {source}: {rates_count} курсов за {time_sec} сек")
            else:
                error = info.get("error", "Неизвестная ошибка")
                summary_lines.append(f"  {status} {source}: ОШИБКА - {error}")

        if results.get("errors"):
            summary_lines.append("\nОшибки:")
            for i, error in enumerate(results["errors"], 1):
                summary_lines.append(f"  {i}. {error}")

        return "\n".join(summary_lines)

    def check_rates_available(self) -> dict[str, bool]:
        data = self.storage.load_current_rates()

        if not data:
            return {
                "available": False,
                "message": "Кеш курсов пуст",
                "last_refresh": None,
                "rates_count": 0
            }

        is_valid = self.storage.is_cache_valid()
        last_refresh = data.get("last_refresh")
        rates_count = len(data.get("pairs", {}))

        return {
            "available": is_valid,
            "message": "Кеш актуален" if is_valid else "Кеш устарел",
            "last_refresh": last_refresh,
            "rates_count": rates_count
        }
