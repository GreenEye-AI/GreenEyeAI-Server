from time import time

from server import Server, Request, Response
from server.logging import info, warn, error  # noqa: F401


def esp_sens_path(server: Server, req: Request) -> Response:
	data: dict = req.get_json()
	if server.database is None:
		return Response(500)
	if data and 'temperature' in data and 'humidity' in data:
		server.database.execute(
			'INSERT INTO sensors (timestamp, temperature, humidity) VALUES (?, ?, ?)',
			(time(), data['temperature'], data['humidity'])
		)
	else:
		return Response(400).text('Не полные данные')
	return Response(200)


def esp_gcmd_path(server: Server, req: Request) -> Response:
	commands: list[tuple[int, str, str]] = server.data.commands
	command_id, device, action = (0, 'None', 'off')
	with server.data.commands_lock:
		if len(commands) > 0:
			command_id, device, action = commands[0]
	return Response(200).json({
		"queue_size": len(commands) - 1,
		"id": command_id,
		"device": device,
		"action": action
	})


def esp_dcmd_path(server: Server, req: Request) -> Response:
	commands: list[tuple[int, str, str]] = server.data.commands
	data = req.get_json()
	if data is None:
		return Response(400)
	if ('id' not in data):
		return Response(400)
	with server.data.commands_lock:
		if len(commands) == 0:
			return Response(400)
		if data['id'] != commands[0][0]:
			return Response(400)
		command_id, device, action = commands.pop(0)
	server.database.execute(
		f'INSERT INTO {device} (timestamp, state) VALUES (?, ?)',
		(time(), True if action == 'on' else False)
	)
	info("Команда удалена")
	return Response(200)