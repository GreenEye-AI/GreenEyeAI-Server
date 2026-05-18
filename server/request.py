from __future__ import annotations
from typing import Any 
from socket import socket as Socket, MSG_PEEK
import json

from .inet import KiB
__all__ = ['Request']


class Request:
	method: str
	path: str
	version: str
	headers: dict[str, str]
	data: bytes

	def __init__(self, method: str = 'GET', path: str = '/') -> None:
		self.method = method
		self.path = path
		self.version = 'HTTP/1.1'
		self.headers = dict()
		self.data = b''
	
	@staticmethod
	def from_socket(client: Socket) -> Request | None:
		req: Request = Request()
		# читаем заголовки HTTP
		data: bytes = client.recv(KiB*4, MSG_PEEK) # опасная функция
		if not data:
			raise ConnectionResetError
		index: int = data.find(b'\r\n\r\n')
		if index < 0:
			return None
		data: bytes = client.recv(index+4)
		data = data[:-4]
		text: str = data.decode('ascii') # опасная функция
		headers: list[str] = text.split('\r\n')

		line: str = headers.pop(0)
		method, path, version = line.split(' ', 2)

		if '?' in path:
			path = path.split('?', 1)[0]

		req.method = method.upper()
		req.path = path
		req.version = version.upper()

		req.headers = dict()
		for header in headers:
			header, content = header.split(': ', 1)
			req.headers[header] = content

		req.data = b''
		if 'Content-Length' in req.headers:
			size: int = int(req.headers['Content-Length'])
			while True:
				if (len(req.data) >= size):
					break
				req.data += client.recv(size - len(req.data))
		return req
	
	def header(self, name: str, value: str) -> Request:
		self.headers[name] = value
		return self
	
	def text(self, data: str) -> Request:
		self.headers['Content-Type'] = 'text/html; charset=utf-8'
		self.data = data.encode('utf8')
		return self
	
	def json(self, data: dict | list) -> Request:
		self.headers['Content-Type'] = 'application/json'
		self.data = json.dumps(data).encode('utf8')
		return self
	
	def get_json(self) -> Any:
		try:
			return json.loads(self.data)
		except:  # noqa: E722
			return None
	
	def to_body(self) -> str:
		line: str = ' '.join([self.method, self.path, self.version])
		return '\r\n'.join([line,] + [f'{k}: {v}' for k, v in self.headers.items()]) + '\r\n\r\n'
	
	def to_text(self) -> str:
		if len(self.data) > 0:
			self.headers['Content-Length'] = str(len(self.data))
		return self.to_body() + self.data.decode('utf8')
	
	def to_bytes(self) -> bytes:
		if len(self.data) > 0:
			self.headers['Content-Length'] = str(len(self.data))
		return self.to_body().encode('ascii') + self.data
	
	def to_socket(self, sock: Socket) -> None:
		sock.send(self.to_bytes())
