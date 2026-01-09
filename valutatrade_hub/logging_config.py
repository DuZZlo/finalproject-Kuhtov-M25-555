import logging
import logging.handlers
import os
from pathlib import Path
import json
from datetime import datetime

from valutatrade_hub.infra.settings import SettingsLoader


def setup_logging():
    settings = SettingsLoader()
    
    logs_dir = settings.logs_dir
    os.makedirs(logs_dir, exist_ok=True)
    
    log_format = settings.log_format
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    
    if log_format == "json":
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    logger = logging.getLogger("valutatrade")
    logger.setLevel(log_level)
    logger.propagate = False
    
    log_file = os.path.join(logs_dir, "actions.log")
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=settings.get("max_log_file_size_mb", 10) * 1024 * 1024,  # MB to bytes
        backupCount=settings.get("max_log_files", 5)
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.WARNING)
    
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    api_logger = logging.getLogger("valutatrade.api")
    api_logger.setLevel(log_level)
    
    return logger


class JsonFormatter(logging.Formatter):
    
    def format(self, record):
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if hasattr(record, "action"):
            log_record["action"] = record.action
        if hasattr(record, "username"):
            log_record["username"] = record.username
        if hasattr(record, "user_id"):
            log_record["user_id"] = record.user_id
        if hasattr(record, "currency_code"):
            log_record["currency_code"] = record.currency_code
        if hasattr(record, "amount"):
            log_record["amount"] = record.amount
        if hasattr(record, "rate"):
            log_record["rate"] = record.rate
        if hasattr(record, "result"):
            log_record["result"] = record.result
        if hasattr(record, "error_type"):
            log_record["error_type"] = record.error_type
        if hasattr(record, "error_message"):
            log_record["error_message"] = record.error_message
        
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_record, ensure_ascii=False)


def get_logger(name: str = "valutatrade") -> logging.Logger:
    return logging.getLogger(name)