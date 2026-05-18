from threading import Thread, Lock, RLock
from functools import wraps
from typing import Callable, Any
__all__ = ['nonblocking', 'Lock', 'RLock']


def nonblocking(func: Callable[..., Any]) -> Callable[..., None]:
	@wraps(func)
	def wrapper(*args, **kwargs) -> None:
		Thread(target=func, args=args, kwargs=kwargs, daemon=True).start()
	return wrapper