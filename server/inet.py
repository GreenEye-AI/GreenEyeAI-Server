__all__ = ['Socket', 'KiB', 'MiB', 'GiB']
from socket import socket as Socket


KiB = 1024
MiB = KiB**2
GiB = KiB**3


def Konvert(x):
	if x >= GiB:
		return f'{x/GiB:.2f}GB'
	if x >= MiB:
		return f'{x/MiB:.2f}MB'
	if x >= KiB:
		return f'{x/KiB:.2f}KB'
	return f'{x}B'