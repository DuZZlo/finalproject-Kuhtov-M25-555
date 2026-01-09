class ValutaTradeError(Exception):
    pass

class InsufficientFundsError(ValutaTradeError):
    
    def __init__(self, currency_code: str, available: float, required: float):
        self.currency_code = currency_code
        self.available = available
        self.required = required
        message = f"Недостаточно средств: доступно {available:.4f} {currency_code}, требуется {required:.4f} {currency_code}"
        super().__init__(message)

class CurrencyNotFoundError(ValutaTradeError):
    
    def __init__(self, currency_code: str):
        self.currency_code = currency_code
        message = f"Неизвестная валюта '{currency_code}'"
        super().__init__(message)


class ApiRequestError(ValutaTradeError):
    def __init__(self, reason: str, service: str = "unknown"):
        self.reason = reason
        self.service = service
        message = f"Ошибка при обращении к внешнему API ({service}): {reason}"
        super().__init__(message)


class AuthenticationError(ValutaTradeError):
    
    def __init__(self, message: str = "Ошибка аутентификации"):
        super().__init__(message)


class PortfolioNotFoundError(ValutaTradeError):
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        message = f"Портфель для пользователя {user_id} не найден"
        super().__init__(message)


class ValidationError(ValutaTradeError):
    
    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(f"Ошибка валидации поля '{field}': {message}")


class RateUnavailableError(ValutaTradeError):
    
    def __init__(self, from_currency: str, to_currency: str):
        self.from_currency = from_currency
        self.to_currency = to_currency
        message = f"Курс {from_currency}→{to_currency} недоступен"
        super().__init__(message)