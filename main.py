import uuid
from time import sleep
from datetime import datetime
from threading import Lock

from server import Server, Request, Response
from server import Data, DataBase
from server.cluster import Cluster
from server.logging import info, warn, error  # noqa: F401
from server.threads import nonblocking

from esp_paths import esp_sens_path, esp_gcmd_path, esp_dcmd_path

from web_paths import web_gmod_path, web_smod_path
from web_paths import web_gidx_path, web_gadm_path, web_galn_path, web_paln_path
from web_paths import web_acwr_path, web_aclt_path, web_acfn_path
from web_paths import web_gdb2_path
# установка и получение расписания
from web_paths import web_sshd_path, web_gshd_path
from web_paths import get_last_state, append_command


data = Data() # общие переменные и тд
data.commands = list()
data.commands_lock = Lock()
data.mode = 'manual' # или auto
data.mode_lock = Lock()
data.token = str(uuid.uuid4())
info('Токен авторизации:', data.token)


database = DataBase('main.db')
database.execute('''
	CREATE TABLE IF NOT EXISTS sensors (
		timestamp REAL NOT NULL,
		temperature FLOAT NOT NULL,
		humidity FLOAT NOT NULL
	)
''')
database.execute('''
	CREATE TABLE IF NOT EXISTS light (
		timestamp REAL NOT NULL,
		state BOOLEAN NOT NULL
	)
''')
database.execute('''
	CREATE TABLE IF NOT EXISTS water (
		timestamp REAL NOT NULL,
		state BOOLEAN NOT NULL
	)
''')
database.execute('''
	CREATE TABLE IF NOT EXISTS fan (
		timestamp REAL NOT NULL,
		state BOOLEAN NOT NULL
	)
''')


cluster = Cluster('site')
if cluster is None:
	error('Кластер повреждён!')
	exit()
server = Server(data, database, cluster)


@nonblocking
def main():
	# Анти-спам: время последней отправленной команды для каждого устройства.
	# Предотвращает спам в очередь, пока база данных не обновится.
	last_command_time = {'light': 0.0, 'water': 0.0, 'fan': 0.0}
	COMMAND_COOLDOWN = 30  # секунд ожидания перед повторной отправкой той же команды
	
	# Время последнего включения (для расчета duration_minutes)
	last_water_start = 0.0
	last_fan_start = 0.0

	while True:
		# Если не авто-режим или нет расписания — просто спим и ждем
		if (data.mode != 'auto') or (data.schedule is None):
			sleep(10)
			continue
			
		time_now = datetime.now().time()
		timestamp = datetime.now().timestamp()
		state = get_last_state(database)

		# ==========================================
		# 1. УПРАВЛЕНИЕ ОСВЕЩЕНИЕМ (LIGHT)
		# ==========================================
		start = data.schedule['light']['start']
		end = data.schedule['light']['end']
		
		# Определяем, каким должен быть свет прямо сейчас (1 - вкл, 0 - выкл)
		desired_light = 0 
		if start <= end:
			# Прямой период (например, с 08:00 до 20:00)
			if start <= time_now <= end:
				desired_light = 1
		else:
			# Обратный период (переход через полночь, например, с 22:00 до 06:00)
			if time_now >= start or time_now <= end:
				desired_light = 1

		# Если фактический статус не совпадает с желаемым
		if state['light'] != desired_light:
			# Проверяем кулдаун, чтобы не спамить в очередь
			if (timestamp - last_command_time['light']) >= COMMAND_COOLDOWN:
				action = 'on' if desired_light == 1 else 'off'
				append_command(data, 'light', action)
				last_command_time['light'] = timestamp

		# ==========================================
		# 2. УПРАВЛЕНИЕ ПОЛИВОМ (WATER)
		# ==========================================
		water_interval = data.schedule['water']['interval_hours'] * 3600
		water_duration = data.schedule['water']['duration_minutes'] * 60

		if state['water'] == 0:
			# Если вода выключена и прошло достаточно времени с ПОСЛЕДНЕГО включения
			if (timestamp - last_water_start) >= water_interval:
				if (timestamp - last_command_time['water']) >= COMMAND_COOLDOWN:
					append_command(data, 'water', 'on')
					last_command_time['water'] = timestamp
					last_water_start = timestamp  # Фиксируем начало полива
		
		elif state['water'] == 1:
			# Если вода включена и прошло время длительности (duration)
			if (timestamp - last_water_start) >= water_duration:
				if (timestamp - last_command_time['water']) >= COMMAND_COOLDOWN:
					append_command(data, 'water', 'off')
					last_command_time['water'] = timestamp

		# ==========================================
		# 3. УПРАВЛЕНИЕ ВЕНТИЛЯТОРОМ (FAN)
		# ==========================================
		# Предполагается, что у вентилятора логика аналогична поливу
		
		fan_interval = data.schedule['fan']['interval_hours'] * 3600
		fan_duration = data.schedule['fan']['duration_minutes'] * 60

		if state['fan'] == 0:
			if (timestamp - last_fan_start) >= fan_interval:
				if (timestamp - last_command_time['fan']) >= COMMAND_COOLDOWN:
					append_command(data, 'fan', 'on')
					last_command_time['fan'] = timestamp
					last_fan_start = timestamp
						
		elif state['fan'] == 1:
			if (timestamp - last_fan_start) >= fan_duration:
				if (timestamp - last_command_time['fan']) >= COMMAND_COOLDOWN:
					append_command(data, 'fan', 'off')
					last_command_time['fan'] = timestamp

		# ==========================================
		# Задержка цикла (ОБЯЗАТЕЛЬНО)
		# ==========================================
		# Не дает скрипту утилизировать процессор на 100% и бережет базу данных
		sleep(5)


@server.path('GET', '/me')
def me_path(server: Server, req: Request) -> Response:
	return Response(200).text(req.to_body().replace('\r\n', '<br>'))


@server.path('GET', '/ping')
def ping_path(server: Server, req: Request) -> Response:
	return Response(200)


server.path('POST', '/api/esp/sensors'   )(esp_sens_path)
server.path('GET',  '/api/esp/command'   )(esp_gcmd_path)
server.path('POST', '/api/esp/command'   )(esp_dcmd_path)

server.path('GET',  '/api/command/mode'  )(web_gmod_path)
server.path('POST', '/api/command/mode'  )(web_smod_path)

server.path('POST', '/api/command/water' )(web_acwr_path)
server.path('POST', '/api/command/light' )(web_aclt_path)
server.path('POST', '/api/command/fan'   )(web_acfn_path)

server.path('GET',  '/'                  )(web_gidx_path)
server.path('GET',  '/admin'             )(web_gadm_path)
server.path('GET',  '/admin.html'        )(web_gadm_path)
server.path('GET',  '/admin/login'       )(web_galn_path)
server.path('POST', '/api/admin/login'   )(web_paln_path)
# server.path('GET',  '/api/web/db'        )(web_gdb1_path)
server.path('GET',  '/api/last_state'    )(web_gdb2_path)
server.path('POST', '/api/schedule'      )(web_sshd_path)
server.path('GET',  '/api/schedule'      )(web_gshd_path)

main()
server.start()