import math
import time
from functools import lru_cache, update_wrapper
from typing import Any, Callable


def _ttl_hash_gen(seconds: int):
    start_time = time.time()
    while True:
        yield math.floor((time.time() - start_time) / seconds)


def ttl_lru_cache(maxsize: int = 128, ttl: int = -1):
    if ttl <= 0:
        ttl = 65536
    hash_gen = _ttl_hash_gen(ttl)

    def wrapper(func: Callable) -> Callable:
        @lru_cache(maxsize)
        def ttl_func(ttl_hash, *args, **kwargs):
            return func(*args, **kwargs)

        def wrapped(*args, **kwargs) -> Any:
            th = next(hash_gen)
            return ttl_func(th, *args, **kwargs)

        setattr(wrapped, "cache_info", ttl_func.cache_info)
        setattr(wrapped, "cache_clear", ttl_func.cache_clear)
        return update_wrapper(wrapped, func)

    return wrapper
