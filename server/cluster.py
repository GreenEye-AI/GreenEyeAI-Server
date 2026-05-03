from __future__ import annotations
from time import time
from os import listdir
from os.path import isfile, isdir, getmtime

from .logging import info
__all__ = ['File', 'Dir', 'Cluster']


class File:
	path: str
	last: float
	lmod: float
	delay: float
	data: bytes

	def __new__(cls, path: str, delay: float = 5) -> File | None:
		if not isfile(path):
			return None
		file = super().__new__(cls)
		file.path = path
		file.last = 0
		file.lmod = 0
		file.delay = delay
		file.data = b''
		return file
	
	def read(self) -> bytes:
		return self.data
	
	def save(self) -> bool:
		if not isfile(self.path):
			return False
		try:
			with open(self.path, 'wb') as file:
				file.write(self.data)
			return True
		except:  # noqa: E722
			return False
	
	def write(self, data: bytes) -> bool:
		self.data = data 
		return self.save()
	
	def update(self) -> bool:
		if not isfile(self.path):
			return False
		if time() - self.last > self.delay:
			lmod = getmtime(self.path)
			if lmod == self.lmod:
				return True
			try:
				with open(self.path, 'rb') as file:
					self.data = file.read()
				if self.last > 0:
					info('Изменён файл:', self.path)
				self.last = time()
				self.lmod = lmod
			except:  # noqa: E722
				return False
		return True


class Dir:
	path: str
	last: float
	delay: float
	file_delay: float
	paths: dict[str, Dir | File]

	def __new__(cls, path: str, delay: float = 1, file_delay: float = 5) -> Dir | None: 
		if not isdir(path):
			return None
		dir = super().__new__(cls)
		dir.path = path
		dir.last = 0
		dir.delay = delay
		dir.file_delay = file_delay
		dir.paths = dict()
		return dir
	
	def __getitem__(self, path: str) -> Dir | File | None:
		if path.startswith('/'):
			path = path[1:]
		if '/' in path:
			path, opath = path.split('/', 1)
			obj = self.paths.get(path)
			if type(obj) is Dir:
				return obj[opath]
			return None
		else:
			return self.paths.get(path)
		
	def __contains__(self, path: str) -> bool:
		if path.startswith('/'):
			path = path[1:]
		if '/' in path:
			path, opath = path.split('/', 1)
			obj = self.paths.get(path)
			if type(obj) is Dir:
				return opath in obj
			return False
		else:
			return (path in self.paths)
	
	def update(self) -> bool:
		if not isdir(self.path):
			return False
		
		if time() - self.last > self.delay:
			for name in listdir(self.path):
				if name in self.paths:
					if not self.paths[name].update():
						info('Удалён:', self.paths[name].path)
						del self.paths[name]
					continue
				
				opath = f'{self.path}/{name}'

				if isfile(opath):
					file = File(opath, self.file_delay)
					if file is None:
						continue
					file.update()
					self.paths[name] = file
					info('Добавлен файл:', opath)

				elif isdir(opath):
					dir = Dir(opath, self.delay, self.file_delay)
					if dir is None:
						continue
					dir.update()
					self.paths[name] = dir
					info('Добавлена директория:', opath)

		return True


class Cluster:
	main: Dir | None

	def __new__(cls,
		path: str,
		dir_delay: float = 1,
		file_delay: float = 5
	) -> Cluster | None:
		if path.startswith('./'):
			path = path[2:]
		main = Dir(path, dir_delay, file_delay)
		if main is None:
			return None
		cl = super().__new__(cls)
		cl.main = main
		return cl

	def __getitem__(self, path: str) -> Dir | File | None:
		if self.main is None:
			return None
		return self.main[path]
	
	def __contains__(self, path: str) -> bool:
		if self.main is None:
			return False
		return path in self.main

	def update(self) -> bool:
		if self.main is None:
			return False
		if not self.main.update():
			self.main = None
			return False
		return True