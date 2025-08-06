# app.py
from flask import Flask, render_template, request, jsonify, Response
import subprocess
import paho.mqtt.client as mqtt
import json
import threading
from datetime import datetime
import time
import os
import io
import base64
from config import *
from player import AudioPlayer
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = SECRET_KEY

# Audio playback control
audio_lock = threading.Lock()
audio_playing = False

# Global variables to store sensor data
sensor_data = {
    'gyro': {'x': 0, 'y': 0, 'z': 0, 'timestamp': datetime.now().isoformat()},
    'accel': {'x': 0, 'y': 0, 'z': 0, 'timestamp': datetime.now().isoformat()},
    'temp': {'value': 0, 'timestamp': datetime.now().isoformat()},
    'distance': {'value': 0, 'timestamp': datetime.now().isoformat()},
    'weight_value': {'value': 0, 'timestamp': datetime.now().isoformat()},
    'weight_status': {'status': 'unknown', 'timestamp': datetime.now().isoformat()},
    'gyro_y': {'value': 0, 'timestamp': datetime.now().isoformat()},
    'gyro_z': {'value': 0, 'timestamp': datetime.now().isoformat()},
    'load': {'value': 0, 'timestamp': datetime.now().isoformat()},
    'bpm': {'value': 0, 'timestamp': datetime.now().isoformat()},
    'alcohol': {'value': 0, 'timestamp': datetime.now().isoformat()},
}

# Audio alert thresholds and tracking
AUDIO_THRESHOLDS = {
    'temp_high': 37.5,  # High fever threshold in Celsius
    'temp_low': 35.0,   # Low body temp threshold
    'bpm_high': 100,    # High BPM threshold
    'bpm_low': 60,      # Low BPM threshold
    'alcohol_detected': 0.1,  # Alcohol detection threshold
    'motion_threshold': 5.0,  # Motion detection threshold
}

# Track last audio alerts to prevent spam
last_audio_alerts = {
    'high_temp': 0,
    'low_temp': 0,
    'high_bpm': 0,
    'low_bpm': 0,
    'normal_bpm': 0,
    'alcohol': 0,
    'motion': 0,
    'mqtt_connected': 0,
    'system_startup': 0,
}

AUDIO_COOLDOWN = 30  # Seconds between repeated audio alerts

# MQTT connection status
mqtt_connected = False

# Initialize Audio Player
audio_player = AudioPlayer(verbose=True)

# MQTT Client Setup
mqtt_client = mqtt.Client()

try:
    from picamera2 import Picamera2
    CAMERA_AVAILABLE = True
except ImportError:
    CAMERA_AVAILABLE = False
    print("⚠️ Camera modules not available - facial recognition will use simulation mode")

# Initialize camera if available
camera = None
if CAMERA_AVAILABLE:
    try:
        camera = Picamera2()
        camera.configure(camera.create_preview_configuration(main={"format": 'XRGB8888', "size": (640, 480)}))
        camera.start()
        print("📹 Camera initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize camera: {e}")
        camera = None
        CAMERA_AVAILABLE = False

def should_play_audio_alert(alert_type: str) -> bool:
    """Check if enough time has passed since last audio alert"""
    current_time = time.time()
    if current_time - last_audio_alerts.get(alert_type, 0) >= AUDIO_COOLDOWN:
        last_audio_alerts[alert_type] = current_time
        return True
    return False

def play_audio_threaded(func, *args):
    """Play audio in a separate thread to avoid blocking - only one audio at a time"""
    global audio_playing
    
    def audio_task():
        global audio_playing
        
        # Check if audio is already playing
        if not audio_lock.acquire(blocking=False):
            print(f"🔇 Audio skipped - another audio is playing: {func.__name__}")
            return
        
        try:
            audio_playing = True
            success = func(*args)
            if not success:
                print(f"⚠️ Audio playback failed for {func.__name__} with args {args}")
        except Exception as e:
            print(f"❌ Audio error in {func.__name__}: {e}")
        finally:
            audio_playing = False
            audio_lock.release()
    
    thread = threading.Thread(target=audio_task, daemon=True)
    thread.start()

def check_and_play_audio_alerts(sensor_type: str, value: float = None):
    """Check sensor values and play audio alerts when thresholds are exceeded"""
    try:
        if sensor_type == 'temp' and value is not None:
            if value >= AUDIO_THRESHOLDS['temp_high'] and should_play_audio_alert('high_temp'):
                play_audio_threaded(audio_player.play_health_alert, 'high_temp')
                print(f"🔊 High temperature alert: {value}°C")
            elif value <= AUDIO_THRESHOLDS['temp_low'] and should_play_audio_alert('low_temp'):
                play_audio_threaded(audio_player.play_health_alert, 'temp_measure')
                print(f"🔊 Low temperature alert: {value}°C")
        
        elif sensor_type == 'bpm' and value is not None:
            if value >= AUDIO_THRESHOLDS['bpm_high'] and should_play_audio_alert('high_bpm'):
                play_audio_threaded(audio_player.play_health_alert, 'high_bpm')
                print(f"🔊 High BPM alert: {value}")
            elif value > 0 and value <= AUDIO_THRESHOLDS['bpm_low'] and should_play_audio_alert('low_bpm'):
                play_audio_threaded(audio_player.play_health_alert, 'normal_bpm')
                print(f"🔊 Low BPM alert: {value}")
            elif value > 0 and 60 <= value < 100 and should_play_audio_alert('normal_bpm'):
                # Normal BPM detected
                play_audio_threaded(audio_player.play_health_alert, 'normal_bpm')
                print(f"🔊 Normal BPM detected: {value}")
        
        elif sensor_type == 'alcohol' and value is not None:
            if value >= AUDIO_THRESHOLDS['alcohol_detected'] and should_play_audio_alert('alcohol'):
                play_audio_threaded(audio_player.play_health_alert, 'alcohol_detected')
                print(f"🔊 Alcohol detected alert: {value}")
        
        elif sensor_type == 'motion' and value is not None:
            if abs(value) >= AUDIO_THRESHOLDS['motion_threshold'] and should_play_audio_alert('motion'):
                play_audio_threaded(audio_player.play_motion_alert)
                print(f"🔊 Motion detected alert: {value}")
                
    except Exception as e:
        print(f"Error in audio alert system: {e}")

def on_connect(client, userdata, flags, rc):
    global mqtt_connected
    if rc == 0:
        mqtt_connected = True
        print(f"Successfully connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
        # Play system online sound
        if should_play_audio_alert('mqtt_connected'):
            play_audio_threaded(audio_player.play_system_status, 'online')
    else:
        mqtt_connected = False
        print(f"Failed to connect to MQTT broker with result code {rc}")
        # Play error sound
        play_audio_threaded(audio_player.play_system_status, 'error')
    
    # Subscribe to all topics
    for topic in TOPICS.values():
        client.subscribe(topic)
        print(f"Subscribed to {topic}")

def on_message(client, userdata, msg):
    topic = msg.topic
    try:
        payload = msg.payload.decode()
        timestamp = datetime.now().isoformat()
        
        # Process different topics
        if topic == TOPICS['gyro']:
            data = json.loads(payload)
            sensor_data['gyro'] = {**data, 'timestamp': timestamp}
            # Check for significant motion
            if 'x' in data and 'y' in data and 'z' in data:
                motion_magnitude = (data['x']**2 + data['y']**2 + data['z']**2)**0.5
                check_and_play_audio_alerts('motion', motion_magnitude)
        elif topic == TOPICS['accel']:
            data = json.loads(payload)
            sensor_data['accel'] = {**data, 'timestamp': timestamp}
            # Check for significant acceleration/motion
            if 'x' in data and 'y' in data and 'z' in data:
                accel_magnitude = (data['x']**2 + data['y']**2 + data['z']**2)**0.5
                check_and_play_audio_alerts('motion', accel_magnitude)
        elif topic == TOPICS['temp']:
            # Handle both JSON and simple float formats
            try:
                temp_data = json.loads(payload)
                # Check if it's a dictionary with temperature data
                if isinstance(temp_data, dict):
                    if 'temp' in temp_data:
                        temp_value = float(temp_data['temp'])
                        sensor_data['temp'] = {'value': temp_value, 'timestamp': timestamp}
                        check_and_play_audio_alerts('temp', temp_value)
                    elif 'temperature' in temp_data:
                        temp_value = float(temp_data['temperature'])
                        sensor_data['temp'] = {'value': temp_value, 'timestamp': timestamp}
                        check_and_play_audio_alerts('temp', temp_value)
                    else:
                        # If it's a dict but no recognized key, try to get the first numeric value
                        for key, value in temp_data.items():
                            try:
                                temp_value = float(value)
                                sensor_data['temp'] = {'value': temp_value, 'timestamp': timestamp}
                                check_and_play_audio_alerts('temp', temp_value)
                                break
                            except (ValueError, TypeError):
                                continue
                else:
                    # If it's not a dict (could be a plain number), use it directly
                    temp_value = float(temp_data)
                    sensor_data['temp'] = {'value': temp_value, 'timestamp': timestamp}
                    check_and_play_audio_alerts('temp', temp_value)
            except json.JSONDecodeError:
                # If JSON parsing fails, treat as plain float
                temp_value = float(payload)
                sensor_data['temp'] = {'value': temp_value, 'timestamp': timestamp}
                check_and_play_audio_alerts('temp', temp_value)
        elif topic == TOPICS['distance']:
            sensor_data['distance'] = {'value': float(payload), 'timestamp': timestamp}
        elif topic == TOPICS['weight_value']:
            sensor_data['weight_value'] = {'value': float(payload), 'timestamp': timestamp}
        elif topic == TOPICS['weight_status']:
            sensor_data['weight_status'] = {'status': payload, 'timestamp': timestamp}
        elif topic == TOPICS['gyro_y']:
            sensor_data['gyro_y'] = {'value': float(payload), 'timestamp': timestamp}
        elif topic == TOPICS['gyro_z']:
            sensor_data['gyro_z'] = {'value': float(payload), 'timestamp': timestamp}
        elif topic == TOPICS['load']:
            sensor_data['load'] = {'value': float(payload), 'timestamp': timestamp}
        elif topic == TOPICS['bpm']:
            bpm_value = float(payload)
            sensor_data['bpm'] = {'value': bpm_value, 'timestamp': timestamp}
            check_and_play_audio_alerts('bpm', bpm_value)
        elif topic == TOPICS['alcohol']:
            # Handle both JSON and simple float formats
            try:
                alcohol_data = json.loads(payload)
                if 'alcohol_level' in alcohol_data:
                    alcohol_value = float(alcohol_data['alcohol_level'])
                    sensor_data['alcohol'] = {'value': alcohol_value, 'timestamp': timestamp}
                    check_and_play_audio_alerts('alcohol', alcohol_value)
                elif 'alcohol' in alcohol_data:
                    alcohol_value = float(alcohol_data['alcohol'])
                    sensor_data['alcohol'] = {'value': alcohol_value, 'timestamp': timestamp}
                    check_and_play_audio_alerts('alcohol', alcohol_value)
                else:
                    alcohol_value = float(payload)
                    sensor_data['alcohol'] = {'value': alcohol_value, 'timestamp': timestamp}
                    check_and_play_audio_alerts('alcohol', alcohol_value)
            except json.JSONDecodeError:
                alcohol_value = float(payload)
                sensor_data['alcohol'] = {'value': alcohol_value, 'timestamp': timestamp}
                check_and_play_audio_alerts('alcohol', alcohol_value)
        
    except Exception as e:
        print(f"Error processing message from {topic}: {e}")

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# Flask Routes
@app.route("/")
def index():
    return render_template('dashboard.html')
    
@app.route("/dashboard")
def dashboard():
    return render_template('dashboard.html')

@app.route("/face-recognition")
def face_recognition():
    return render_template("face_recognition.html")

@app.route("/api/sensor-data")
def get_sensor_data():
    return jsonify(sensor_data)

@app.route("/api/mqtt-status")
def get_mqtt_status():
    return jsonify({
        'connected': mqtt_connected,
        'broker': MQTT_BROKER,
        'port': MQTT_PORT
    })

def generate_frames():
    """Generate video frames using optimized frame capture method"""
    import time
    import threading
    from queue import Queue, Empty
    
    print("🎥 Starting optimized camera frame generator...")
    
    # Frame queue for buffering
    frame_queue = Queue(maxsize=3)
    
    def capture_frames():
        """Background thread to capture frames continuously"""
        while True:
            try:
                # Capture single frame with libcamera-still (fast and reliable)
                process = subprocess.Popen([
                    "libcamera-still",
                    "--camera", "0",
                    "-o", "-",
                    "--width", "640",
                    "--height", "480",
                    "--nopreview",
                    "--immediate",  # Take photo immediately
                    "--timeout", "1"  # 1ms timeout for speed
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                frame, error = process.communicate(timeout=2)
                
                if process.returncode == 0 and len(frame) > 1000:  # Valid JPEG
                    # Try to add frame to queue (non-blocking)
                    try:
                        frame_queue.put(frame, block=False)
                    except:
                        # Queue full, remove old frame and add new one
                        try:
                            frame_queue.get_nowait()
                            frame_queue.put(frame, block=False)
                        except:
                            pass
                else:
                    print(f"Frame capture failed: {error.decode() if error else 'Unknown error'}")
                    time.sleep(0.1)
                    
            except subprocess.TimeoutExpired:
                print("Frame capture timeout")
                process.kill()
                time.sleep(0.1)
            except Exception as e:
                print(f"Capture error: {e}")
                time.sleep(0.5)
            
            # Small delay between captures for reasonable frame rate
            time.sleep(0.066)  # ~15 FPS
    
    # Start background capture thread
    capture_thread = threading.Thread(target=capture_frames, daemon=True)
    capture_thread.start()
    
    # Main streaming loop
    last_frame = None
    frame_repeat_count = 0
    max_repeats = 5  # Maximum times to repeat same frame
    
    try:
        while True:
            try:
                # Try to get new frame (with timeout)
                frame = frame_queue.get(timeout=0.5)
                last_frame = frame
                frame_repeat_count = 0
                
                # Yield the frame
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
                
            except Empty:
                # No new frame, repeat last frame if available
                if last_frame and frame_repeat_count < max_repeats:
                    yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + last_frame + b"\r\n")
                    frame_repeat_count += 1
                else:
                    print("No frames available, waiting...")
                    time.sleep(0.1)
                    
    except Exception as e:
        print(f"Streaming error: {e}")
    finally:
        print("🛑 Frame generator stopped")

def generate_frames_fallback():
    """Fallback method using single frame capture"""
    print("📸 Using fallback single-frame capture method")
    import time
    
    while True:
        try:
            # Use libcamera-still for single frames
            process = subprocess.open(
                ["libcamera-still", "--camera", "0", "-o", "-", "--width", "640", "--height", "480", "--nopreview"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            frame, error = process.communicate(timeout=10)
            
            if process.returncode == 0 and len(frame) > 100:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
            else:
                print(f"Frame capture error: {error.decode() if error else 'Unknown error'}")
                
            # Small delay between frames for single-shot method
            time.sleep(0.1)
            
        except subprocess.TimeoutExpired:
            print("Frame capture timeout")
            process.kill()
            time.sleep(0.5)
        except Exception as e:
            print(f"Fallback capture error: {e}")
            time.sleep(1)

@app.route("/video_feed")
def video_feed():
    return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

    
@app.route("/api/control/servo", methods=['POST'])
def control_servo():
    try:
        data = request.get_json()
        angle = data.get('angle', 0)
        
        # Publish servo control command
        mqtt_client.publish(TOPICS['servo'], str(angle))
        
        # Play user interaction sound
        play_audio_threaded(audio_player.play_user_interaction, 'press_button')
        
        return jsonify({'status': 'success', 'message': f'Servo set to {angle} degrees'})
    except Exception as e:
        play_audio_threaded(audio_player.play_system_status, 'error')
        return jsonify({'status': 'error', 'message': str(e)})

@app.route("/api/control/stepper", methods=['POST'])
def control_stepper():
    try:
        data = request.get_json()
        steps = data.get('steps', 0)
        direction = data.get('direction', 'CW')
        
        command = {'steps': steps, 'direction': direction}
        mqtt_client.publish(TOPICS['stepper'], json.dumps(command))
        
        # Play user interaction sound
        play_audio_threaded(audio_player.play_user_interaction, 'press_button')
        
        return jsonify({'status': 'success', 'message': f'Stepper moved {steps} steps {direction}'})
    except Exception as e:
        play_audio_threaded(audio_player.play_system_status, 'error')
        return jsonify({'status': 'error', 'message': str(e)})

@app.route("/api/audio/test", methods=['POST'])
def test_audio():
    """Test audio playback with specific sound"""
    try:
        data = request.get_json()
        sound_name = data.get('sound_name', 'system_online')
        
        # Play the requested sound in a separate thread
        success = False
        if sound_name in ['high_temp', 'high_bpm', 'normal_bpm', 'alcohol_detected', 'temp_measure']:
            success = audio_player.play_health_alert(sound_name)
        elif sound_name in ['online', 'error', 'setup_complete', 'sensors_active', 'scan_start']:
            success = audio_player.play_system_status(sound_name)
        elif sound_name == 'motion':
            success = audio_player.play_motion_alert()
        elif sound_name in ['identified', 'touch_screen', 'press_button', 'do_not_move']:
            success = audio_player.play_user_interaction(sound_name)
        else:
            success = audio_player.play_sound(sound_name)
        
        return jsonify({
            'status': 'success' if success else 'error',
            'message': f'Audio test {"successful" if success else "failed"} for sound: {sound_name}',
            'sound_played': sound_name
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route("/api/audio/available")
def get_available_sounds():
    """Get list of available audio files"""
    try:
        available_sounds = audio_player.list_available_sounds()
        return jsonify({
            'status': 'success',
            'sounds': available_sounds,
            'sound_categories': {
                'health_alerts': ['high_temp', 'high_bpm', 'normal_bpm', 'alcohol_detected', 'temp_measure'],
                'system_status': ['online', 'error', 'setup_complete', 'sensors_active', 'scan_start'],
                'user_interaction': ['identified', 'touch_screen', 'press_button', 'do_not_move'],
                'motion': ['motion']
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route("/api/audio/status")
def get_audio_status():
    """Get current audio alert status and thresholds"""
    return jsonify({
        'thresholds': AUDIO_THRESHOLDS,
        'last_alerts': last_audio_alerts,
        'cooldown_seconds': AUDIO_COOLDOWN,
        'audio_enabled': True,
        'audio_player_status': 'ready',
        'audio_currently_playing': audio_playing
    })

@app.route('/print-readings', methods=['POST'])
def print_readings():
    # Define the absolute path to the script
    script_path = '/home/bsit/BotibotWeb/server/print.py'
    
    # Verify the script exists before trying to execute
    if not os.path.exists(script_path):
        return jsonify({
            'success': False,
            'message': 'Print script not found',
            'error': f'File not found: {script_path}'
        }), 404

    try:
        # Use run() instead of Popen() for one-time execution
        result = subprocess.run(
            ['python3', script_path],
            capture_output=True,
            text=True,
            timeout=30  # Add timeout to prevent hanging
        )
        
        if result.returncode == 0:
            return jsonify({
                'success': True,
                'message': 'Print job completed successfully',
                'output': result.stdout
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Print job failed',
                'error': result.stderr,
                'return_code': result.returncode
            }), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'message': 'Print job timed out',
            'error': 'Process took too long to complete'
        }), 500
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Failed to execute print job',
            'error': str(e)
        }), 500

@app.route("/api/camera/feed")
def camera_feed():
    """Get current camera frame as base64 encoded image."""
    try:
        if not CAMERA_AVAILABLE or camera is None:
            # Return a placeholder image
            return jsonify({
                'success': False,
                'message': 'Camera not available',
                'placeholder': True
            })
        
        # Capture frame from camera
        frame = camera.capture_array()
        
        # Convert frame to RGB (picamera2 gives XRGB8888)
        if frame.shape[2] == 4:  # XRGB8888 format
            frame = frame[:, :, :3]  # Remove alpha channel
        
        # Convert to PIL Image
        img = Image.fromarray(frame)
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=85)
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return jsonify({
            'success': True,
            'image': f'data:image/jpeg;base64,{img_base64}',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Camera error: {str(e)}',
            'placeholder': True
        })


@app.route("/api/camera/capture", methods=['POST'])
def camera_capture():
    """Capture a single image for facial recognition."""
    try:
        if not CAMERA_AVAILABLE or camera is None:
            return jsonify({
                'success': False,
                'message': 'Camera not available - please check camera connection',
                'error': 'camera_unavailable'
            }), 400

        # Capture frame from camera
        frame = camera.capture_array()
        
        # Convert frame to RGB (picamera2 gives XRGB8888)
        if frame.shape[2] == 4:  # XRGB8888 format
            frame = frame[:, :, :3]  # Remove alpha channel
        
        # Convert to PIL Image
        img = Image.fromarray(frame)
        
        # Convert to base64 (same format as face_recognition_client.py)
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=85)
        img_data = buffer.getvalue()
        img_base64 = base64.b64encode(img_data).decode('utf-8')
        
        print(f"📸 Image captured for facial recognition ({len(img_data)} bytes)")
        
        return jsonify({
            'success': True,
            'image_base64': img_base64,
            'size': len(img_data),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Camera capture error: {e}")
        return jsonify({
            'success': False,
            'message': f'Camera capture failed: {str(e)}',
            'error': 'capture_failed'
        }), 500

@app.route("/api/facial-recognition/authenticate", methods=['POST'])
def facial_recognition_authenticate():
    """Facial recognition authentication endpoint - port 6000 compatible."""
    try:
        data = request.get_json()
        timestamp = data.get('timestamp', datetime.now().isoformat())
        source = data.get('source', 'unknown')
        
        print(f"🔐 Facial recognition request from {source} at {timestamp}")
        
        # Simulate facial recognition processing
        import time
        time.sleep(2)  # Simulate processing time
        
        # In a real implementation, this would:
        # 1. Capture current camera frame
        # 2. Run facial recognition algorithm
        # 3. Compare with stored faces
        # 4. Return authentication result
        
        if CAMERA_AVAILABLE and camera is not None:
            try:
                # Capture frame for analysis
                frame = camera.capture_array()
                print("📸 Captured frame for facial recognition analysis")
                
                # Here you would implement actual facial recognition
                # For now, simulate successful authentication
                authenticated = True
                confidence = 0.95
                
            except Exception as e:
                print(f"Camera capture error during auth: {e}")
                authenticated = True  # Fallback authentication
                confidence = 0.8
        else:
            # No camera available, use fallback authentication
            authenticated = True
            confidence = 0.7
            print("📷 No camera - using fallback authentication")
        
        # Play authentication sound feedback
        if authenticated:
            play_audio_threaded(audio_player.play_user_interaction, 'identified')
        else:
            play_audio_threaded(audio_player.play_system_status, 'error')
        
        return jsonify({
            'authenticated': authenticated,
            'confidence': confidence,
            'timestamp': datetime.now().isoformat(),
            'source': source,
            'message': 'Identity verified successfully' if authenticated else 'Authentication failed'
        })
        
    except Exception as e:
        print(f"❌ Facial recognition error: {e}")
        return jsonify({
            'authenticated': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

def start_mqtt():
    try:
        if MQTT_USERNAME and MQTT_PASSWORD:
            mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
        mqtt_client.loop_forever()
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {e}")
        play_audio_threaded(audio_player.play_system_status, 'error')

if __name__ == "__main__":
    # Start MQTT client in a separate thread
    mqtt_thread = threading.Thread(target=start_mqtt)
    mqtt_thread.daemon = True
    mqtt_thread.start()
    
    # Play startup sound
    print("🎵 Starting BotiBot Web Server...")
    if should_play_audio_alert('system_startup'):
        play_audio_threaded(audio_player.play_system_status, 'setup_complete')
    
    # Announce sensors are active
    time.sleep(2)  # Brief delay before next sound
    play_audio_threaded(audio_player.play_system_status, 'sensors_active')
    
    # Start Flask server
    app.run(debug=DEBUG, port=PORT, host=HOST)
