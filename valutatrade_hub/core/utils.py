import json
import os
from datetime import datetime
from typing import Any

from valutatrade_hub.core.currencies import CurrencyNotFoundError, CurrencyRegistry
from valutatrade_hub.infra.settings import SettingsLoader


def get_exchange_rate(from_currency: str, to_currency: str) -> float | None:
    """
    Получает курс обмена между валютами из локального кеша.
    """
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
            with open(rates_file, encoding='utf-8') as f:
                data = json.load(f)

            if "pairs" in data:
                pairs = data.get("pairs", {})

                pair_key = f"{from_currency}_{to_currency}"
                if pair_key in pairs:
                    rate_info = pairs[pair_key]
                    if isinstance(rate_info, dict) and "rate" in rate_info:
                        return float(rate_info["rate"])

                from_to_usd = f"{from_currency}_USD"
                usd_to_to = f"USD_{to_currency}"

                if from_to_usd in pairs and usd_to_to in pairs:
                    rate_from_usd = float(pairs[from_to_usd]["rate"])
                    rate_usd_to = float(pairs[usd_to_to]["rate"])

                    return rate_from_usd * rate_usd_to

                to_to_usd = f"{to_currency}_USD"
                if from_to_usd in pairs and to_to_usd in pairs:
                    rate_from_usd = float(pairs[from_to_usd]["rate"])
                    rate_to_usd = float(pairs[to_to_usd]["rate"])

                    if rate_to_usd != 0:
                        return rate_from_usd / rate_to_usd

        return None

    except (OSError, json.JSONDecodeError, ValueError, KeyError, ZeroDivisionError) as e:
        print(f"Warning: Could not load exchange rate from cache: {e}")
        return None


def validate_currency(currency_code: str) -> bool:
    """
    Проверяет валидность кода валюты через реестр
    """
    try:
        CurrencyRegistry.get_currency(currency_code)
        return True
    except CurrencyNotFoundError:
        return False


def validate_amount(amount: Any) -> bool:
    """
    Проверяет валидность суммы
    """
    try:
        amount_float = float(amount)
        return amount_float > 0
    except (ValueError, TypeError):
        return False


def is_cache_valid() -> bool:
    """
    Проверяет, является ли кеш курсов актуальным
    """
    settings = SettingsLoader()
    rates_file = settings.get_data_file_path("rates.json")

    try:
        if not os.path.exists(rates_file):
            return False

        with open(rates_file, encoding='utf-8') as f:
            data = json.load(f)

        if "last_refresh" not in data:
            return False

        last_refresh = datetime.fromisoformat(data["last_refresh"])
        ttl_seconds = settings.rates_ttl_seconds

        return (datetime.now() - last_refresh).total_seconds() < ttl_seconds

    except (OSError, json.JSONDecodeError, ValueError, KeyError):
        return False


def get_cache_info() -> dict[str, Any]:
    """
    Возвращает информацию о кеше курсов.
    """
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

            with open(rates_file, encoding='utf-8') as f:
                data = json.load(f)

            if "last_refresh" in data:
                info["last_refresh"] = data["last_refresh"]
                info["is_valid"] = is_cache_valid()

            if "source" in data:
                info["source"] = data["source"]

            if "pairs" in data:
                info["rates_count"] = len(data["pairs"])

    except (OSError, json.JSONDecodeError):
        pass

    return info
