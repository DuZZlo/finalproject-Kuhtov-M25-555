import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from pathlib import Path
from valutatrade_hub.core.currencies import CurrencyRegistry, CurrencyNotFoundError
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.infra.database import DatabaseManager

def get_exchange_rate(from_currency: str, to_currency: str) -> Optional[float]:
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()
    
    if from_currency == to_currency:
        return 1.0
    
    try:
        CurrencyRegistry.get_currency(from_currency)
        CurrencyRegistry.get_currency(to_currency)
    except CurrencyNotFoundError:
        return None

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
        rate_from_usd = rates[from_currency]
        rate_to_usd = rates[to_currency]
        
        return rate_to_usd / rate_from_usd
    
    return None

def get_available_currencies() -> list:
    return ["USD", "EUR", "GBP", "JPY", "CNY", "BTC", "ETH", "RUB"]

def validate_currency(currency_code: str) -> bool:
    try:
        CurrencyRegistry.get_currency(currency_code)
        return True
    except CurrencyNotFoundError:
        return False

def validate_amount(amount: Any) -> bool:
    try:
        amount_float = float(amount)
        return amount_float > 0
    except (ValueError, TypeError):
        return False