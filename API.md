1. СЕРВЕР -> ФРОНТ  

❌ 1. Получение списка растений  

GET /api/plants

GET /api/plants?status=unhealthy

Ответ:

```json
{
	"plants": [
		{
			"plant_id": 1,
			"position": 1,
			"status": "unhealthy",
			"last_update": "2026-04-22T12:00:01"
		}
	]
}
```

статусы: healthy, unhealthy, warning, critical  
position берётся из словаря позиций:
```json
1: {"x": 100, "y": 200, "width": 300, "height": 300},
2: {"x": 450, "y": 200, "width": 300, "height": 300},
3: {"x": 800, "y": 200, "width": 300, "height": 300},
						...
```
растений нет:
```json
{
	"plants": []
}
```

❌ 1.2 Получение статуса растений с диагнозом
GET /api/plants/status

Ответ:

```json
{
	"plants": [
		{
			"plant_id": 1,
			"position": 1,
			"diagnosis": "healthy",
			"last_diagnosis_at": "2026-04-22T10:00:00",
			"photo_url": "/data/crop_photos/plant_1_20260422_100000.jpg"
		}
	]
}
```

❌ 1.3 Получение истории показаний 
GET /api/readings

Параметры: plant_id (обязательно), limit, from_date, to_date

Ответ:

```json
{
	"readings": [
		{
			"id": 1,
			"plant_id": 1,
			"temperature": 23.5,
			"humidity": 65,
			"ph": 6.5,
			"diagnosis": "healthy",
			"confidence": 0.95,
			"image_url": "/data/crop_photos/plant_1_20260422_100000.jpg",
			"created_at": "2026-04-22T12:00:01"
		}
	]
}
```

❌ 1.4 Получение статуса для гостевой страницы
GET /api/guest/status

Ответ:

```json
{
	"temperature": 23.5,
	"humidity": 65,
	"mode": "auto",
	"uptime": 3600
}
```

✅ 1.5 Получение данных для графиков

GET /api/graph/table

```json
{
	"table": "sensors", // water, fan, light или pH
	"seconds": 600 // за посл. 600 сек = 10 минут
}
```

Ответ:

```json
[[1777738253.3134413, 1], [1777738373.3380244, 0], ...] // для water, light, fan
[[1777738253.3134413, 13.0, 65.3], [1777738373.3380244, 12.5, 73.1], ...] // для sensors
```

✅ 1.6 Получение текущего режима

GET /api/command/mode

Ответ:

```json
{
	"mode": "auto"
}
```

✅ 1.7 Получение расписания  

GET /api/schedule

Ответ:

```json
{
	"light": {"start": "08:00", "end": "20:00"},
	"fan": {"interval_hours": 2, "duration_minutes": 5},
	"water": {"interval_hours": 3, "duration_minutes": 10}
}
```

❌ 1.8 Статус сервера  

GET /api/status

Ответ:

```json
{
	"status": "online",
	"uptime": 3600,
	"db_status": "connected"
}
```

✅ 1.9 Последнее состояне релешек  

GET /api/last_state  

Ответ:

```json
{"water": 0, "light": 1, "fan": 1}
```

✅ 1.10. Стрим/видео  

GET /api/stream

Возвращение MIME формата (т.е. кадрового)


2. ФРОНТ -> СЕРВЕР

✅ 2.1 Авторизация админа

POST /api/admin/login

```json
{
	"username": "admin",
	"password": "password123"
}
```

Ответ:

```json
{
	"token": "165aeca1-e2ca-4938-94ee-e0b9e11d53d2",
	"expires_in": 86400
}
```

✅ 2.2-4 Управление поливом/светом/вентилятором

POST /api/command/water

POST /api/command/light

POST /api/command/fan

```json
{
	"token": "165aeca1-e2ca-4938-94ee-e0b9e11d53d2",
	"state": "on"
}   
```

Ответ:
HTTP 200 / 400 / 500

✅ 2.5 Установка режима

POST /api/command/mode

```json
{
	"token": "165aeca1-e2ca-4938-94ee-e0b9e11d53d2",
	"mode": "auto" // или "manual"
}   
```

Ответ:
HTTP 200 / 400 / 500

✅ 2.6 Сохранение расписаний

POST /api/schedule

```json
{
	"token": "165aeca1-e2ca-4938-94ee-e0b9e11d53d2",
	"light": {"start": "08:00", "end": "20:00"},
	"fan": {"interval_hours": 2, "duration_minutes": 5},
	"water": {"interval_hours": 3, "duration_minutes": 10}
}
```

Ответ:
HTTP 200 / 400 / 500

❌ 2.7 Очистка фото больных растений

POST /api/admin/cleanup/sick_plants

```json
{"days": 30}
```
Ответ:

```json
{
	"status": "ok",
	"deleted_count": 15,
	"message": "Deleted 15 old sick plant photos"
}
```

❌ 2.8 Сделать фото

POST/api/admin/make_photo
```json
{
	 "token": "165aeca1-e2ca-4938-94ee-e0b9e11d53d2",
}
```

✅ 2.9. Установка уровня pH

POST /api/ph

```json
{
    "token": "165aeca1-e2ca-4938-94ee-e0b9e11d53d2",
    "level": 6.5
}
```

Ответ:
HTTP 200 / 400 / 500

-------
3. ВЗАИМОДЕЙСТВИЕ С ESP  

✅ 3.1. ESP -> Сервер (показания датчиков)
POST /api/esp/sensors

```json
{
	"temperature": 23.5,
	"humidity": 65
}
```

✅ 3.2. ESP -> Сервер (запрос команд)

GET /api/esp/command

**без тела запроса

✅ 3.3. Сервер -> ESP (команда)

```json
{
	"queue_size": 3,
	"command_id": 123,
	"device": "light",
	"action": "on"
}
```

если нет команд, то "device": "None"

✅ 3.4. ESP -> Сервер (подтверждение команды)
POST /api/esp/command

```json
{
	"command_id": 123
}
```

-------

4. ОБРАБОТКА ФОТО
 
❌ 4.1 Сервер -> ML модель (HTTP POST):  
Сервер отправляет фото в ML модель  
POST ml_model:5001/analyze

```json
{
	"image_id": "plant_1_20260422_120001.jpg",
	"image_base64": "/9j/4AAQSkZJRg...",
}
```



❌ 4.2 ML модель -> Сервер (HTTP POST):

POST server:8000/api/ml/result

```json
{
	"image_id": "plant_1_20260422_120001.jpg",
	"diagnosis": "healthy",
	"confidence": 0.95
}
```


