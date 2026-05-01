1. СЕРВЕР -> ФРОНТ
1.1 Получение списка растений
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

\\статусы: healthy, unhealthy, warning, critical

\\position берётся из словаря позиций (хранится в формате: 1: {"x": 100, "y": 200, "width": 300, "height": 300}, 2: {"x": 450, "y": 200, "width": 300, "height": 300}, 3: {"x": 800, "y": 200, "width": 300, "height": 300}, ...)



\\растений нет:
```json
{
    "plants": []
}
```

1.2 Получение статуса растений с диагнозом
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

1.3 Получение истории показаний 
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
            "diagnosis": "healthy",
            "confidence": 0.95,
            "image_url": "/data/crop_photos/plant_1_20260422_100000.jpg",
            "created_at": "2026-04-22T12:00:01"
        }
    ]
}
```

1.4 Получение статуса для гостевой страницы
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

1.5 Получение данных для графиков

GET /api/graph/sensors?period=day

Ответ:

```json
{
    "labels": ["2026-04-15", "2026-04-16", "2026-04-17"],
    "temperature": [22.1, 23.5, 24.0],
    "humidity": [60, 65, 62]
}
```

1.6 Получение текущего режима

GET /api/command/mode

Ответ:

```json
{
    "mode": "auto"
}
```

1.7 Получение расписаний
GET /api/schedules

Ответ:

```json
{
    "light": [
        {"start": "08:00", "end": "20:00"}
    ],
    "fan": [
        {"interval_hours": 2, "duration_minutes": 5}
    ],
    "water": [
        {"interval_hours": 6, "duration_minutes": 2}
    ]
}
```

2. ФРОНТ -> СЕРВЕР

2.1-3 Управление поливом/светом/вентилятором
POST /api/command/water
POST /api/command/light
POST /api/command/fan
```json
{
	"state": "on"
	"token": "165aeca1-e2ca-4938-94ee-e0b9e11d53d2"
}   
```

Ответ:
HTTP 200 / 400 / 500

2.4 Авторизация админа

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
    "status": "ok",
    "token": "165aeca1-e2ca-4938-94ee-e0b9e11d53d2",
    "expires_in": 86400
}
```

2.5 Установка режима

POST /api/command/mode


{"mode": "auto"}   // или "manual"
Ответ:

```json
{
    "status": "ok",
    "mode": "auto"
}
```

2.6 Сохранение расписаний

POST /api/schedules

```json
{
    "light": [{"start": "08:00", "end": "20:00"}],
    "fan": [{"interval_hours": 2, "duration_minutes": 5}],
    "water": [{"interval_hours": 6, "duration_minutes": 2}]
}
```

Ответ:

```json
{
    "status": "ok",
    "message": "Schedules saved"
}
```

2.7 Очистка фото больных растений

POST /api/admin/cleanup/sick_plants


{"days": 30}

Ответ:

```json
{
    "status": "ok",
    "deleted_count": 15,
    "message": "Deleted 15 old sick plant photos"
}
```

2.8 Сделать фото

POST/api/admin/make_photo
```json
{
	 "token": "165aeca1-e2ca-4938-94ee-e0b9e11d53d2",
}
```


2.9. Установка режима
POST /api/command/mode

```json
{
	"mode": "auto"
	"token": "165aeca1-e2ca-4938-94ee-e0b9e11d53d2"
}
```

Ответ: HTTP 200/ 400 / 500


3. СТАТУС СЕРВЕРА
GET /api/status

Ответ:

```json
{
    "status": "online",
    "uptime": 3600,
    "db_status": "connected"
}
```


-------

1. ESP -> Сервер (показания датчиков)
POST /api/esp/sensors

```json
{
    "temperature": 23.5,
    "humidity": 65
}
```

2. ESP -> Сервер (запрос команд)

GET /api/esp/get_command

**без тела запроса

3. Сервер -> ESP (команда)

```json
{
    "queue_size": 3,
    "command_id": 123,
    "device": "light",
    "action": "on"
}
```

если нет команд, то "device": "None"

4. ESP -> Сервер (подтверждение команды)
POST /api/esp/command_ask

```json
{
    "command_id": 123,
    "status": "executed"
}
```

Полная схема общения

ESP → Сервер: {"temperature": 23.5, "humidity": 65}

ESP → Сервер: GET /api/esp/command

Сервер → ESP: {"command_id": 123, "device": "light", "action": "on"}

ESP → Сервер: {"command_id": 123, "status": "executed"}




-------

!!!!! Сервер отправляет фото в ML модель

Сервер -> ML модель (HTTP POST):

POST
http://ml_model:5001/analyze

```json
{
    "image_id": "plant_1_20260422_120001.jpg",
    "image_base64": "/9j/4AAQSkZJRg...",
}
```



ML модель -> Сервер (HTTP POST):



POST http://server:8000/api/ml/result

```json
{
    "image_id": "plant_1_20260422_120001.jpg",
    "diagnosis": "healthy",
    "confidence": 0.95
}
```



DEVICE_MAPPING

DEVICE_MAPPING = {
    "AA:BB:CC:DD:EE:FF": {"id": "esp_01", "shelf": 1},
}
