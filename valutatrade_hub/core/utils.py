import json
import os
from datetime import datetime
from typing import Optional, Dict, Any

from valutatrade_hub.core.currencies import CurrencyRegistry, CurrencyNotFoundError
from valutatrade_hub.infra.settings import SettingsLoader


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
    
    settings = SettingsLoader()
    rates_file = settings.get_data_file_path("rates.json")
    
    try:
        if os.path.exists(rates_file):
            with open(rates_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if "pairs" in data:
                pairs = data.get("pairs", {})
                
                pair_key = f"{from_currency}_{to_currency}"
                if pair_key in pairs:
                    rate_info = pairs[pair_key]
                    if isinstance(rate_info, dict) and "rate" in rate_info:
                        return float(rate_info["rate"])
                
                reverse_pair = f"{to_currency}_{from_currency}"
                if reverse_pair in pairs:
                    rate_info = pairs[reverse_pair]
                    if isinstance(rate_info, dict) and "rate" in rate_info:
                        rate = float(rate_info["rate"])
                        if rate != 0:
                            return 1.0 / rate
                
                if from_currency != "USD" and to_currency != "USD":
                    rate_from_usd = get_exchange_rate(from_currency, "USD")
                    rate_to_usd = get_exchange_rate("USD", to_currency)
                    
                    if rate_from_usd and rate_to_usd:
                        return rate_to_usd / rate_from_usd
        
        return None
        
    except (json.JSONDecodeError, IOError, ValueError, KeyError) as e:
        print(f"Warning: Could not load exchange rate from cache: {e}")
        return None


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


def is_cache_valid() -> bool:
    settings = SettingsLoader()
    rates_file = settings.get_data_file_path("rates.json")
    
    try:
        if not os.path.exists(rates_file):
            return False
        
        with open(rates_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if "last_refresh" not in data:
            return False
        
        last_refresh = datetime.fromisoformat(data["last_refresh"])
        ttl_seconds = settings.rates_ttl_seconds
        
        return (datetime.now() - last_refresh).total_seconds() < ttl_seconds
        
    except (json.JSONDecodeError, IOError, ValueError, KeyError):
        return False


def get_cache_info() -> Dict[str, Any]:
    settings = SettingsLoader()
    rates_file = settings.get_data_file_path("rates.json")
    
    info = {
        "exists": False,
        "is_valid": False,
        "last_refresh": None,
        "rates_count": 0,
        "source": None
    }
    
    try:
        if os.path.exists(rates_file):
            info["exists"] = True
            
            with open(rates_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if "last_refresh" in data:
                info["last_refresh"] = data["last_refresh"]
                info["is_valid"] = is_cache_valid()
            
            if "source" in data:
                info["source"] = data["source"]
            
            if "pairs" in data:
                info["rates_count"] = len(data["pairs"])
        
    except (json.JSONDecodeError, IOError):
        pass
    
    return info