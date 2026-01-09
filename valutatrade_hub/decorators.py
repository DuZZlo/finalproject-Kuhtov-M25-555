import functools
import time
from typing import Any, Callable, Optional, Dict
import inspect

from valutatrade_hub.logging_config import get_logger


def log_action(action_name: Optional[str] = None, verbose: bool = False):
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger("valutatrade.actions")
            
            action = action_name or func.__name__.upper()
            
            user_info = {}
            func_params = {}
            
            try:
                sig = inspect.signature(func)
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()
                
                for param_name, param_value in bound_args.arguments.items():
                    if param_name in ['user_id', 'username', 'currency', 'currency_code', 'amount']:
                        func_params[param_name] = param_value
                
                if 'user_id' in func_params:
                    user_info['user_id'] = func_params['user_id']
                elif 'username' in func_params:
                    user_info['username'] = func_params['username']

                log_params = {
                    'action': action,
                    **user_info,
                    'currency_code': func_params.get('currency') or func_params.get('currency_code'),
                    'amount': func_params.get('amount'),
                }
                
                if verbose:
                    log_params['function'] = func.__name__
                    log_params['module'] = func.__module__
                    log_params['args'] = str(args)
                    log_params['kwargs'] = str(kwargs)
                
                logger.info(f"Начало действия: {action}", extra=log_params)
                
                start_time = time.time()
                
                result = func(*args, **kwargs)
                
                execution_time = time.time() - start_time
                
                log_params.update({
                    'result': 'OK',
                    'execution_time_ms': round(execution_time * 1000, 2)
                })
                
                if isinstance(result, tuple) and len(result) >= 1:
                    success = result[0]
                    if isinstance(success, bool):
                        log_params['result'] = 'OK' if success else 'ERROR'
                        
                        if len(result) >= 2 and not success:
                            log_params['error_message'] = str(result[1])
                
                logger.info(f"Завершение действия: {action}", extra=log_params)
                
                return result
                
            except Exception as e:
                error_log_params = {
                    'action': action,
                    **user_info,
                    'currency_code': func_params.get('currency') or func_params.get('currency_code'),
                    'amount': func_params.get('amount'),
                    'result': 'ERROR',
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                }
                
                logger.error(f"Ошибка в действии {action}: {e}", extra=error_log_params)
                
                raise
        
        return wrapper
    return decorator


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
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