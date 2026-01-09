import json
import os
from datetime import datetime
from typing import Any

from valutatrade_hub.logging_config import get_logger
from valutatrade_hub.parser_service.config import ParserConfig

logger = get_logger("parser.storage")


class RatesStorage:
    """
    Класс для работы с хранилищем курсов валют
    """
    def __init__(self, config: ParserConfig):
        """
        Инициализация хранилища
        """
        self.config = config
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """
        Создает необходимые директории, если их нет
        """
        os.makedirs(os.path.dirname(self.config.RATES_FILE_PATH), exist_ok=True)
        os.makedirs(os.path.dirname(self.config.HISTORY_FILE_PATH), exist_ok=True)

    def save_current_rates(self, rates: dict[str, float],
                          source: str,
                          metadata: dict | None = None) -> bool:
        """
        Сохраняет текущие курсы в rates.json
        """
        try:
            current_time = datetime.now().isoformat()

            rates_data = {
                "last_refresh": current_time,
                "source": source,
                "pairs": {}
            }

            for pair, rate in rates.items():
                rates_data["pairs"][pair] = {
                    "rate": rate,
                    "updated_at": current_time,
                    "source": source
                }

            if metadata:
                rates_data["metadata"] = metadata

            temp_file = f"{self.config.RATES_FILE_PATH}.tmp"

            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(rates_data, f, indent=2, ensure_ascii=False, default=str)

            os.replace(temp_file, self.config.RATES_FILE_PATH)

            logger.info(f"Сохранено {len(rates)} курсов в {self.config.RATES_FILE_PATH}")
            return True

        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"Ошибка при сохранении текущих курсов: {e}")
            return False

    def save_to_history(self, rates: dict[str, float],
                       source: str,
                       request_metadata: dict | None = None) -> bool:
        """
        Сохраняет курсы в историческое хранилище
        """
        try:
            current_time = datetime.now()
            timestamp = current_time.isoformat()

            history = self._load_history()

            for pair, rate in rates.items():
                from_currency, to_currency = pair.split("_")

                history_entry = {
                    "id": f"{pair}_{current_time.strftime('%Y%m%d_%H%M%S')}",
                    "from_currency": from_currency,
                    "to_currency": to_currency,
                    "rate": rate,
                    "timestamp": timestamp,
                    "source": source,
                    "meta": request_metadata or {}
                }

                history.append(history_entry)

            if len(history) > 1000:
                history = history[-1000:]

            temp_file = f"{self.config.HISTORY_FILE_PATH}.tmp"

            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False, default=str)

            os.replace(temp_file, self.config.HISTORY_FILE_PATH)

            logger.info(f"Добавлено {len(rates)} записей в историю")
            return True

        except (OSError, json.JSONDecodeError, ValueError) as e:
            logger.error(f"Ошибка при сохранении в историю: {e}")
            return False

    def _load_history(self) -> list[dict[str, Any]]:
        """
        Загружает исторические данные
        """
        try:
            if os.path.exists(self.config.HISTORY_FILE_PATH):
                with open(self.config.HISTORY_FILE_PATH, encoding='utf-8') as f:
                    return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Не удалось загрузить историю: {e}")

        return []

    def load_current_rates(self) -> dict[str, Any] | None:
        """
        Загружает текущие курсы из кеша
        """
        try:
            if os.path.exists(self.config.RATES_FILE_PATH):
                with open(self.config.RATES_FILE_PATH, encoding='utf-8') as f:
                    return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Не удалось загрузить текущие курсы: {e}")

        return None

    def is_cache_valid(self) -> bool:
        """
        Проверяет, является ли кеш актуальным
        """
        data = self.load_current_rates()

        if not data or "last_refresh" not in data:
            return False

        try:
            last_refresh = datetime.fromisoformat(data["last_refresh"])
            cache_age = datetime.now() - last_refresh

            # Кеш считается актуальным, если возраст меньше TTL
            return cache_age.total_seconds() < (self.config.CACHE_TTL_MINUTES * 60)

        except (ValueError, TypeError):
            return False

    def clear_cache(self) -> bool:
        """
        Очищает кеш курсов
        """
        try:
            if os.path.exists(self.config.RATES_FILE_PATH):
                os.remove(self.config.RATES_FILE_PATH)
                logger.info("Кеш курсов очищен")
                return True
            return False
        except OSError as e:
            logger.error(f"Ошибка при очистке кеша: {e}")
            return False

    def get_rate(self, from_currency: str, to_currency: str) -> float | None:
        """
        Получает курс из кеша
        """
        data = self.load_current_rates()

        if not data or "pairs" not in data:
            return None

        pair = f"{from_currency}_{to_currency}"
        reverse_pair = f"{to_currency}_{from_currency}"

        if pair in data["pairs"]:
            return data["pairs"][pair]["rate"]

        if reverse_pair in data["pairs"]:
            rate = data["pairs"][reverse_pair]["rate"]
            if rate != 0:
                return 1.0 / rate

        return None
