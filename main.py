import uuid
import json
from time import sleep
from datetime import datetime
from threading import Lock
from socket import socket as Socket
from os.path import isfile

try:
	import cv2 # type: ignore
	from picamera2 import Picamera2 # type: ignore
	from libcamera import controls # type: ignore
	is_rasberi_server = True
except:  # noqa: E722
	is_rasberi_server = False

try:
	from ultralytics import YOLO
	from ultralytics.engine.results import Results
	from io import BytesIO
	from PIL import Image
	model = YOLO("best.pt")
	is_model_server = True
except:  # noqa: E722
	is_model_server = False

from server import Server, Request, Response
from server import Data, DataBase
from server.cluster import Cluster, File
from server.logging import info, warn, error  # noqa: F401
from server.threads import nonblocking

from esp_paths import esp_sens_path, esp_gcmd_path, esp_dcmd_path

from web_paths import web_gmod_path, web_smod_path
from web_paths import web_gadm_path, web_paln_path
# работа с БД
from web_paths import web_acwr_path, web_aclt_path, web_acfn_path, web_sphl_path
from web_paths import web_gdb1_path, web_gdb2_path, web_gpts_path
# установка и получение расписания
from web_paths import web_sshd_path, web_gshd_path
# получение стрима
from web_paths import web_gstr_path
from web_paths import get_last_state, append_command


data = Data() # общие переменные и тд
data.commands = list()
data.commands_lock = Lock()
data.mode = 'manual' # или auto
data.mode_lock = Lock()
data.token = str(uuid.uuid4())
if not is_rasberi_server:
	with open("stream.jpg", 'rb') as file:
		data.stream = file.read()
data.stream_lock = Lock()
data.plants = {i+1: 'empty' for i in range(20)}
data.schedule = {
	'light': {
		'start': '08:00',
		'end': '18:00'
	},
	'fan': {
		'interval_hours': 2,
		'duration_minutes': 2
	},
	'water': {
		'interval_hours': 5,
		'duration_minutes': 5
	}
}

if isfile('schedule.json'):
	with open('schedule.json', 'rb') as file:
		try:
			data.schedule = json.load(file)
		except:  # noqa: E722
			error('Файл schedule.json повреждён или содержет не верный формат')

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
database.execute('''
	CREATE TABLE IF NOT EXISTS ph (
		timestamp REAL NOT NULL,
		level REAL NOT NULL
	)
''')

database.execute('CREATE INDEX IF NOT EXISTS idx_sensors_ts ON sensors(timestamp)')
database.execute('CREATE INDEX IF NOT EXISTS idx_light_ts   ON   light(timestamp)')
database.execute('CREATE INDEX IF NOT EXISTS idx_water_ts   ON   water(timestamp)')
database.execute('CREATE INDEX IF NOT EXISTS idx_fan_ts     ON     fan(timestamp)')
database.execute('CREATE INDEX IF NOT EXISTS idx_ph_ts      ON      ph(timestamp)')


cluster = Cluster('site')
if cluster is None:
	error('Кластер повреждён!')
	exit()
server = Server(data, database, cluster, port=8080)


@nonblocking
def photo_processing():
	# if (not is_model_server) or (not is_rasberi_server):
	if (not is_model_server):
		return
	
	x1, y1 = (130, 100)
	x2, y2 = (x1+738, y1+551)

	# 1. Нормализуем координаты (на случай, если x2 < x1 или y2 < y1)
	x_left, x_right = sorted([x1, x2])
	y_top, y_bottom = sorted([y1, y2])

	# 2. Параметры сетки
	cols, rows = 5, 4
	tile_w = (x_right - x_left) / cols
	tile_h = (y_bottom - y_top) / rows

	# 3. Вычисляем точные границы разрезов (избегаем зазоров и наложений)
	x_bounds = [int(round(x_left + i * tile_w)) for i in range(cols + 1)]
	y_bounds = [int(round(y_top + i * tile_h)) for i in range(rows + 1)]
	x_bounds[-1], y_bounds[-1] = x_right, y_bottom  # Фиксируем правый нижний угол
	
	last_screenshot_time = 0
	image_queue: list[tuple[Image.Image, int]] = []

	while data.stream is None:
		sleep(0.1)
	
	while True:
		timestamp = datetime.now().timestamp()
		if (timestamp - last_screenshot_time > 30):
			last_screenshot_time = timestamp
			image_queue.clear()
			img = Image.open(BytesIO(data.stream))

			idx = 1
			for r in range(rows):
				for c in range(cols):
					# (left, upper, right, lower)
					box = (x_bounds[c], y_bounds[r], x_bounds[c+1], y_bounds[r+1])
					tile = img.crop(box)
						
					# Формат JPEG требует режима RGB (RGBA/Grayscale вызовут ошибку)
					if tile.mode != 'RGB':
						tile = tile.convert('RGB')
					image_queue.append((tile, idx,))
					idx += 1
		
		start = datetime.now().timestamp()
		if len(image_queue) > 0:
			img, idx = image_queue.pop(0)
			results: list[Results] = model(img, save=False, conf=0.25, verbose=False)
			for result in results:
				boxes = result.boxes
				if boxes is not None and len(boxes) > 0:
					max_conf = 0
					max_cls_name = 'empty'
					for i, cls_id in enumerate(boxes.cls):
						cls_name = result.names[int(cls_id)]
						conf = boxes.conf[i]
						if '_' in cls_name:
							cls_name = cls_name.split('_', 1)[0]
						if conf > max_conf:
							max_conf = conf
							max_cls_name = cls_name
					data.plants[idx] = max_cls_name
				else:
					data.plants[idx] = 'empty'

		delay = 1 - (datetime.now().timestamp() - start)
		if (delay > 0):
			sleep(delay)

@nonblocking
def update_stream():
	if not is_rasberi_server:
		return
	
	picam2 = Picamera2()
	config = picam2.create_video_configuration(
			main={"size": (1080, 680), "format": "RGB888"},
			controls={"FrameRate": 24}, 
	)
	picam2.configure(config)
	picam2.set_controls({
		# Ручной режим (отключаем автофокус)
		"AfMode": controls.AfModeEnum.Manual,
		# Фокус на ~0.5 метра (1 / 2.0 = 0.5м)
		"LensPosition": 0,
	})
	picam2.start()
	sleep(1)  # прогрев камеры

	while True:
		frame = picam2.capture_array()
		ret, buffer = cv2.imencode('.jpg', frame)
		jpeg_bytes = buffer.tobytes()
		data.stream = jpeg_bytes


@nonblocking
def auto_control():
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
		start = datetime.strptime(data.schedule['light']['start'], "%H:%M").time()
		end = datetime.strptime(data.schedule['light']['end'], "%H:%M").time()
		
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

		sleep(5)


@server.path('GET', '/me')
def me_path(server: Server, client: Socket, req: Request) -> Response | None:
	return Response(200).text(req.to_body().replace('\r\n', '<br>'))


@server.path('GET', '/ping')
def ping_path(server: Server, client: Socket, req: Request) -> Response | None:
	return Response(200).header('Connection', 'keep-alive')


@server.path('GET',  '/')
def web_gidx_path(server: Server, client: Socket, req: Request) -> Response | None:
	if '/index.html' in server.cluster:
		file = server.cluster['/index.html']
		if type(file) is File:
			return Response(200).html(file.read())
	return Response(404)


server.path('POST', '/api/esp/sensors'   )(esp_sens_path)
server.path('GET',  '/api/esp/command'   )(esp_gcmd_path)
server.path('POST', '/api/esp/command'   )(esp_dcmd_path)

server.path('GET',  '/api/command/mode'  )(web_gmod_path)
server.path('POST', '/api/command/mode'  )(web_smod_path)

server.path('POST', '/api/command/water' )(web_acwr_path)
server.path('POST', '/api/command/light' )(web_aclt_path)
server.path('POST', '/api/command/fan'   )(web_acfn_path)

server.path('POST', '/api/ph'            )(web_sphl_path)

server.path('GET',  '/admin'             )(web_gadm_path)
server.path('GET',  '/admin.html'        )(web_gadm_path)
server.path('POST', '/api/admin/login'   )(web_paln_path)
server.path('POST', '/api/graph/table'   )(web_gdb1_path)
server.path('GET',  '/api/last_state'    )(web_gdb2_path)
server.path('POST', '/api/schedule'      )(web_sshd_path)
server.path('GET',  '/api/schedule'      )(web_gshd_path)
server.path('GET',  '/api/plants'        )(web_gpts_path)

server.path('GET',  '/api/stream',       )(web_gstr_path)

auto_control()
update_stream()
photo_processing()
server.start()