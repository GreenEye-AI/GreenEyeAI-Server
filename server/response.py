from __future__ import annotations
from socket import socket as Socket
import json

from .status import STATUS
__all__ = ['Response']


class Response:
	data: bytes
	headers: dict[str, str]

	def __init__(self,
		status: int = 200,
		headers: dict[str, str] | None = None,
		data: bytes | None = None
	) -> None:
		self.status = status

		self.headers = {
			'Connection': 'close'
		}

		if headers is not None:
			for k,v in headers.items():
				self.headers[k] = v

		self.data = b''
		if data is not None:
			self.data = data

	def header(self, name: str, value: str) -> Response:
		self.headers[name] = value
		return self
	
	def bytes(self, data: bytes) -> Response:
		self.data = data
		return self

	def text(self, data: str) -> Response:
		self.headers['Content-Type'] = 'text/plain'
		self.data = data.encode('utf8')
		return self
	
	def html(self, data: str | bytes) -> Response:
		self.header('Content-Type', 'text/html; charset=utf-8')
		if type(data) is str:
			self.data = data.encode('utf8')
		elif type(data) is bytes:
			self.data = data
		return self

	def json(self, data: dict | list) -> Response:
		self.headers['Content-Type'] = 'application/json'
		self.data = json.dumps(data).encode('utf8')
		return self
	
	def to_body(self) -> str:
		line = f'HTTP/1.1 {self.status} {STATUS[self.status]}'
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