# MQTT Configuration
MQTT_BROKER = "192.168.4.1"  # Change this to your MQTT broker IP/hostname (192.168.4.1 for Pi)
MQTT_PORT = 1883
MQTT_USERNAME = None  # Set if your broker requires authentication
MQTT_PASSWORD = None  # Set if your broker requires authentication
MQTT_KEEPALIVE = 60

# Flask Configuration
SECRET_KEY = "your-secret-key-change-this"
DEBUG = False
HOST = "0.0.0.0"
PORT = 5000

# MQTT Topics Configuration
TOPICS = {
    'gyro': 'sensors/gyro',
    'accel': 'sensors/accel',
    'temp': 'tempgun/sensor/temp_object',
    'distance': 'sensors/distance',
    'weight_value': 'weight/value',
    'weight_status': 'weight/status',
    'gyro_y': 'esp32/gyro/y',
    'gyro_z': 'esp32/gyro/z',
    'load': 'esp32/loadcell',
    'bpm': 'health/bpm',
    'alcohol': 'alcohol/reading',
    'servo': 'actuators/servo',
    'stepper': 'actuators/stepper'
}
