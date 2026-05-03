from random import randint
from datetime import datetime

from server import Server, Request, Response
from server.cluster import File
from server.data import Data
from server.database import DataBase
from server.logging import info, warn, error  # noqa: F401


def web_gmod_path(server: Server, req: Request) -> Response:
	with server.data.mode_lock:
		mode: str = server.data.mode
	return Response(200).json({
		'mode': mode
	})


def web_smod_path(server: Server, req: Request) -> Response:
	data = req.get_json()
	if data is None:
		return Response(400)
	if ('mode' not in data) or ('token' not in data):
		return Response(400)
	if data['token'] != server.data.token:
		return Response(400)
	if data['mode'] not in ('auto', 'manual',):
		return Response(400)
	with server.data.mode_lock:
		server.data.mode = data['mode']
	return Response(200)


def append_command(data: Data, device: str, state: str) -> None:
	with data.commands_lock:
		commands: list[tuple[int, str, str]] = data.commands
		if len(commands) >= 10:
			del commands[-1]
		commands.append((randint(0, 65535), device, state))


def web_aclt_path(server: Server, req: Request) -> Response:
	with server.data.mode_lock:
		mode: str = server.data.mode
	if mode != 'manual':
		return Response(400)
	data = req.get_json()
	if data is None:
		return Response(400)
	if ('state' not in data) or ('token' not in data):
		return Response(400)
	if data['token'] != server.data.token:
		return Response(400)
	if data['state'] not in ('on', 'off',):
		return Response(400)
	append_command(server.data, 'light', data['state'])
	info("Команада добавлена")
	return Response(200)
	

def web_acwr_path(server: Server, req: Request) -> Response:
	with server.data.mode_lock:
		mode: str = server.data.mode
	if mode != 'manual':
		return Response(400)
	data = req.get_json()
	if data is None:
		return Response(400)
	if ('state' not in data) or ('token' not in data):
		return Response(400)
	if data['token'] != server.data.token:
		return Response(400)
	if data['state'] not in ('on', 'off',):
		return Response(400)
	append_command(server.data, 'water', data['state'])
	info("Команада добавлена")
	return Response(200)


def web_acfn_path(server: Server, req: Request) -> Response:
	with server.data.mode_lock:
		mode: str = server.data.mode
	if mode != 'manual':
		return Response(400)
	data = req.get_json()
	if data is None:
		return Response(400)
	if ('state' not in data) or ('token' not in data):
		return Response(400)
	if data['token'] != server.data.token:
		return Response(400)
	if data['state'] not in ('on', 'off',):
		return Response(400)
	append_command(server.data, 'fan', data['state'])
	info("Команада добавлена")
	return Response(200)


def web_gidx_path(server: Server, req: Request) -> Response:
	if '/index.html' in server.cluster:
		file = server.cluster['/index.html']
		if type(file) is File:
			return Response(200).html(file.read())
	return Response(404)


def web_gadm_path(server: Server, req: Request) -> Response:
	res = Response(302).header('Location', '/admin/login')

	if 'Cookie' not in req.headers:
		return res

	if 'token='+server.data.token not in req.headers['Cookie']:
		return res

	if '/admin.html' not in server.cluster:
		return Response(404)
	
	obj = server.cluster['/admin.html']
	if type(obj) is File:
		return Response(200).bytes(obj.read())
	return Response(500)


def web_galn_path(server: Server, req: Request) -> Response:
	path = '/admin/login.html'
	if path in server.cluster:
		file = server.cluster[path]
		if type(file) is File:
			return Response(200).html(file.read())
	return Response(404)


def web_paln_path(server: Server, req: Request) -> Response:
	data = req.get_json()
	if data is None:
		return Response(400)
	if ('username' not in data) or ('password' not in data):
		return Response(400)
	if (data['username'] != 'admin') or (data['password'] != 'admin123'):
		return Response(401)
	return Response(200).json({
		'token': server.data.token,
		'expires_in': 86400
	})


def web_sshd_path(server: Server, req: Request) -> Response:
	data: dict | None = req.get_json()
	if data is None:
		return Response(400)
	if (('token' not in data) or
			('water' not in data) or
			('light' not in data) or
			('fan' not in data)):
		return Response(400)
	if data['token'] != server.data.token:
		return Response(400)
	if (
		('start' not in data['light']) or
		('end' not in data['light']) or 
		('interval_hours' not in data['water']) or
		('interval_hours' not in data['fan']) or
		('duration_minutes' not in data['water']) or
		('duration_minutes' not in data['fan'])):
		return Response(400)
	if (
		(type(data['light']['start']) is not str) or
		(type(data['light']['end']) is not str) or
		(type(data['water']['interval_hours']) is not int) or
		(type(data['fan']['interval_hours']) is not int) or
		(type(data['water']['duration_minutes']) is not int) or
		(type(data['fan']['duration_minutes']) is not int)):
		return Response(400)
	try:
		data['light']['start'] = datetime.strptime(data['light']['start'], "%H:%M").time()
		data['light']['end'] = datetime.strptime(data['light']['end'], "%H:%M").time()
	except:  # noqa: E722
		return Response(400)
	server.data.schedule = {
		'light': {
			'start': data['light']['start'],
			'end': data['light']['end'],
		},
		'fan': {
			'interval_hours': data['fan']['interval_hours'],
			'duration_minutes': data['fan']['duration_minutes'],
		},
		'water': {
			'interval_hours': data['water']['interval_hours'],
			'duration_minutes': data['water']['duration_minutes'],
		},
	}
	return Response(200)
	

def web_gshd_path(server: Server, req: Request) -> Response:
	if server.data.schedule is None:
		return Response(500)
	return Response(200).json({
		'light': {
			'start': server.data.schedule['light']['start'].strftime("%H:%M"),
			'end': server.data.schedule['light']['end'].strftime("%H:%M"),
		},
		'fan': {
			'interval_hours': server.data.schedule['fan']['interval_hours'],
			'duration_minutes': server.data.schedule['fan']['duration_minutes'],
		},
		'water': {
			'interval_hours': server.data.schedule['water']['interval_hours'],
			'duration_minutes': server.data.schedule['water']['duration_minutes'],
		},
	})


def web_gdb1_path(server: Server, req: Request) -> Response:
	data = req.get_json()
	if data is None:
		return Response(400)
	if ('table' not in data) or ('seconds' not in data):
		return Response(400)
	if data['table'] not in ('water', 'light', 'fan', 'sensors'):
		return Response(400)
	if type(data['seconds']) is not int:
		return Response(400)
	if data['seconds'] < 0:
		return Response(400)
	table = data['table']
	seconds = data['seconds']
	data = server.database.execute(f'''
		SELECT * FROM {table}
		WHERE timestamp >= unixepoch('now') - {seconds};
	''', mode=3)
	if data is None:
		return Response(500)
	return Response(200).json(data)


def get_last_state(database: DataBase) -> dict[str, int]:
	_list = database.execute(''' 
		SELECT 'water' AS device,
			(SELECT state FROM water ORDER BY timestamp DESC LIMIT 1) AS state
		UNION ALL
		SELECT 'light' AS device,
			(SELECT state FROM light ORDER BY timestamp DESC LIMIT 1) AS state
		UNION ALL
		SELECT 'fan' AS device,
			(SELECT state FROM fan ORDER BY timestamp DESC LIMIT 1) AS state;
	''', mode=3)
	if _list is None:
		return {'water': 0, 'fan': 0, 'light': 0}
	data = {k: v for k,v in _list}
	return data


def web_gdb2_path(server: Server, req: Request) -> Response:
	data = get_last_state(server.database)
	return Response(200).json(data)

