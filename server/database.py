from __future__ import annotations
import sqlite3
from threading import Thread, Event
from queue import Queue
from typing import Any


class DataBase(Thread):
	def __init__(self, path: str) -> None:
		super().__init__(daemon=True)
		self.path = path
		self.task_queue = Queue()
		self.start()

	def run(self) -> None:
		self.connection = sqlite3.connect(self.path, isolation_level=None)
		self.cursor = self.connection.cursor()

		while True:
			task = self.task_queue.get()
			if task is None:
				break

			sql, parameters, result_container, event, mode, count = task
			try:
				self.cursor.execute(sql, parameters)
				match mode:
					case 1:
						result_container['data'] = self.cursor.fetchone()
					case 2:
						result_container['data'] = self.cursor.fetchmany(count)
					case 3:
						result_container['data'] = self.cursor.fetchall()
			except Exception as e:
				result_container['error'] = e
			finally:
				if event is not None:
					event.set()  # Разблокируем вызывающий поток
			
			self.task_queue.task_done()

		self.cursor.close()
		self.connection.close()

	def execute(self,
		sql: str,
		parameters: tuple = (),
		mode: int | None = None,
		count: int = 1
	) -> list[Any] | None:
		'''Выполняет запрос и возвращает данные вызывающему потоку'''
		event = (Event() if mode is not None else None)
		result_container = {'data': None, 'error': None}
		self.task_queue.put((sql, parameters, result_container, event, mode, count))
		if event is not None:
			event.wait()

		if result_container['error']:
			raise result_container['error']
		return result_container['data']

	def close(self) -> None:
		self.task_queue.put(None)
		self.join()