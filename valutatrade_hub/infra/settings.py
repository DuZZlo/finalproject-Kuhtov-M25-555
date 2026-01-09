import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
import toml


class SingletonMeta(type):
    """
    Используем метакласс для большей гибкости и читаемости кода.
    Этот подход позволяет легко создавать другие синглтоны в проекте.
    """
    
    _instances: Dict[type, object] = {}
    
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class SettingsLoader(metaclass=SingletonMeta):
    
    def __init__(self, config_path: Optional[str] = None):
        self._default_settings = {
            "data_dir": "data",
            "logs_dir": "logs",
            "default_base_currency": "USD",
            "rates_ttl_seconds": 300,  # 5 минут
            "log_level": "INFO",
            "log_format": "json",
            "max_log_file_size_mb": 10,
            "max_log_files": 5,
        }
        
        self._settings = self._default_settings.copy()
        self._config_path = config_path or self._find_config_file()
        self.reload()
    
    def _find_config_file(self) -> Optional[str]:
        possible_paths = [
            "pyproject.toml",
            "config.json",
            "valutatrade_config.json",
            os.path.join("valutatrade_hub", "config.json"),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        return None
    
    def reload(self) -> None:
        if not self._config_path:
            return
        
        try:
            if self._config_path.endswith('.toml'):
                config_data = toml.load(self._config_path)
                valutatrade_config = config_data.get("tool", {}).get("valutatrade", {})
                self._settings.update(valutatrade_config)
            elif self._config_path.endswith('.json'):
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    json_config = json.load(f)
                self._settings.update(json_config)
        except (FileNotFoundError, json.JSONDecodeError, toml.TomlDecodeError) as e:
            print(f"Warning: Could not load config from {self._config_path}: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        self._settings[key] = value
    
    @property
    def data_dir(self) -> str:
        return self.get("data_dir")
    
    @property
    def logs_dir(self) -> str:
        return self.get("logs_dir")
    
    @property
    def default_base_currency(self) -> str:
        return self.get("default_base_currency")
    
    @property
    def rates_ttl_seconds(self) -> int:
        return self.get("rates_ttl_seconds")
    
    @property
    def log_level(self) -> str:
        return self.get("log_level")
    
    @property
    def log_format(self) -> str:
        return self.get("log_format")
    
    def get_data_file_path(self, filename: str) -> str:
        data_dir = self.data_dir
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, filename)
    
    def get_log_file_path(self, filename: str) -> str:
        logs_dir = self.logs_dir
        os.makedirs(logs_dir, exist_ok=True)
        return os.path.join(logs_dir, filename)
    
    def __getitem__(self, key: str) -> Any:
        return self.get(key)
    
    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)
    
    def __contains__(self, key: str) -> bool:
        return key in self._settings
    
    def to_dict(self) -> Dict[str, Any]:
        return self._settings.copy()