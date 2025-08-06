#!/usr/bin/env python3
"""
ESP32 MQTT Simulator
Simulates ESP32 sending sensor data via MQTT
"""
import paho.mqtt.client as mqtt
import json
import time
import random
import threading

# MQTT Configuration - matches your setup
MQTT_BROKER = "192.168.4.1"
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60

# MQTT Topics (same as in config.py)
TOPICS = {
    'gyro': 'sensors/gyro',
    'accel': 'sensors/accel',
    'temp': 'sensors/temp',
    'distance': 'sensors/distance',
    'weight_value': 'weight/value',
    'weight_status': 'weight/status',
    'gyro_y': 'esp32/gyro/y',
    'gyro_z': 'esp32/gyro/z',
    'load': 'esp32/loadcell',
    'bpm': 'health/bpm',
    'alcohol': 'alcohol/reading'
}

class ESP32Simulator:
    def __init__(self):
        self.client = mqtt.Client("ESP32_Simulator")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.running = False
        
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"ESP32 Simulator connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
            # Subscribe to actuator topics to receive commands
            client.subscribe("actuators/servo")
            client.subscribe("actuators/stepper")
        else:
            print(f"Failed to connect with result code {rc}")
    
    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode()
        print(f"ESP32 received command on {topic}: {payload}")
        
        if topic == "actuators/servo":
            print(f"Setting servo to {payload} degrees")
        elif topic == "actuators/stepper":
            try:
                command = json.loads(payload)
                print(f"Moving stepper {command['steps']} steps {command['direction']}")
            except:
                print(f"Invalid stepper command: {payload}")
    
    def generate_sensor_data(self):
        """Generate realistic sensor data"""
        return {
            'gyro': {'x': random.uniform(-10, 10), 'y': random.uniform(-10, 10), 'z': random.uniform(-10, 10)},
            'accel': {'x': random.uniform(-2, 2), 'y': random.uniform(-2, 2), 'z': random.uniform(8, 12)},
            'temp': random.uniform(20, 35),
            'distance': random.uniform(5, 200),
            'weight_value': random.uniform(0, 100),
            'weight_status': random.choice(['stable', 'measuring', 'overload']),
            'gyro_y': random.uniform(-10, 10),
            'gyro_z': random.uniform(-10, 10),
            'load': random.uniform(0, 50),
            'bpm': random.randint(60, 100),
            'alcohol': random.uniform(0, 1000)
        }
    
    def publish_sensor_data(self):
        """Continuously publish sensor data"""
        while self.running:
            try:
                data = self.generate_sensor_data()
                
                # Publish gyro as JSON
                gyro_data = json.dumps(data['gyro'])
                self.client.publish(TOPICS['gyro'], gyro_data)
                
                # Publish accel as JSON
                accel_data = json.dumps(data['accel'])
                self.client.publish(TOPICS['accel'], accel_data)
                
                # Publish single values
                self.client.publish(TOPICS['temp'], str(data['temp']))
                self.client.publish(TOPICS['distance'], str(data['distance']))
                self.client.publish(TOPICS['weight_value'], str(data['weight_value']))
                self.client.publish(TOPICS['weight_status'], data['weight_status'])
                self.client.publish(TOPICS['gyro_y'], str(data['gyro_y']))
                self.client.publish(TOPICS['gyro_z'], str(data['gyro_z']))
                self.client.publish(TOPICS['load'], str(data['load']))
                self.client.publish(TOPICS['bpm'], str(data['bpm']))
                self.client.publish(TOPICS['alcohol'], str(data['alcohol']))
                
                print(f"Published sensor data - Temp: {data['temp']:.1f}°C, Distance: {data['distance']:.1f}cm, BPM: {data['bpm']}")
                
                time.sleep(2)  # Publish every 2 seconds
                
            except Exception as e:
                print(f"Error publishing data: {e}")
                time.sleep(1)
    
    def start(self):
        """Start the ESP32 simulator"""
        try:
            self.client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
            self.client.loop_start()
            
            self.running = True
            
            # Start publishing in a separate thread
            publish_thread = threading.Thread(target=self.publish_sensor_data)
            publish_thread.daemon = True
            publish_thread.start()
            
            print("ESP32 Simulator started. Press Ctrl+C to stop.")
            
            # Keep the main thread alive
            while self.running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\nStopping ESP32 Simulator...")
            self.stop()
        except Exception as e:
            print(f"Error: {e}")
    
    def stop(self):
        """Stop the ESP32 simulator"""
        self.running = False
        self.client.loop_stop()
        self.client.disconnect()

if __name__ == "__main__":
    print("ESP32 MQTT Simulator")
    print("===================")
    print(f"Connecting to MQTT broker: {MQTT_BROKER}:{MQTT_PORT}")
    print("This simulates an ESP32 device sending sensor data via MQTT")
    print()
    
    simulator = ESP32Simulator()
    simulator.start()
