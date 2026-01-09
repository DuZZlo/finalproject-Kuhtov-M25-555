import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from pathlib import Path

def get_exchange_rate(from_currency: str, to_currency: str) -> Optional[float]:
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()
    
    if from_currency == to_currency:
        return 1.0
    
    rates = {
        "USD": 1.0,      
        "EUR": 1.17,      
        "GBP": 1.34,     
        "JPY": 0.0064,   
        "CNY": 0.14,     
        "BTC": 89754.0,  
        "ETH": 3092.65,   
        "RUB": 0.012,
    }
    
    if from_currency in rates and to_currency in rates:
        rate_from = rates[from_currency]
        rate_to = rates[to_currency]
        return rate_to / rate_from
    
    return None

def load_json(file_path: str) -> Any:
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Ошибка при загрузке {file_path}: {e}")
    
    if "users" in file_path:
        return []
    elif "portfolios" in file_path:
        return []
    elif "rates" in file_path:
        return {"source": "stub", "last_refresh": ""}
    return {}

def save_json(data: Any, file_path: str) -> bool:
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        return True
    except (IOError, TypeError) as e:
        print(f"Ошибка при сохранении {file_path}: {e}")
        return False

def get_available_currencies() -> list:
    return ["USD", "EUR", "GBP", "JPY", "CNY", "BTC", "ETH", "RUB"]

def validate_currency(currency_code: str) -> bool:
    if not currency_code or not isinstance(currency_code, str):
        return False
    
    currency_code = currency_code.upper().strip()
    return currency_code in get_available_currencies()

def validate_amount(amount: Any) -> bool:
    try:
        amount_float = float(amount)
        return amount_float > 0
    except (ValueError, TypeError):
        return False