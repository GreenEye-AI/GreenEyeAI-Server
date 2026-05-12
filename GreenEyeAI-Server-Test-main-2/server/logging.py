from functools import wraps
from datetime import datetime


def now() -> str:
	now = datetime.now()
	milliseconds = now.microsecond // 1000
	formatted_time = now.strftime(r'%Y.%m.%d %H:%M:%S')
	return f"{formatted_time}.{milliseconds:03d}"


@wraps(print)
def info(*args, **kwargs) -> None:
	print(f'[{now()}] INFO:', *args, **kwargs)


@wraps(print)
def warn(*args, **kwargs) -> None:
	print(f'[{now()}] WARN:', *args, **kwargs)


@wraps(print)
def error(*args, **kwargs) -> None:
	print(f'[{now()}] ERROR:', *args, **kwargs)