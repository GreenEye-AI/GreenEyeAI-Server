from __future__ import annotations
from typing import Callable
from socket import SO_REUSEADDR, SOL_SOCKET, socket as Socket, AF_INET, SOCK_STREAM
from time import sleep
import mimetypes

from .logging import info, warn, error
from .threads import nonblocking
from .request import Request
from .response import Response
from .data import Data
from .database import DataBase
from .cluster import Cluster, File


CALLBACK_TYPE = Callable[['Server', Socket, Request], Response | None]


class Server:
	data: Data
	database: DataBase
	cluster: Cluster
	host: str
	port: int
	socket: Socket
	paths: dict[str, dict[str, CALLBACK_TYPE]]
	debug: bool
	
	def __init__(self,
		data: Data,
		database: DataBase,
		cluster: Cluster,
		host: str = '0.0.0.0',
		port: int = 5000,
		debug: bool = False,
	) -> None:
		self.data = data
		self.database = database
		self.cluster = cluster
		self.paths = dict()
		self.host = host
		self.port = port
		self.debug = debug


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
			client, (ip, port) = self.socket.accept()
			self.processing(client, ip, port) # не блокирует поток


	def cluster_get_content(self, path: str) -> bytes | None:
		file = self.cluster[path]
		if type(file) is File:
			return file.read()


	@nonblocking
	def processing(self, client: Socket, ip: str, port: int) -> None:
		if self.debug:
			info(f'Подключение: {ip}:{port}')
		client.settimeout(5.0)

		while True:
			try:
				req = Request.from_socket(client)
			except TimeoutError:
				break
			except ConnectionResetError:
				break
			except:
				raise

			if req is None:
				if self.debug:
					warn(f'Неверный HTTP: {ip}:{port}')
				Response(400).to_socket(client)
				break
				
			if req.path in self.paths:
				if req.method not in self.paths[req.path]:
					Response(400).to_socket(client)
					break
				res = self.paths[req.path][req.method](self, client, req)
				if res is not None:
					res.to_socket(client)
					if 'Connection' in res.headers:
						if res.headers['Connection'] == 'keep-alive':
							continue

			elif (((path := req.path) in self.cluster) or
				((path := req.path + '.html') in self.cluster)):
				data = self.cluster_get_content(path)
				if data is None:
					Response(404).to_socket(client)
				else:
					res = Response(200)
					mimetype = mimetypes.guess_type(path)[0]
					if mimetype is not None:
						res.header('Content-Type', mimetype)
					res.bytes(data)
					res.to_socket(client)

			else:
				Response(404).to_socket(client)
			break

		if self.debug:
			info(f'Отключение: {ip}:{port}')
		client.close()


	def start(self) -> None:
		info('Запуск сервера')
		self.socket: Socket = Socket(AF_INET, SOCK_STREAM)
		self.socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
		self.socket.bind((self.host, self.port))
		self.socket.listen(128)
		self.accepting() # не блокирует поток

		try:
			while True:
				if not self.cluster.update():
					error('Кластер повреждён!')
					break
				sleep(0.5)
			error('Аварийная остановка сервера!')
		except KeyboardInterrupt:
			info('Принудительная остановка сервера')
			if self.database is not None:
				self.database.close()
		except:
			error('Аварийная остановка сервера!')
			raise