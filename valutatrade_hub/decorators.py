import functools
import inspect
import time
from collections.abc import Callable

from valutatrade_hub.logging_config import get_logger


def log_action(action_name: str | None, verbose: bool = False):
    """
    Декоратор для логирования действий пользователя.
    Args:
        action_name: Имя действия (если None, будет использовано имя функции)
        verbose: Режим подробного логирования
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger("valutatrade.actions")

            # Определяем имя действия
            action = action_name or func.__name__.upper()

            # Извлекаем информацию о пользователе и параметрах
            user_info = {}
            func_params = {}

            try:
                # Пытаемся извлечь user_id из аргументов
                sig = inspect.signature(func)
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()

                for param_name, param_value in bound_args.arguments.items():
                    if param_name in ['user_id', 'username', 'currency', 'currency_code', 'amount']:
                        func_params[param_name] = param_value

                # Ищем user_id в разных возможных местах
                if 'user_id' in func_params:
                    user_info['user_id'] = func_params['user_id']
                elif 'username' in func_params:
                    user_info['username'] = func_params['username']

                # Параметры для логирования
                log_extra = {
                    'action': action,
                    **user_info,
                }

                # Добавляем только если не None
                if func_params.get('currency') or func_params.get('currency_code'):
                    log_extra['currency_code'] = func_params.get('currency') or func_params.get('currency_code')

                if func_params.get('amount') is not None:
                    log_extra['amount'] = func_params.get('amount')

                if verbose:
                    # Добавляем дополнительный контекст для verbose режима
                    log_extra['function_name'] = func.__name__
                    log_extra['module_name'] = func.__module__
                    log_extra['args_str'] = str(args)
                    log_extra['kwargs_str'] = str(kwargs)

                # Логируем начало действия
                logger.info(f"Начало действия: {action}", extra=log_extra)

                # Засекаем время выполнения
                start_time = time.time()

                # Выполняем функцию
                result = func(*args, **kwargs)

                # Рассчитываем время выполнения
                execution_time = time.time() - start_time

                # Логируем успешное завершение
                log_extra.update({
                    'result': 'OK',
                    'execution_time_ms': round(execution_time * 1000, 2)
                })

                # Добавляем результат, если это кортеж с успехом
                if isinstance(result, tuple) and len(result) >= 1:
                    success = result[0]
                    if isinstance(success, bool):
                        log_extra['result'] = 'OK' if success else 'ERROR'

                        if len(result) >= 2 and not success:
                            # Есть сообщение об ошибке
                            log_extra['error_message'] = str(result[1])

                logger.info(f"Завершение действия: {action}", extra=log_extra)

                return result

            except Exception as e:
                # Логируем ошибку
                error_log_extra = {
                    'action': action,
                    **user_info,
                    'result': 'ERROR',
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                }

                # Добавляем только если не None
                if func_params.get('currency') or func_params.get('currency_code'):
                    error_log_extra['currency_code'] = func_params.get('currency') or func_params.get('currency_code')

                if func_params.get('amount') is not None:
                    error_log_extra['amount'] = func_params.get('amount')

                logger.error(f"Ошибка в действии {action}: {e}", extra=error_log_extra)

                # Пробрасываем исключение дальше
                raise

        return wrapper
    return decorator


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """
    Декоратор для повторных попыток при сбоях
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    logger = get_logger("valutatrade.retry")
                    logger.warning(
                        f"Попытка {attempt + 1}/{max_retries} не удалась для {func.__name__}: {e}"
                    )

                    if attempt < max_retries - 1:
                        time.sleep(delay * (attempt + 1))

            logger.error(
                f"Все {max_retries} попыток для {func.__name__} не удались. Последняя ошибка: {last_exception}"
            )
            raise last_exception

        return wrapper
    return decorator


def validate_input(*validators: Callable):
    """
    Декоратор для валидации входных параметров
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for validator in validators:
                validator_result = validator(*args, **kwargs)
                if validator_result is not None and not validator_result:
                    raise ValueError(f"Валидация не пройдена: {validator.__name__}")

            return func(*args, **kwargs)

        return wrapper
    return decorator


def cache_result(ttl_seconds: int = 300):
    """
    Декоратор для кеширования результатов функций
    """
    def decorator(func: Callable) -> Callable:
        cache = {}
        cache_timestamps = {}

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = (func.__name__, args, frozenset(kwargs.items()))

            current_time = time.time()

            if cache_key in cache:
                cache_time = cache_timestamps.get(cache_key, 0)
                if current_time - cache_time < ttl_seconds:
                    return cache[cache_key]

            result = func(*args, **kwargs)
            cache[cache_key] = result
            cache_timestamps[cache_key] = current_time

            return result

        return wrapper
    return decorator
