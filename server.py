from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from datetime import datetime
import json

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('server.log'),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)
CORS(app)  # Разрешаем кросс-доменные запросы

# Хранилище последних показаний (для демонстрации)
latest_sensor_data = {}

@app.route('/status', methods=['GET'])
def status():
    """Эндпоинт для проверки работы сервера"""
    return jsonify({
        'status': 'online',
        'time': datetime.now().isoformat(),
        'message': 'Server is running'
    }), 200

@app.route('/data', methods=['POST'])
def receive_data():
    """Эндпоинт для приема данных от ESP"""
    try:
        # Получаем JSON данные
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data received'}), 400
        
        # Добавляем временную метку на сервере
        data['server_time'] = datetime.now().isoformat()
        
        # Логируем полученные данные
        logging.info(f"Received data from ESP: {json.dumps(data, indent=2)}")
        
        # Сохраняем последние показания
        if 'sensor_id' in data:
            latest_sensor_data[data['sensor_id']] = data
        else:
            # Если нет ID, сохраняем с временной меткой
            latest_sensor_data[datetime.now().timestamp()] = data
        
        # Здесь можно добавить сохранение в базу данных
        
        return jsonify({
            'status': 'success',
            'message': 'Data received',
            'received_at': data['server_time']
        }), 201
        
    except Exception as e:
        logging.error(f"Error processing data: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/latest/<sensor_id>', methods=['GET'])
def get_latest(sensor_id):
    """Получить последние показания конкретного датчика"""
    if sensor_id in latest_sensor_data:
        return jsonify(latest_sensor_data[sensor_id]), 200
    return jsonify({'error': 'Sensor not found'}), 404

@app.route('/logs', methods=['GET'])
def get_logs():
    """Получить последние записи из лога"""
    try:
        with open('server.log', 'r') as f:
            lines = f.readlines()[-50:]  # Последние 50 строк
        return jsonify({'logs': lines}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("="*50)
    print("Server starting...")
    print(f"Local access: http://127.0.0.1:5000")
    
    # Получаем локальный IP для доступа с других устройств
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print(f"Network access: http://{local_ip}:5000 (для ESP)")
    print("="*50)
    
    # Запускаем сервер
    app.run(
        host='0.0.0.0',  # Слушаем все интерфейсы
        port=5000,
        debug=True  # В продакшене нужно отключить
    )
