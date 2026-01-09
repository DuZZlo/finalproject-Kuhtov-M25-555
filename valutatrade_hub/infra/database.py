import json
import os
import threading
from datetime import datetime
from typing import Any, TypeVar

from valutatrade_hub.infra.settings import SettingsLoader

T = TypeVar('T')


class DatabaseManager(metaclass=type(SettingsLoader)):

    def __init__(self):
        self._settings = SettingsLoader()
        self._lock = threading.Lock()
        self._cache: dict[str, Any] = {}
        self._cache_timestamps: dict[str, float] = {}

        self._ensure_directories()

    def _ensure_directories(self) -> None:
        data_dir = self._settings.data_dir
        logs_dir = self._settings.logs_dir

        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(logs_dir, exist_ok=True)

    def _get_file_path(self, collection: str) -> str:
        filename = f"{collection}.json"
        return self._settings.get_data_file_path(filename)

    def _read_file(self, file_path: str) -> Any:
        cache_key = file_path

        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            if os.path.exists(file_path):
                with open(file_path, encoding='utf-8') as f:
                    data = json.load(f)

                self._cache[cache_key] = data
                self._cache_timestamps[cache_key] = os.path.getmtime(file_path)
                return data
        except (OSError, json.JSONDecodeError) as e:
            print(f"Warning: Could not read {file_path}: {e}")

        if "users" in file_path:
            default_data = []
        elif "portfolios" in file_path:
            default_data = []
        elif "rates" in file_path:
            default_data = {
                "source": "stub",
                "last_refresh": datetime.now().isoformat()
            }
        else:
            default_data = {}

        self._cache[cache_key] = default_data
        self._cache_timestamps[cache_key] = 0

        return default_data

    def _write_file(self, file_path: str, data: Any) -> bool:
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)

            self._cache[file_path] = data
            self._cache_timestamps[file_path] = os.path.getmtime(file_path)

            return True
        except (OSError, TypeError) as e:
            print(f"Error: Could not write to {file_path}: {e}")
            return False

    def read_collection(self, collection: str) -> Any:
        with self._lock:
            file_path = self._get_file_path(collection)
            return self._read_file(file_path)

    def write_collection(self, collection: str, data: Any) -> bool:
        with self._lock:
            file_path = self._get_file_path(collection)
            return self._write_file(file_path, data)

    def find_one(self, collection: str, condition: dict[str, Any]) -> dict[str, Any] | None:
        data = self.read_collection(collection)

        if isinstance(data, list):
            for item in data:
                if all(item.get(key) == value for key, value in condition.items()):
                    return item

        return None

    def find_all(self, collection: str, condition: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        data = self.read_collection(collection)
        results = []

        if isinstance(data, list):
            for item in data:
                if condition is None or all(item.get(key) == value for key, value in condition.items()):
                    results.append(item)

        return results

    def insert_one(self, collection: str, item: dict[str, Any]) -> bool:
        data = self.read_collection(collection)

        if isinstance(data, list):
            data.append(item)
            return self.write_collection(collection, data)

        return False

    def update_one(self, collection: str, condition: dict[str, Any], update: dict[str, Any]) -> bool:
        data = self.read_collection(collection)

        if not isinstance(data, list):
            return False

        for i, item in enumerate(data):
            if all(item.get(key) == value for key, value in condition.items()):
                data[i].update(update)
                return self.write_collection(collection, data)

        return False

    def delete_one(self, collection: str, condition: dict[str, Any]) -> bool:
        data = self.read_collection(collection)

        if not isinstance(data, list):
            return False

        for i, item in enumerate(data):
            if all(item.get(key) == value for key, value in condition.items()):
                del data[i]
                return self.write_collection(collection, data)

        return False

    def clear_cache(self, collection: str | None = None) -> None:
        with self._lock:
            if collection:
                file_path = self._get_file_path(collection)
                if file_path in self._cache:
                    del self._cache[file_path]
                    del self._cache_timestamps[file_path]
            else:
                self._cache.clear()
                self._cache_timestamps.clear()

    def is_cache_valid(self, collection: str, max_age_seconds: int = 60) -> bool:
        file_path = self._get_file_path(collection)

        if file_path not in self._cache_timestamps:
            return False

        import time
        cache_age = time.time() - self._cache_timestamps[file_path]
        return cache_age < max_age_seconds
