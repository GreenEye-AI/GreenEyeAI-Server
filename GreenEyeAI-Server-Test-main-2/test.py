from time import sleep  # noqa: F401
from random import random

from server.inet import Socket
from server.request import Request 
from server.response import Response
from server.logging import info, warn, error # noqa: F401


socket = Socket()
socket.connect(('localhost', 5000))

req = Request('POST', '/api/admin/login')
req.json({
    'username': 'admin',
    'password': 'admin123'
})
req.to_socket(socket)

res = Request.from_socket(socket)
if res is None:
	warn('Входящий запрос неверный')
	exit()
data = res.get_json()
if data is None:
	warn('Входящий запрос неверный')
	exit()
token = data['token']
socket.close()

socket = Socket()
socket.connect(('localhost', 5000))

req = Request('POST', '/api/ph')
req.json({
	'token': token,
	'level': 0.0
})
req.to_socket(socket)
data = socket.recv(1024)
print(data)
socket.close()

socket = Socket()
socket.connect(('localhost', 5000))

req = Request('GET', '/api/graph/table')
req.json({
	'table': 'ph',
	'seconds': 60
})
req.to_socket(socket)
data = socket.recv(1024**2)
print(data)
socket.close()