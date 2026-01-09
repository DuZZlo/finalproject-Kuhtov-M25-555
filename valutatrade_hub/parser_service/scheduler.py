import threading
import time
from datetime import datetime

from valutatrade_hub.logging_config import get_logger
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.updater import RatesUpdater

logger = get_logger("parser.scheduler")


class RatesScheduler:
    """
    Планировщик периодического обновления курсов
    """
    def __init__(self, config: ParserConfig | None = None):
        """
        Инициализация планировщика
        """
        self.config = config or ParserConfig()
        self.updater = RatesUpdater(self.config)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._update_count = 0
        self._error_count = 0

    def start(self, run_immediately: bool = True) -> None:
        """
        Запускает планировщик в фоновом потоке
        """
        if self._thread and self._thread.is_alive():
            logger.warning("Планировщик уже запущен")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._scheduler_loop,
            name="RatesScheduler",
            daemon=True
        )

        logger.info(f"Запуск планировщика с интервалом {self.config.UPDATE_INTERVAL_MINUTES} мин")
        self._thread.start()

        if run_immediately:
            initial_thread = threading.Thread(
                target=self._run_single_update,
                name="InitialUpdate",
                daemon=True
            )
            initial_thread.start()

    def stop(self) -> None:
        """
        Останавливает планировщик
        """
        if self._thread and self._thread.is_alive():
            logger.info("Остановка планировщика...")
            self._stop_event.set()
            self._thread.join(timeout=5)
            logger.info("Планировщик остановлен")

    def _scheduler_loop(self) -> None:
        """
        Основной цикл планировщика
        """
        logger.info("Цикл планировщика запущен")

        while not self._stop_event.is_set():
            try:
                wait_time = self.config.UPDATE_INTERVAL_MINUTES * 60
                logger.debug(f"Ожидание {wait_time} сек до следующего обновления...")

                for _ in range(wait_time):
                    if self._stop_event.is_set():
                        break
                    time.sleep(1)

                if not self._stop_event.is_set():
                    self._run_single_update()

            except Exception as e:
                logger.error(f"Ошибка в цикле планировщика: {e}", exc_info=True)
                time.sleep(60)  # Ждем минуту при ошибке

    def _run_single_update(self) -> None:
        """
        Выполняет единичное обновление курсов
        """
        try:
            logger.info(f"Запланированное обновление #{self._update_count + 1}")

            results = self.updater.update_rates()
            self._update_count += 1

            if results["status"] == "error":
                self._error_count += 1
                logger.error(f"Обновление #{self._update_count} завершилось с ошибками")
            else:
                logger.info(f"Обновление #{self._update_count} успешно завершено")

        except Exception as e:
            self._error_count += 1
            logger.error(f"Неожиданная ошибка при обновлении: {e}", exc_info=True)

    def run_once(self) -> dict:
        """
        Выполняет однократное обновление
        """
        return self.updater.update_rates()

    def get_stats(self) -> dict:
        """
        Возвращает статистику работы планировщика
        """
        return {
            "started": self._thread is not None and self._thread.is_alive(),
            "update_count": self._update_count,
            "error_count": self._error_count,
            "success_rate": (self._update_count - self._error_count) / max(self._update_count, 1),
            "last_update": datetime.now().isoformat() if self._update_count > 0 else None,
            "interval_minutes": self.config.UPDATE_INTERVAL_MINUTES
        }
