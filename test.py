from time import sleep  # noqa: F401
from random import choice  # noqa: F401

from server.inet import Socket
from server.request import Request
from server.logging import info, warn, error # noqa: F401


socket = Socket()
socket.connect(('localhost', 5000))
socket.settimeout(None)

req = Request('POST', '/api/admin/login')
req.header('Connection', 'keep-alive')
req.json({'username': 'admin', 'password': 'admin123'})
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

# states = ['on', 'off']

# req = Request('POST', '/api/command/water')
# req.header('Connection', 'keep-alive')
# req.json({'state': choice(states), 'token': token})
# req.to_socket(socket)

# sleep(0.1)
# req = Request('POST', '/api/command/light')
# req.header('Connection', 'keep-alive')
# req.json({'state': choice(states), 'token': token})
# req.to_socket(socket)

# sleep(0.1)
# req = Request('POST', '/api/command/fan')
# req.header('Connection', 'keep-alive')
# req.json({'state': choice(states), 'token': token})
# req.to_socket(socket)

# sleep(1)
# exit()

req = Request('POST', '/api/schedule')
req.header('Connection', 'keep-alive')
req.json({
	"token": token,
	"light": {"start": "08:00", "end": "19:14"},
	"fan": {"interval_hours": 1, "duration_minutes": 1},
	"water": {"interval_hours": 1, "duration_minutes": 2}
})
req.to_socket(socket)

res = Request.from_socket(socket)
if res is None:
	warn('Входящий запрос неверный')
	exit()
print(res.to_text())

sleep(1)