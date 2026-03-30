from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from datetime import datetime
import os
import uuid
import sqlite3
from threading import Lock
import json
from enum import Enum
from typing import Dict, List, Optional, Any
import paho.mqtt.client as mqtt
import time

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler('server.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class SensorType(Enum):
    """Перечисление типов сенсоров"""
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    PH = "ph"
    EC = "ec"
    LIGHT = "light"
    WATER_LEVEL = "water_level"

class PlantHealthStatus(Enum):
    """Статусы здоровья растения"""
    HEALTHY = "healthy"
    WARNING = "warning"
    DISEASED = "diseased"
    CRITICAL = "critical"

class ESP826 """Класс для команд ESP8266"""
    def __init__(self, command: str, params: Dict[str, Any] = None, device_id: str = None):
        self.command = command
        self.params = params or {}
        self.device_id = device_id or "default_esp"
        self.timestamp = datetime.now().isoformat()
        self.message_id = str(uuid.uuid4())

class DatabaseManager:
    """Класс управления базой данных"""
    
    def __init__(self, db_path: str = 'hydro_smart.db'):
        self.db_path = db_path
        self.lock = Lock()
        self.init_db()
    
    def init_db(self):
        """Инициализация базы данных"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Таблица для показаний сенсоров
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sensor_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sensor_type TEXT NOT NULL,
                    value REAL NOT NULL,
                    unit TEXT,
                    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    plant_id TEXT,
                    device_id TEXT
                )
            ''')
            
            # Таблица для результатов ML
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ml_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_id TEXT NOT NULL,
                    diagnosis TEXT NOT NULL,
                    confidence REAL,
                    health_status TEXT,
                    recommendations TEXT,
                    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    plant_id TEXT
                )
            ''')
            
            # Таблица для команд ESP8266
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS esp_commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    command_type TEXT NOT NULL,
                    params TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    plant_id TEXT,
                    device_id TEXT,
                    status TEXT DEFAULT 'pending',
                    executed_at TIMESTAMP
                )
            ''')
            
            # Таблица для статусов растений
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS plant_statuses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plant_id TEXT UNIQUE NOT NULL,
                    device_id TEXT,
                    health_status TEXT DEFAULT 'healthy',
                    last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    issues TEXT,
                    last_sensor_reading_id INTEGER,
                    last_ml_result_id INTEGER
                )
            ''')
            
            # Таблица для статусов ESP8266 устройств
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS esp_devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT UNIQUE NOT NULL,
                    device_name TEXT,
                    ip_address TEXT,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'offline',
                    plant_id TEXT
                )
            ''')
            
            conn.commit()
            logging.info("Database initialized successfully")

    def save_sensor_reading(self, sensor_type: str, value: float, unit: str, 
                          plant_id: str = None, device_id: str = None):
        """Сохранение показания сенсора в базу данных"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO sensor_readings (sensor_type, value, unit, plant_id, device_id)
                    VALUES (?, ?, ?, ?, ?)
                ''', (sensor_type, value, unit, plant_id, device_id))
                
                reading_id = cursor.lastrowid
                conn.commit()
                
                logging.info(f"Saved sensor reading: {sensor_type}={value}{unit}, "
                           f"plant_id={plant_id}, device_id={device_id}")
                return reading_id

    def save_ml_result(self, image_id: str, diagnosis: str, confidence: float, 
                      health_status: str, recommendations: str, plant_id: str = None):
        """Сохранение результата ML анализа в базу данных"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO ml_results (image_id, diagnosis, confidence, health_status, recommendations, plant_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (image_id, diagnosis, confidence, health_status, recommendations, plant_id))
                
                result_id = cursor.lastrowid
                conn.commit()
                
                logging.info(f"Saved ML result: {diagnosis}, confidence={confidence}, plant_id={plant_id}")
                return result_id

    def update_plant_status(self, plant_id: str, health_status: str, issues: str = None, device_id: str = None):
        """Обновление статуса растения"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Проверяем существует ли запись
                cursor.execute('SELECT id FROM plant_statuses WHERE plant_id = ?', (plant_id,))
                existing = cursor.fetchone()
                
                if existing:
                    cursor.execute('''
                        UPDATE plant_statuses 
                        SET health_status = ?, issues = ?, last_update = CURRENT_TIMESTAMP, device_id = ?
                        WHERE plant_id = ?
                    ''', (health_status, issues, device_id, plant_id))
                else:
                    cursor.execute('''
                        INSERT INTO plant_statuses (plant_id, device_id, health_status, issues)
                        VALUES (?, ?, ?, ?)
                    ''', (plant_id, device_id, health_status, issues))
                
                conn.commit()
                logging.info(f"Updated plant status: {plant_id} -> {health_status}")

    def register_esp_device(self, device_id: str, device_name: str = None, 
                           ip_address: str = None, plant_id: str = None):
        """Регистрация ESP8266 устройства"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO esp_devices 
                    (device_id, device_name, ip_address, last_seen, status, plant_id)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP, 'online', ?)
                ''', (device_id, device_name, ip_address, plant_id))
                
                conn.commit()
                logging.info(f"Registered ESP8266 device: {device_id}")

    def update_esp_device_status(self, device_id: str, status: str = 'online', 
                                ip_address: str = None):
        """Обновление статуса ESP8266 устройства"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                update_fields = ['last_seen = CURRENT_TIMESTAMP']
                params = []
                
                if status:
                    update_fields.append('status = ?')
                    params.append(status)
                
                if ip_address:
                    update_fields.append('ip_address = ?')
                    params.append(ip_address)
                
                params.append(device_id)
                
                query = f"UPDATE esp '.join(update_fields)} WHERE device_id = ?"
                cursor.execute(query, params)
                
                conn.commit()
                logging.info(f"Updated ESP8266 device status: {device_id} -> {status}")

    def get_plant_status(self, plant_id: str) -> Dict:
        """Получение статуса растения"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT plant_id, health_status, issues, last_update, device_id
                    FROM plant_statuses 
                    WHERE plant_id = ?
                ''', (plant_id,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        'plant_id': row[0],
                        'health_status': row[1],
                        'issues': row[2],
                        'last_update': row[3],
                        'device_id': row[4]
                    }
                return None

    def get_plant_statuses(self) -> List[Dict]:
        """Получение всех статусов растений"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT plant_id, health_status, issues, last_update, device_id
                    FROM plant_statuses
                    ORDER BY last_update DESC
                ''')
                
                rows = cursor.fetchall()
                return [
                    {
                        'plant_id': row[0],
                        'health_status': row[1],
                        'issues': row[2],
                        'last_update': row[3],
                        'device_id': row[4]
                    } for row in rows
                ]

    def get_problematic_plants(self) -> List[Dict]:
        """Получение растений с проблемами (warning, diseased, critical)"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT plant_id, health_status, issues, last_update, device_id
                    FROM plant_statuses
                    WHERE health_status IN ('warning', 'diseased', 'critical')
                    ORDER BY last_update DESC
                ''')
                
                rows = cursor.fetchall()
                return [
                    {
                        'plant_id': row[0],
                        'health_status': row[1],
                        'issues': row[2],
                        'last_update': row[3],
                        'device_id': row[4]
                    } for row in rows
                ]

    def get_sensor_readings(self, plant_id: str = None, device_id: str = None, 
                           sensor_type: str = None, limit: int = 100) -> List[Dict]:
        """Получение показаний сенсоров"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                query = '''
                    SELECT id, sensor_type, value, unit, received_at, plant_id, device_id
                    FROM sensor_readings
                '''
                params = []
                
                conditions = []
                if plant_id:
                    conditions.append('plant_id = ?')
                    params.append(plant_id)
                if device_id:
                    conditions.append('device_id = ?')
                    params.append(device_id)
                if sensor_type:
                    conditions.append('sensor_type = ?')
                    params.append(sensor_type)
                
                if conditions:
                    query += ' WHERE ' + ' AND '.join(conditions)
                
                query += ' ORDER BY received_at DESC LIMIT ?'
                params.append(limit)
                
                cursor = conn.cursor()
                cursor.execute(query, params)
                
                rows = cursor.fetchall()
                return [
                    {
                        'id': row[0],
                        'sensor_type': row[1],
                        'value': row[2],
                        'unit': row[3],
                        'received_at': row[4],
                        'plant_id': row[5],
                        'device_id': row[6]
                    } for row in rows
                ]

    def get_ml_results(self, plant_id: str = None, limit: int = 100) -> List[Dict]:
        """Получение результатов ML анализа"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                query = '''
                    SELECT id, image_id, diagnosis, confidence, health_status, recommendations, received_at, plant_id
                    FROM ml_results
                '''
                params = []
                
                if plant_id:
                    query += ' WHERE plant_id = ?'
                    params.append(plant_id)
                
                query += ' ORDER BY received_at DESC LIMIT ?'
                params.append(limit)
                
                cursor = conn.cursor()
                cursor.execute(query, params)
                
                rows = cursor.fetchall()
                return [
                    {
                        'id': row[0],
                        'image_id': row[1],
                        'diagnosis': row[2],
                        'confidence': row[3],
                        'health_status': row[4],
                        'recommendations': row[5],
                        'received_at': row[6],
                        'plant_id': row[7]
                    } for row in rows
                ]

    def save_esp_command(self, command_type: str, params: Dict, plant_id: str, device_id: str):
        """Сохранение команды ESP8266 в базу данных"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO esp_commands (command_type, params, plant_id, device_id)
                    VALUES (?, ?, ?, ?)
                ''', (command_type, json.dumps(params), plant_id, device_id))
                
                command_id = cursor.lastrowid
                conn.commit()
                
                logging.info(f"Saved ESP command: {command_type}, device: {device_id}")
                return command_id

    def get_pending_commands(self, device_id: str, limit: int = 10) -> List[Dict]:
        """Получение ожидающих выполнения команд для устройства"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, command_type, params, sent_at, plant_id, device_id
                    FROM esp_commands
                    WHERE device_id = ? AND status = 'pending'
                    ORDER BY sent_at ASC
                    LIMIT ?
                ''', (device_id, limit))
                
                rows = cursor.fetchall()
                return [
                    {
                        'id': row[0],
                        'command_type': row[1],
                        'params': json.loads(row[2]),
                        'sent_at': row[3],
                        'plant_id': row[4],
                        'device_id': row[5]
                    } for row in rows
                ]

    def mark_command_executed(self, command_id: int):
        """Отметка команды как выполненной"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE esp_commands
                    SET status = 'executed', executed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (command_id,))
                
                conn.commit()
                logging.info(f"Marked command {command_id} as executed")

class MQTTManager:
    """Класс управления MQTT для связи с ESP8266"""
    
    def __init__(self, broker_host: str = "localhost", broker_port: int = 1883):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        
        # Подписка на топики
        self.esp_topics = {}  # device_id -> topic
        self.command_callbacks = {}
        
    def on_connect(self, client, userdata, flags, rc):
        """Обработчик подключения к MQTT брокеру"""
        if rc == 0:
            logging.info("Connected to MQTT broker")
            # Подписываемся на топики для получения данных от ESP
            self.client.subscribe("esp8266/+/data")
            self.client.subscribe("esp8266/+/status")
            self.client.subscribe("esp8266/+/commands/response")
        else:
            logging.error(f"Failed to connect to MQTT broker, return code {rc}")
    
    def on_disconnect(self, client, userdata, rc):
        """Обработчик отключения от MQTT брокера"""
        logging.warning("Disconnected from MQTT broker")
    
    def on_message(self, client, userdata, msg):
        """Обработчик входящих сообщений MQTT"""
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            logging.error(f"Invalid JSON in MQTT message: {payload}")
            return
        
        logging.info(f"MQTT message received: {topic} -> {data}")
        
        if topic.startswith("esp8266/") and "/data" in topic:
            # Данные сенсора от ESP8266
            parts = topic.split('/')
            if len(parts) >= 3:
                device_id = parts[1]
                self.handle_esp_data(device_id, data)
        
        elif topic.startswith("esp8266/") and "/status" in topic:
            # Статус ESP8266 устройства
            parts = topic.split('/')
            if len(parts) >= 3:
                device_id = parts[1]
                self.handle_esp_status(device_id, data)
        
        elif topic.startswith("esp8266/") and "/commands/response" in topic:
            # Ответ на команду от ESP8266
            parts = topic.split('/')
            if len(parts) >= 4:
                device_id = parts[1]
                command_id = parts[3]
                self.handle_command_response(device_id, command_id, data)
    
    def handle_esp_data(self, device_id: str,  Dict):
        """Обработка данных от ESP8266"""
        # Регистрируем устройство если еще не зарегистрировано
        db_manager.register_esp_device(device_id)
        
        # Обновляем статус устройства
        db_manager.update_esp_device_status(device_id, 'online')
        
        # Сохраняем показания сенсоров
        if 'sensors' in 
            for sensor_data in data['sensors']:
                sensor_type = sensor_data.get('type')
                value = sensor_data.get('value')
                unit = sensor_data.get('unit', '')
                plant_id = sensor_data.get('plant_id', f'plant_{device_id}')
                
                if sensor_type and value is not None:
                    db_manager.save_sensor_reading(
                        sensor_type, value, unit, plant_id, device_id
                    )
    
    def handle_esp_status(self, device_id: str, status_ Dict):
        """Обработка статуса ESP8266 устройства"""
        status = status_data.get('status', 'online')
        ip_address = status_data.get('ip')
        plant_id = status_data.get('plant_id')
        
        db_manager.update_esp_device_status(device_id, status, ip_address)
        
        if plant_id:
            # Обновляем статус растения если есть проблемы
            if status == 'error':
                db_manager.update_plant_status(plant_id, 'warning', 'Device communication error')
    
    def handle_command_response(self, device_id: str, command_id: str, response: Dict):
        """Обработка ответа на команду от ESP8266"""
        success = response.get('success', False)
        message = response.get('message', '')
        
        logging.info(f"Command response from {device_id}: {command_id}, success: {success}")
        
        # В реальности по ID и обновить её статус
        # Это требует дополнительной логики хранения соответствия команд
    
    def start(self):
        """Запуск MQTT клиента"""
        try:
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            logging.info("MQTT manager started")
        except Exception as e:
            logging.error(f"Failed to start MQTT manager: {e}")
    
    def stop(self):
        """Остановка MQTT клиента"""
        self.client.loop_stop()
        self.client.disconnect()
        logging.info("MQTT manager stopped")
    
    def send_command(self, device_id: str, command: ESP8266Command):
        """Отправка команды на ESP8266 через MQTT"""
        topic = f"esp8266/{device_id}/commands"
        
        command_payload = {
            'command': command.command,
            'params': command.params,
            'message_id': command.message_id,
            'timestamp': command.timestamp
        }
        
        try:
            result = self.client.publish(topic, json.dumps(command_payload))
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logging.info(f"Command sent to {device_id}: {command.command}")
                
                # Сохраняем команду в базу данных
                db_manager.save_esp_command(
                    command.command,
                    command.params,
                    command.plant_id or f'plant_{device_id}',
                    device_id
                )
                
                return True
            else:
                logging.error(f"Failed to send command to {device_id}: {result.rc}")
                return False
        except Exception as e:
            logging.error(f"Error sending command to {device_id}: {e}")
            return False

class MLService:
    """Сервис для имитации работы ML модели"""
    
    @staticmethod
    def analyze_image(image_path: str) -> Dict[str, Any]:
        """
        Имитация анализа изображения
        
        Args:
            image_path: путь к изображению
            
        Returns:
            Словарь с результатами анализа
        """
        import random
        
        # Случайные диагнозы для тестирования
        diagnoses = [
            "Healthy plant",
            "Nitrogen deficiency detected",
            "Fungal infection present",
            "Water stress observed",
            "Pest damage identified",
            "Phosphorus deficiency",
            "Potassium deficiency"
        ]
        
        # Случайные статусы здоровья
        health_statuses = ["healthy", "warning", "diseased", "critical"]
        
        # Случайные рекомендации
        recommendations = [
            "Increase watering frequency",
            "Apply nitrogen-rich fertilizer",
            "Treat with fungicide",
            "Reduce light exposure",
            "Check drainage system",
            "Monitor pH levels closely",
            "Adjust nutrient solution concentration"
        ]
        
        # Случайный выбор
        diagnosis = random.choice(diagnoses)
        health_status = random.choice(health_statuses)
        confidence = round(random.uniform(0.6, 0.99), 2)
        rec_count = random.randint(1, 3)
        selected_recs = random.sample(recommendations, rec_count)
        
        result = {
            "diagnosis": diagnosis,
            "health_status": health_status,
            "confidence": confidence,
            "recommendations": selected_recs,
            "analysis_time": datetime.now().isoformat()
        }
        
        logging.info(f"ML analysis completed for {image_path}: {result}")
        return result

class NotificationManager:
    """Менеджер уведомлений"""
    
    def __init__(self):
        self.notifications = []
    
    def send_notification(self, plant_id: str, health_status: str, message: str, 
                         severity: str = "info", device_id: str = None):
        """
        Отправка уведомления
        
        Args:
            plant_id: ID растения
            health_status: статус здоровья
            message: текст сообщения
            severity: уровень важности (info, warning, error, critical)
            device_id: ID устройства (опционально)
        """
        notification = {
            "id": str(uuid.uuid4()),
            "plant_id": plant_id,
            "device_id": device_id,
            "health_status": health_status,
            "message": message,
            "severity": severity,
            "timestamp": datetime.now().isoformat()
        }
        
        self.notifications.append(notification)
        logging.info(f"Notification sent: {message} for plant {plant_id}")
        
        # В реальности здесь будет отправка через WebSocket или другую систему
        return notification
    
    def get_notifications(self, plant_id: str = None, device_id: str = None, 
                         limit: int = 50) -> List[Dict]:
        """Получение уведомлений"""
        filtered = self.notifications
        
        if plant_id:
            filtered = [n for n in filtered if n["plant_id"] == plant_id]
        if device_id:
            filtered = [n for n in filtered if n["device_id"] == device_id]
        
        return sorted(filtered, key=lambda x: x["timestamp"], reverse=True)[:limit]

    def get_problematic_notifications(self, limit: int = 50) -> List[Dict]:
        """Получение уведомлений о проблемах (warning, error, critical)"""
        problematic = [
            n for n in self.notifications 
            if n["severity"] in ["warning", "error", "critical"]
        ]
        return sorted(problematic, key=lambda x: x["timestamp"], reverse=True)[:limit]

# Инициализация приложения
app = Flask(__name__)
CORS(app)

# Настройки
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Инициализация компонентов
db_manager = DatabaseManager()
mqtt_manager = MQTTManager(broker_host="localhost", broker_port=1883)  # Настройте под ваш MQTT брокер
ml_service = MLService()
notification_manager = NotificationManager()

def add_log(level: str, message: str, details: str = None):
    """
    Добавление записи в лог
    
    Args:
        level: уровень логирования (INFO, WARNING, ERROR)
        message: сообщение
        details: дополнительная информация
        
    Returns:
        Словарь с информацией о логе
    """
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'level': level,
        'message': message,
        'details': details
    }
    
    if level == 'INFO':
        logging.info(message)
    elif level == 'WARNING':
        logging.warning(message)
    elif level == 'ERROR':
        logging.error(message)
    
    return log_entry

def validate_sensor_data( Dict) -> tuple[bool, str]:
    """
    Валидация данных сенсора
    
    Args:
         словарь с данными сенсора
        
    Returns:
        tuple: (успешно, сообщение об ошибке)
    """
    required_fields = ['sensor', 'value']
    missing_fields = [field for field in required_fields if field not in data or data[field] is None]
    
    if missing_fields:
        return False, f"Missing required fields: {missing_fields}"
    
    sensor_type = data.get('sensor')
    if sensor_type not in [e.value for e in SensorType]:
        return False, f"Invalid sensor type: {sensor_type}. Valid types: {[e.value for e in SensorType]}"
    
    try:
        value = float(data['value'])
        if value < -1000 or value > 1000:  # разумные пределы для сенсорных данных
            return False, f"Value out of range: {value}"
    except (ValueError, TypeError):
        return False, f"Invalid value type: {data['value']}"
    
    return True, "Valid"

def determine_plant_health_status(sensor_ List[Dict], ml_result: Dict = None) -> tuple[str, str]:
    """
    Определение статуса здоровья растения на основе сенсорных данных и ML результата
    
    Args:
        sensor_ список последних показаний сенсоров
        ml_result: результат ML анализа (опционально)
        
    Returns:
        tuple: (health_status, issues_description)
    """
    health_status = PlantHealthStatus.HEALTHY.value
    issues = []
    
    # Анализ сенсорных данных
    for reading in sensor_
        sensor_type = reading['sensor_type']
        value = reading['value']
        
        # Проверка критических значений
        if sensor_type == SensorType.TEMPERATURE.value:
            if value < 10 or value > 35:
                issues.append(f"Temperature out of range: {value}°C")
                health_status = PlantHealthStatus.WARNING.value
        elif sensor_type == SensorType.HUMIDITY.value:
            if value < 30 or value > 80:
                issues.append(f"Humidity out of range: {value}%")
                if health_status == PlantHealthStatus.HEALTHY.value:
                    health_status = PlantHealthStatus.WARNING.value
        elif sensor_type == SensorType.PH.value:
            if value < 5.0 or value > 8.0:
                issues.append(f"pH out of range: {value}")
                health_status = PlantHealthStatus.WARNING.value
        elif sensor_type == SensorType.EC.value:
            if value > 3.0:  # высокая электропроводность может указывать на перекорм
                issues.append(f"High EC level: {value} dS/m")
                health_status = PlantHealthStatus.WARNING.value
    
    # Обработка ML результата если доступен
    if ml_result and ml_result.get('health_status') != PlantHealthStatus:
        ml_health = ml_result['health_status']
        if ml_health == PlantHealthStatus.CRITICAL.value:
            health_status = PlantHealthStatus.CRITICAL.value
        elif ml_health == PlantHealthStatus.DISEASED.value and health_status != PlantHealthStatus.CRITICAL.value:
            health_status = PlantHealthStatus.DISEASED.value
        elif ml_health == PlantHealthStatus.WARNING.value and health_status == PlantHealthStatus.HEALTHY.value:
            health_status = PlantHealthStatus.WARNING.value
        
        if ml_result.get('recommendations'):
            issues.extend(ml_result['recommendations'])
    
    # Если есть серьезные проблемы, повышаем статус
    critical_issues = [issue for issue in issues if any(keyword in issue.lower() for keyword in 
                                                     ['fungal', 'pest', 'disease', 'infection', 'critical'])]
    if critical_issues:
        health_status = PlantHealthStatus.CRITICAL.value
    
    return health_status, '; '.join(issues) if issues else "All parameters normal"

@app.route('/data', methods=['POST'])
def receive_data():
    """
    Получение данных от ESP8266 устройства через HTTP
    
    Request body:
    {
        "device_id": "esp_device_123",
        "sensors": [
            {
                "type": "temperature|humidity|ph|ec|light|water_level",
                "value": number,
                "unit": string,
                "plant_id": string (optional)
            }
        ]
    }
    
    Response:
    {
        "status": "ok|error",
        "message": string,
        "received_at": ISO timestamp
    }
    """
    try:
        data = request.get_json()
        
        if not 
            add_log('ERROR', 'No JSON data received')
            return jsonify({
                'status': 'error', 
                'message': 'No JSON data received',
                'received_at': datetime.now().isoformat()
            }), 400
        
        device_id = data.get('device_id', 'unknown_esp')
        sensors = data.get('sensors', [])
        
        if not sensors:
            add_log('ERROR', 'No sensor data provided', str(data))
            return jsonify({
                'status': 'error',
                'message': 'No sensor data provided',
                'received_at': datetime.now().isoformat()
            }), 400
        
        # Регистрируем устройство
        db_manager.register_esp_device(device_id)
        db_manager.update_esp_device_status(device_id, 'online')
        
        plant_ids = set()
        
        # Обработка данных каждого сенсора
        for sensor_data in sensors:
            is_valid, error_msg = validate_sensor_data(sensor_data)
            if not is_valid:
                add_log('WARNING', f'Sensor data validation failed: {error_msg}', str(sensor_data))
                continue  # Пропускаем невалидные данные
            
            sensor_type = sensor_data.get('sensor')
            value = float(sensor_data.get('value'))
            unit = sensor_data.get('unit', '')
            plant_id = sensor_data.get('plant_id', f'plant_{device_id}')
            
            # Сохранение в базу данных
            reading_id = db_manager.save_sensor_reading(sensor_type, value, unit, plant_id, device_id)
            plant_ids.add(plant_id)
        
 статуса для каждого растения
        for plant_id in plant_ids:
            # Получение последних показаний для анализа состояния
            recent_readings = db_manager.get_sensor_readings(plant_id=plant_id, device_id=device_id, limit=10)
            
            # Получение последнего ML результата
            ml_results = db_manager.get_ml_results(plant_id=plant_id, limit=1)
            latest_ml_result = ml_results[0] if ml_results else None
            
            # Определение статуса здоровья растения
            health_status, issues = determine_plant_health_status(recent_readings, latest_ml_result)
            
            # Обновление статуса растения в базе
            db_manager.update_plant_status(plant_id, health_status, issues, device_id)
            
            # Отправка уведомления если статус изменился на проблемный
            if health_status in [PlantHealthStatus.WARNING.value, PlantHealthStatus.DISEASED.value, 
                               PlantHealthStatus.CRITICAL.value]:
                severity_map = {
                    PlantHealthStatus.WARNING.value: "warning",
                    PlantHealthStatus.DISEASED.value: "error", 
                    PlantHealthStatus.CRITICAL.value: "critical"
                }
                severity = severity_map.get(health_status, "warning")
                
                notification_manager.send_notification(
                    plant_id=plant_id,
                    health_status=health_status,
                    message=f"Plant health alert: {issues}" if issues else f"Plant status changed to {health_status}",
                    severity=severity,
                    device_id=device_id
                )
        
        add_log('INFO', f"Data received from ESP8266: {device_id}", 
                f"Sensors: {len(sensors)}, Plants affected: {len(plant_ids)}")
        
        return jsonify({
            'status': 'ok',
            'message': 'Data received and processed',
            'received_at': datetime.now().isoformat(),
            'device_id': device_id,
            'processedensors)
        }), 201
        
    except ValueError as e:
        add_log('ERROR', f"Invalid data format: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Invalid data format: {str(e)}',
            'received_at': datetime.now().isoformat()
        }), 400
    except Exception as e:
        add_log('ERROR', f"Error processing sensor  {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Internal server error: {str(e)}',
            'received_at': datetime.now().isoformat()
        }), 500

@app.route('/esp/command', methods=['POST'])
def send_command_to_esp():
    """
    Отправка команды на ESP8266 устройство
    
    Request body:
    {
        "command": "turn_on_light|turn_off_light|water_plants|stop_watering|set_ph|set_ec|get_status",
        "params": {"duration": 10, "amount": 50, "target_value": 6.5},
        "device_id": string,
        "plant_id": string (optional)
    }
    
    Response:
    {
        "status": "ok|error",
        "message": string,
        "command_id": number
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No JSON data received',
                'received_at': datetime.now().isoformat()
            }), 400
        
        command = data.get('command')
        params = data.get('params', {})
        device_id = data.get('device_id')
        plant_id = data.get('plant_id', f'plant_{device_id}' if device_id else 'default_plant')
        
        if not command or not device_id:
            return jsonify({
                'status': 'error',
                'message': 'Command and device_id are required',
                'received_at': datetime.now().isoformat()
            }), 400
        
        # Проверяем, что устройство зарегистрировано
        # (в реальности можно добавить проверку статуса устройства)
        
        # Создаем объект команды
        esp_command = ESP8266Command(command, params, device_id)
        
        # Отправляем команду через MQTT
        success = mqtt_manager.send_command(device_id, esp_command)
        
        if success:
            return jsonify({
                'status': 'ok',
                'message': 'Command sent to ESP8266',
                'command_id': esp_command.message_id,
                'received_at': datetime.now().isoformat()
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to send command to ESP8266',
                'received_at': datetime.now().isoformat()
            }), 500
        
    except Exception as e:
        add_log('ERROR', f"Error sending command to ESP8266: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to send command: {str(e)}',
            'received_at': datetime.now().isoformat()
        }), 500

@app.route('/esp/devices', methods=['GET'])
def get_esp_devices():
    """
    Получение списка ESP8266 устройств
    
    Response:
    {
        "status": "ok",
        "count": number,
        "devices": [device_object]
    }
    """
    try:
        with db_manager.lock:
            with sqlite3.connect(db_manager.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT device_id, device_name, ip_address, last_seen, status, plant_id
                    FROM esp_devices
                    ORDER BY last_seen DESC
                rows = cursor.fetchall()
                devices = [
                    {
                        'device_id': row[0],
                        'device_name': row[1],
                        'ip_address': row[2],
                        'last_seen': row[3],
                        'status': row[4],
                        'plant_id': row[5]
                    } for row in rows
                ]
        
        return jsonify({
            'status': 'ok',
            'count': len(devices),
            'devices': devices
        }), 200
        
    except Exception as e:
        add_log('ERROR', f"Error getting ESP devices: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to retrieve devices: {str(e)}'
        }), 500

@app.route('/esp/device/<device_id>/commands', methods=['GET'])
def get_pending_commands(device_id: str):
    """
    Получение ожидающих команд для ESP8266 устройства
    
    Path parameter:
    - device_id: string
    
    Response:
    {
        "status": "ok",
        "count": number,
        "commands": [command_object]
    }
    """
    try:
        pending_commands = db_manager.get_pending_commands(device_id)
        
        return jsonify({
            'status': 'ok',
            'count': len(pending_commands),
            'commands': pending_commands
        }), 200
        
    except Exception as e:
        add_log('ERROR', f"Error getting pending commands for {device_id}: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to retrieve commands: {str(e)}'
        }), 500

@app.route('/upload_image', methods=['POST'])
def upload_image():
    """
    Загрузка изображения для ML анализа
    
    Request form:
    - image: файл изображения
    - device_id: string (optional)
    - plant_id: string (optional)
    
    Response:
    {
        "status": "ok|error",
        "message": string,
        "image_path": string,
        "ml_result": ml_result_object,
        "timestamp": ISO timestamp
    }
    """
    try:
        if 'image' not in request.files:
            add_log('ERROR', 'No image file in request')
            return jsonify({
                'status': 'error',
                'message': 'No image file provided'
            }), 400
        
        file = request.files['image']
        
        if file.filename == '':
            add_log('ERROR', 'Empty filename provided')
            return jsonify({
                'status': 'error',
                'message': 'Empty filename'
            }), 400
        
        # Проверка типа файла
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
        if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
            add_log('ERROR', f'Invalid file type: {file.filename}')
            return jsonify({
                'status': 'error',
                'message': f'Invalid file type. Allowed: {allowed_extensions}'
            }), 400
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"photo_{timestamp}_{uuid.uuid4().hex[:8]}.jpg"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        file.save(filepath)
        
        # Получение параметров из формы
        device_id = request.form.get('device_id', 'unknown_esp')
        plant_id = request.form.get('plant_id', f'plant_{device_id}')
        
        # Регистрируем устройство если нужно
        db_manager.register_esp_device(device_id)
        
        # Анализ изображения с помощью ML
        ml_result = ml_service.analyze_image(filepath)
        
        # параметров из результата ML
        diagnosis = ml_result.get('diagnosis', 'Unknown')
        confidence = ml_result.get('confidence', 0.0)
        health_status = ml_result.get('health_status', PlantHealthStatus.HEALTHY.value)
        recommendations = '; '.join(ml_result.get('recommendations', []))
        
        # Сохранение результата ML в базу данных
        result_id = db_manager.save_ml_result(
            image_id=filename,
            diagnosis=diagnosis,
            confidence health_status=health_status,
            recommendations=recommendations,
            plant_id=plant_id
        )
        
        # Обновление статуса растения
        db_manager.update_plant_status(plant_id, health_status, recommendations, device_id)
        
        # Отправка уведомления если есть проблемы
        if health_status in [PlantHealthStatus.WARNING.value, PlantHealthStatus.DISEASED.value, 
                           PlantHealthStatus.CRITICAL.value]:
            severity_map = {
                PlantHealthStatus.WARNING.value: "warning",
                PlantHealthStatus.DISEASED.value: "error",
                PlantHealthStatus.CRITICAL.value: "critical"
            }
            severity = severity_map.get(health_status, "warning")
            
            notification_manager.send_notification(
                plant_id=plant_id,
                health_status=health_status,
                message=f"Image analysis detected: {diagnosis}",
                severity=severity,
                device_id=device_id
            )
        
        add_log('INFO', f"Image uploaded and analyzed", 
                f"File: {filename}, Device: {device_id}, Diagnosis: {diagnosis}")
        
        return jsonify({
            'status': 'ok',
            'message': 'Image uploaded and analyzed',
            'image_path': filepath,
            'ml_result': ml_result,
            'received_at': datetime.now().isoformat()
        }), 201
        
    except Exception as e:
        add_log('ERROR', f"Error uploading and analyzing image: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Upload failed: {str(e)}',
            'received_at': datetime.now().isoformat()
        }), 500

@app.route('/ml_result', methods=['POST'])
def receive_ml_result():
    """
    Получение результата ML анализа (для интеграции с внешней ML системой)
    
    Request body:
    {
        "image_id": string,
        "diagnosis": string,
        "confidence": number,
        "health_status": "healthy|warning|diseased|critical",
        "recommendations": [string],
        "plant_id": string,
        "device_id": string (optional)
    }
    
    Response:
    {
        "status": "ok|error",
        "message": string,
        "received_at": ISO timestamp
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            add_log('ERROR', 'No JSON data received for ML result')
            return jsonify({
                'status': 'error',
                'message': 'No JSON data received'
            }), 400
        
        image_id = data.get('image_id')
        diagnosis = data.get('diagnosis')
        confidence = data.get('confidence', 0.0)
        health_status = data.get('health_status', PlantHealthStatus.HEALTHY.value)
        recommendations = data.get('recommendations', [])
        plant_id = data.get('plant_id', 'default_plant')
        device_id = data.get('device_id')
        
        if not image_id or not diagnosis:
            add_log('ERROR', 'Missing required fields: image_id or diagnosis', str(data))
            return jsonify({
                'status': 'error',
                'message': 'Missing image_id or diagnosis'
            }), 400
        
        # Проверка корректности health_status
        valid_statuses = [status.value for status in PlantHealthStatus]
        if health_status not in valid_statuses:
            health_status = PlantHealthStatus.HEALTHY.value  # значение по умолчанию
        
        # Сохранение в базу данных
        result_id = db_manager.save_ml_result(
            image_id=image_id,
            diagnosis=diagnosis,
            confidence=confidence,
            health_status=health_status,
            recommendations='; '.join(recommendations) if recommendations else '',
            plant_id=plant_id
        )
        
        # Обновление статуса растения
        issues = '; '.join(recommendations) if recommendations else diagnosis
        db_manager.update_plant_status(plant_id, health_status, issues, device_id)
        
        # Отправка уведомления при проблемах
        if health_status in [PlantHealthStatus.WARNING.value, PlantHealthStatus.DISEASED.value, 
                           PlantHealthStatus.CRITICAL.value]:
            severity_map = {
                PlantHealthStatus.WARNING.value: "warning",
                PlantHealthStatus.DISEASED.value: "error",
                PlantHealthStatus.CRITICAL.value: "critical"
            }
            severity = severity_map.get(health_status, "warning")
            
            notification_manager.send_notification(
                plant_id=plant_id,
                health_status=health_status,
                message=f"ML analysis result: {diagnosis}",
                severity=severity,
                device_id=device_id
            )
        
        add_log('INFO', f"ML result received and processed", 
                f"Image: {image_id}, Diagnosis: {diagnosis}, Confidence: {confidence}")
        
        return jsonify({
            'status': 'ok',
            'message': 'ML result received and processed',
            'received_at': datetime.now().isoformat(),
            'result_id': result_id
        }), 201
        
    except Exception as e:
        add_log('ERROR', f"Error processing ML result: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Processing failed: {str(e)}',
            'received_at': datetime.now().isoformat()
        }), 500

@app.route('/status', methods=['GET'])
def status():
    """
    Проверка статуса сервера
    
    Response:
    {
        "status": "online",
        "service": "HydroSmart Server",
        "timestamp": ISO timestamp,
        "version": string,
        "stats": {
            "total_readings": number,
            "total_ml_results": number,
            "total_plants": number,
            "total_devices": number
        }
    }
    """
    add_log('INFO', 'Status check requested')
    
    # Получение статистики из базы данных
    with db_manager.lock:
        with sqlite3.connect(db_manager.db_path) as conn:
            cursor = conn.cursor()
            
            # Подсчет показаний сенсоров
            cursor.execute('SELECT COUNT(*) FROM sensor_readings')
            total_readings = cursor.fetchone()[0]
            
            # Подсчет результатов ML
            cursor.execute('SELECT COUNT(*) FROM ml_results')
            total_ml_results = cursor.fetchone()[0]
            
            # Подсчет уникальных растений
            cursor.execute('SELECT COUNT(DISTINCT plant_id) FROM plant_statuses')
            total_plants = cursor.fetchone()[0]
            
            # Подсчет ESP устройств
            cursor.execute('SELECT COUNT(*) FROM esp_devices')
            total_devices = cursor.fetchone()[0]
    
    return jsonify({
        'status': 'online',
        'service': 'HydroSmart Server',
        'timestamp': datetime.now().isoformat(),
        'version': '2.1.0',
        'stats': {
            'total_readings': total_readings,
            'total_ml_results': total_ml_results,
            'total_plants': total_plants,
            'total_devices': total_devices
        }
    }), 200

@app.route('/readings', methods=['GET'])
def get_readings():
    """
    Получение показаний сенсоров
    
    Query parameters:
    - limit: number (default 100)
    - sensor: string (filter by sensor type)
    - plant_id: string (filter by plant)
    - device_id: string (filter by device)
    
    Response:
    {
        "status": "ok",
        "count": number,
        "readings": [sensor_reading_object]
    }
    """
    try:
        limit = request.args.get('limit', 100, type=int)
        sensor_type = request.args.get('sensor')
        plant_id = request.args.get('plant_id')
        device_id = request.args.get('device_id')
        
        readings = db_manager.get_sensor_readings(
            plant_id=plant_id,
            device_id=device_id,
            sensor_type=sensor_type,
            limit=min(limit, 1000)  # ограничение на 1000 записей
        )
        
        return jsonify({
            'status': 'ok',
            'count': len(readings),
            'readings': readings
        }), 200
        
    except Exception as e:
        add_log('ERROR', f"Error getting sensor readings: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to retrieve readings: {str(e)}'
        }), 500

@app.route('/ml_results', methods=['GET'])
def get_ml_results():
    """
    Получение результатов ML анализа
    
    Query parameters:
    - limit: number (default 100)
    - plant_id: string (filter by plant)
    
    Response:
    {
        "status": "ok",
        "count": number,
        "results": [ml_result_object]
    }
    """
    try:
        limit = request.args.get('limit', 100, type=int)
        plant_id = request.args.get('plant_id')
        
        results = db_manager.get_ml_results(
            plant_id=plant_id,
            limit=min(limit, 1000)
        )
        
        return jsonify({
            'status': 'ok',
            'count': len(results),
            'results': results
        }), 200
        
    except Exception as e:
        add_log('ERROR', f"Error getting ML results: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to retrieve ML results: {str(e)}'
        }), 500

@app.route('/plant/status/<plant_id>', methods=['GET'])
def get_plant_status(plant_id: str):
    """
    Получение статуса конкретного растения
    
    Path parameter:
    - plant_id: string
    
    Response:
    {
        "status": "ok",
        "plant_status": {
            "plant_id": string,
            "health_status": "healthy|warning|diseased|critical",
            "issues": string,
            "last_update": ISO timestamp,
            "device_id": string
        }
    }
    """
    try:
        plant_status = db_manager.get_plant_status(plant_id)
        
        if not plant_status:
            return jsonify({
                'status': 'not_found',
                'message': f'Plant {plant_id} not found'
            }), 404
        
        return jsonify({
            'status': 'ok',
            'plant_status': plant_status
        }), 200
        
    except Exception as e:
        add_log('ERROR', f"Error getting plant status for {plant_id}: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to retrieve plant status: {str(e)}'
        }), 500

@app.route('/plants/statuses', methods=['GET'])
def get_all_plant_statuses():
    """
    Получение статусов всех растений
    
    Response:
    {
        "status": "ok",
        "count": number,
        "plant_statuses": [plant_status_object]
    }
    """
    try:
        plant_statuses = db_manager.get_plant_statuses()
        
        return jsonify({
            'status': 'ok',
            'count': len(plant_statuses),
            'plant_statuses': plant_statuses
        }), 200
        
    except Exception as e:
        add_log('ERROR', f"Error getting all plant statuses: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to retrieve plant statuses: {str(e)}'
        }), 500

@app.route('/plants/problematic', methods=['GET'])
def get_problematic_plants():
    """
    Получение списка растений с проблемами
    
    Query parameters:
    - limit: number (default 100)
    
    Response:
    {
        "status": "ok",
        "count": number,
        "problematic_plants": [plant_status_object]
    }
    """
    try:
        limit = request.args.get('limit', 100, type=int)
        
        problematic_plants = db_manager.get_problematic_plants()
        
        # Применяем лимит
        limited_plants = problematic_plants[:min(limit, 1000)]  # ограничение на 1000
        
        return jsonify({
            'status': 'ok',
            'count': len(limited_plants),
            'problematic_plants': limited_plants
        }), 200
        
    except Exception as e:
        add_log('ERROR', f"Error getting problematic plants: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to retrieve problematic plants: {str(e)}'
        }), 500

@app.route('/notifications', methods=['GET'])
def get_notifications():
    """
    Получение уведомлений
    
    Query parameters:
    - plant_id: string (filter by plant)
    - device_id: string (filter by device)
    - limit: number (default 50)
    
    Response:
    {
        "status": "ok",
        "count": number,
        "notifications": [notification_object]
    }
    """
    try:
        plant_id = request.args.get('plant_id')
        device_id = request.args.get('device_id')
        limit = request.args.get('limit', 50, type=int)
        
        notifications = notification_manager.get_notifications(
            plant_id=plant_id,
            device_id=device_id,
            limit=min(limit, 1000)
        )
        
        return jsonify({
            'status': 'ok',
            'count': len(notifications),
            'notifications': notifications
        }), 200
        
    except Exception as e:
        add_log('ERROR', f"Error getting notifications: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to retrieve notifications: {str(e)}'
        }), 500

@app.route('/notifications/problematic', methods=['GET'])
def get_problematic_notifications():
    """
    Получение уведомлений о проблемах (warning, error, critical)
    
    Query parameters:
    - limit: number (default 50)
    
    Response:
    {
        "status": "ok",
        "count": number,
        "problematic_notifications": [notification_object]
    }
    """
    try:
        limit = request.args.get('limit', 50, type=int)
        
        problematic_notifications = notification_manager.get_problematic_notifications(
            limit=min(limit, 1000)
        )
        
        return jsonify({
            'status': 'ok',
            'count': len(problematic_notifications),
            'problematic_notifications': problematic_notifications
        }), 200
        
    except Exception as e:
        add_log('ERROR', f"Error getting problematic notifications: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to retrieve problematic notifications: {str(e)}'
        }), 500

@app.route('/commands', methods=['GET'])
def get_esp_commands():
    """
    Получение команд ESP8266
    
    Query parameters:
    - device_id: string (filter by device)
    - plant_id: string (filter by plant)
    - status: string (filter by status: pending/executed)
    - limit: number (default 100)
    
    Response:
    {
        "status": "ok",
        "count": number,
        "commands": [command_object]
    }
    """
    try:
        device_id = request.args.get('device_id')
        plant_id = request.args.get('plant_id')
        status_filter = request.args.get('status')
        limit = request.args.get('limit', 100, type=int)
        
        with db_manager.lock:
            with sqlite3.connect(db_manager.db_path) as conn:
                query = 'SELECT * FROM esp_commands'
                params = []
                
                conditions = []
                if device_id:
                    conditions.append('device_id = ?')
                    params.append(device_id)
                if plant_id:
                    conditions.append('plant_id = ?')
                    params.append(plant_id)
                if status_filter:
                    conditions.append('status = ?')
                    params.append(status_filter)
                
                if conditions:
                    query += ' WHERE ' + ' AND '.join(conditions)
                
                query += ' ORDER BY sent_at DESC LIMIT ?'
                params.append(min(limit, 1000))
                
                cursor = conn.cursor()
                cursor.execute(query, params)
                
                rows = cursor.fetchall()
                commands = [
                    {
                        'id': row[0],
                        'command_type': row[1],
                        'params': json.loads(row[2]) if row[2] else {},
                        'sent_at': row[3],
                        'plant_id': row[4],
                        'device_id': row[5],
                        'status': row[6],
                        'executed_at': row[7]
                    } for row in rows
                ]
        
        return jsonify({
            'status': 'ok',
            'count': len(commands),
            'commands': commands
        }), 200
        
    except Exception as e:
        add_log('ERROR', f"Error getting ESP commands: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to retrieve commands: {str(e)}'
        }), 500

@app.route('/logs', methods=['GET'])
def get_logs():
    """
    Получение логов сервера
    
    Query parameters:
    - limit: number (default 100)
    
    Response:
    {
        "status": "ok",
        "count": number,
        "logs": [log_line_string]
    }
    """
    try:
        limit = request.args.get('limit', 100, type=int)
        
        with open('server.log', 'r', encoding='utf-8') as f:
            lines = f.readlines()
            logs = [line.strip() for line in lines[-min(limit, 10000):]]  # ограничение на 10k строк
        
        return jsonify({
            'status': 'ok',
            'count': len(logs),
            'logs': logs
        }), 200
    except Exception as e:
        add_log('ERROR', f"Error reading logs: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Failed to read logs: {str(e)}'
        }), 500

if __name__ == '__main__':
    # Запуск MQTT менеджера
    mqtt_manager.start()
    
    logging.info("Starting HydroSmart Server v2.1.0 for ESP8266 integration")
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        logging.info("Shutting down server...")
    finally:
        mqtt_manager.stop()