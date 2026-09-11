import asyncio
import logging
from functools import wraps

_log = logging.getLogger("wbc.retry")


def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exc = None
            wait = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < max_attempts:
                        _log.warning(
                            "Tentativa %d/%d falhou para %s: %s. Retentando em %.1fs...",
                            attempt, max_attempts, func.__name__, e, wait,
                        )
                        await asyncio.sleep(wait)
                        wait *= backoff
            raise last_exc
        return wrapper
    return decorator
