from __future__ import annotations
from typing import Callable
from socket import socket as Socket, AF_INET, SOCK_STREAM
from time import sleep

from .logging import info, warn, error
from .threads import nonblocking
from .request import Request
from .response import Response
from .data import Data
from .database import DataBase
from .cluster import Cluster, File


CALLBACK_TYPE = Callable[['Server', Request], Response]


def get_content_type(path: str) -> str:
	end = '' 
	if '.' in path:
		end = path.rsplit('.', 1)[1]
	content_type = 'text/plain'
	match end:
		case 'css':
			content_type = 'text/css'
		case 'html':
			content_type = 'text/html; charset=utf-8'
		case 'js':
			content_type = 'application/javascript'
		case 'jpg', 'jpeg':
			content_type = 'image/jpeg'
		case 'png':
			content_type = 'image/png'
		case 'webp':
			content_type = 'image/webp'
		case 'svg':
			content_type = 'image/svg+xml'
		case 'xml':
			content_type = 'text/xml'
	return content_type


class Server:
	data: Data
	database: DataBase
	cluster: Cluster
	host: str
	port: int
	socket: Socket
	paths: dict[str, dict[str, CALLBACK_TYPE]]
	
	def __init__(self,
		data: Data,
		database: DataBase,
		cluster: Cluster,
		host: str = '0.0.0.0',
		port: int = 5000,
	) -> None:
		self.data = data
		self.database = database
		self.cluster = cluster
		self.paths = dict()
		self.host = host
		self.port = port

	# используется для добавления обработчика на путь
	def path(self, method: str, path: str) -> Callable[[CALLBACK_TYPE], None]:
		def wrapper(func: CALLBACK_TYPE):
			if path not in self.paths:
				self.paths[path] = dict()
			self.paths[path][method] = func
		return wrapper
		
	@nonblocking
	def accepting(self) -> None:
		running: bool = True
		while running:
			client: Socket
			ip: str
			port: int
			client, (ip, port) = self.socket.accept()
			self.processing(client, ip, port) # не блокирует поток

	@nonblocking
	def processing(self, client: Socket, ip: str, port: int) -> None:
		info(f'Подключение: {ip}:{port}')
		client.settimeout(5.0)
		running: bool = True
		while running:
			try:
				req = Request.from_socket(client)
			except TimeoutError:
				running = False
				continue
			except ConnectionResetError:
				running = False
				continue
			except:
				raise

			if req is None:
				running = False
				warn(f'Неверный HTTP: {ip}:{port}')
				client.send(Response(400).to_bytes())
				continue
			
			if 'Connection' in req.headers:
				if req.headers['Connection'] == 'keep-alive':
					client.settimeout(60.0)
				else:
					running = False
			else:
				running = False

			if req.path not in self.paths:
				if req.path in self.cluster:
					file = self.cluster[req.path]
					if type(file) is File:
						res = Response(200)
						res.bytes(file.read())
						res.header('Content-Type', get_content_type(file.path))
						res.header('Connection', 'keep-alive' if running else 'close')
						client.send(res.to_bytes())
						continue
				
				res = Response(404)
				res.text("404: Страница не найдена")
				res.header('Content-Type', 'text/html; charset=utf-8')
				res.header('Connection', 'keep-alive' if running else 'close')
				client.send(res.to_bytes())
				continue

			if req.method not in self.paths[req.path]:
				res = Response(400)
				res.header('Connection', 'keep-alive' if running else 'close')
				client.send(res.to_bytes())
				continue
	
			res = self.paths[req.path][req.method](self, req)
			res.header('Connection', 'keep-alive' if running else 'close')
			client.send(res.to_bytes())

		info(f'Отключение: {ip}:{port}')
		client.close()


	def start(self) -> None:
		info('Запуск сервера')
		self.socket: Socket = Socket(AF_INET, SOCK_STREAM)
		self.socket.bind((self.host, self.port))
		self.socket.listen()
		self.accepting() # не блокирует поток

		try:
			while True:
				if not self.cluster.update():
					error('Кластер повреждён!')
					break
				sleep(0.5)
			error('Аварийная остановка сервера!')
		except KeyboardInterrupt:
			info("Принудительная остановка сервера")
			if self.database is not None:
				self.database.close()
		except:
			error('Аварийная остановка сервера!')
			raise