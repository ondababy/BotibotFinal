import json
from escpos.printer import Usb
from datetime import datetime
import sys
import os
import paho.mqtt.client as mqtt
import threading
import time

# MQTT Configuration
MQTT_BROKER = "192.168.4.1"  # ESP32 Access Point IP
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60

# MQTT Topics
MQTT_TOPICS = {
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

# Global sensor data storage
mqtt_sensor_data = {
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

# MQTT client for independent operation
mqtt_client = None
mqtt_connected = False

# Setup printer - Updated with correct Product ID
VENDOR_ID = 0x0483
PRODUCT_ID = 0x5840  # Correct Product ID from your working code

def get_alcohol_description(alcohol_level):
    """
    Get alcohol level description based on reading
    
    Args:
        alcohol_level (float): Alcohol level reading
        
    Returns:
        str: Description of alcohol level
    """
    try:
        level = float(alcohol_level)
        if level == 0:
            return "Sober"
        elif level <= 79.99:
            return "Intoxicated"
        else:
            return "Highly Intoxicated"
    except (ValueError, TypeError):
        return "Unknown"

def initialize_printer():
    """Try different printer initialization methods with resource busy handling"""
    import subprocess
    import time
    
    # First, try to reset USB device if it's busy
    def reset_usb_device():
        try:
            print("🔄 Attempting to reset USB printer device...")
            # Try to reset the USB device
            result = subprocess.run(['sudo', 'usb_modeswitch', '-v', hex(VENDOR_ID), '-p', hex(PRODUCT_ID), '-R'], 
                                  capture_output=True, text=True, timeout=5)
            time.sleep(2)  # Wait for reset
            return True
        except:
            try:
                # Alternative: try to unbind and rebind the device
                subprocess.run(['sudo', 'bash', '-c', 'echo "1-1:1.0" > /sys/bus/usb/drivers/usblp/unbind'], 
                             capture_output=True, text=True, timeout=3)
                time.sleep(1)
                subprocess.run(['sudo', 'bash', '-c', 'echo "1-1:1.0" > /sys/bus/usb/drivers/usblp/bind'], 
                             capture_output=True, text=True, timeout=3)
                time.sleep(2)
                return True
            except:
                return False
    
    # Method 1: Try with correct endpoints FIRST (based on lsusb output)
    endpoint_configs = [
        (0x82, 0x04),  # Correct endpoints from lsusb: IN=0x82, OUT=0x04
        (0x82, 0x01),  # Common fallback
        (0x81, 0x02),  # Alternative 1
        (0x82, 0x02),  # Alternative 2
        (0x81, 0x01),  # Alternative 3
        (0x83, 0x03),  # Alternative 4
    ]
    
    # First attempt without reset
    for in_ep, out_ep in endpoint_configs:
        try:
            printer = Usb(VENDOR_ID, PRODUCT_ID, in_ep=in_ep, out_ep=out_ep, timeout=0)
            print(f"✓ Printer initialized with endpoints: in=0x{in_ep:02x}, out=0x{out_ep:02x}")
            return printer
        except Exception as e:
            if "Resource busy" in str(e) or "errno 16" in str(e):
                print(f"⚠️ Printer busy with endpoints in=0x{in_ep:02x}, out=0x{out_ep:02x}")
                continue
            else:
                print(f"Failed with in_ep=0x{in_ep:02x}, out_ep=0x{out_ep:02x}: {e}")
    
    # If all attempts failed with "Resource busy", try to reset and try again
    print("🔄 All initial attempts failed, trying USB reset...")
    reset_usb_device()
    
    # Second attempt after reset
    for in_ep, out_ep in endpoint_configs:
        try:
            printer = Usb(VENDOR_ID, PRODUCT_ID, in_ep=in_ep, out_ep=out_ep, timeout=0)
            print(f"✓ Printer initialized after reset with endpoints: in=0x{in_ep:02x}, out=0x{out_ep:02x}")
            return printer
        except Exception as e:
            print(f"Failed after reset with in_ep=0x{in_ep:02x}, out_ep=0x{out_ep:02x}: {e}")
    
    # Method 2: Try with auto-detection as fallback
    try:
        printer = Usb(VENDOR_ID, PRODUCT_ID, timeout=0)
        print("✓ Printer initialized with auto-detection")
        return printer
    except Exception as e:
        print(f"Auto-detection failed: {e}")
        if "Resource busy" in str(e):
            print("🔄 Auto-detection failed due to busy resource, trying after delay...")
            time.sleep(3)
            try:
                printer = Usb(VENDOR_ID, PRODUCT_ID, timeout=0)
                print("✓ Printer initialized with auto-detection after delay")
                return printer
            except Exception as e2:
                print(f"Auto-detection failed again: {e2}")
    
    # Method 3: Try with interface specification
    try:
        printer = Usb(VENDOR_ID, PRODUCT_ID, interface=0, timeout=0)
        print("✓ Printer initialized with interface=0")
        return printer
    except Exception as e:
        print(f"Interface method failed: {e}")
    
    print("❌ All printer initialization methods failed")
    return None

def get_current_sensor_data():
    """
    Get current sensor data from MQTT
    This function connects to MQTT and gets live data
    """
    global mqtt_sensor_data
    
    # Always try to get live MQTT data
    if not mqtt_connected:
        print("🔗 Connecting to MQTT for live sensor data...")
        if setup_mqtt():
            print("⏳ Waiting for MQTT data...")
            time.sleep(3)  # Wait for some data to come in
        else:
            print("❌ Failed to connect to MQTT")
            return mqtt_sensor_data  # Return default values
    
    return mqtt_sensor_data

def print_current_readings(sensor_data=None):
    """
    Print current sensor readings to thermal printer
    
    Args:
        sensor_data (dict): Dictionary containing current sensor readings from frontend status cards.
                           If None, will try to get current data automatically from MQTT.
        
    Returns:
        dict: Result of print operation with success status and message
    """
    try:
        # If no sensor data provided, get current data from MQTT
        if sensor_data is None:
            print("📡 No sensor data provided, getting live MQTT data...")
            sensor_data = get_current_sensor_data()
        else:
            print(f"📊 Using sensor data from frontend status cards: {sensor_data}")
        
        # Initialize printer for this print job
        printer = initialize_printer()
        
        if not printer:
            return {
                'success': False,
                'message': 'Printer not available or failed to initialize'
            }
        
        # Extract values as displayed in status cards (captured or live values)
        temp = sensor_data.get('temp', {}).get('value', None)
        bpm = sensor_data.get('bpm', {}).get('value', None)
        alcohol = sensor_data.get('alcohol', {}).get('value', None)
        weight = sensor_data.get('weight_value', {}).get('value', None)
        distance = sensor_data.get('distance', {}).get('value', None)
        
        print(f"🌡️  Temperature: {temp}")
        print(f"💓 BPM: {bpm}")
        print(f"🍷 Alcohol: {alcohol}")
        print(f"⚖️  Weight: {weight}")
        print(f"📏 Distance: {distance}")
        
        # Format values for printing (match dashboard formatting exactly)
        def fmt(val, decimals=2, default='--'):
            try:
                if val is None:
                    return default
                val = float(val)
                if decimals == 0:
                    return str(int(round(val)))
                return f"{val:.{decimals}f}"
            except Exception:
                return default
        
        print_text = "BOTIBOT HEALTH REPORT\n"
        print_text += "=" * 32 + "\n"
        print_text += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        print_text += "=" * 32 + "\n\n"
        print_text += "STATUS CARD VALUES:\n"
        print_text += "-" * 32 + "\n"
        print_text += f"Temperature: {fmt(temp, 2)} °C\n"
        print_text += f"Heart Rate: {fmt(bpm, 0)} BPM\n"
        print_text += f"Alcohol Level: {fmt(alcohol, 2)}\n"
        print_text += f"  Status: {get_alcohol_description(alcohol or 0)}\n"
        print_text += f"Weight: {fmt(weight, 2)} g\n"
        print_text += f"Distance: {fmt(distance, 2)} mm\n"
        print_text += "\n" + "-" * 32 + "\n"
        print_text += "Note: Captured values are\nshown as locked on dashboard\n"
        print_text += "=" * 32 + "\n"
        print_text += "BOTIBOT Health Monitor\n"
        print_text += "www.botibot.com\n"
        print_text += "=" * 32 + "\n"
        
        # Print to thermal printer
        print("Printing health report with status card values...")
        print(f"Print content:\n{print_text}")
        
        try:
            printer.text(print_text)
            printer.cut()
            print("✓ Print successful")
            
            # Properly close the printer connection
            try:
                printer.close()
                print("✓ Printer connection closed")
            except:
                pass  # Ignore close errors
            
            return {
                'success': True,
                'message': 'Health report printed successfully',
                'printed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as print_error:
            try:
                printer.close()
            except:
                pass
            raise print_error
        
    except Exception as e:
        error_msg = f"Print error: {str(e)}"
        print(f"❌ {error_msg}")
        
        # Additional troubleshooting info for resource busy errors
        if "Resource busy" in str(e) or "errno 16" in str(e):
            error_msg += "\n💡 Printer troubleshooting:"
            error_msg += "\n  • Another process may be using the printer"
            error_msg += "\n  • Try waiting a few seconds and try again"
            error_msg += "\n  • Check if any other print jobs are running"
            error_msg += "\n  • Restart the application if problem persists"
        
        return {
            'success': False,
            'message': error_msg
        }

def print_medication_schedule(user_id, medications_data=None):
    try:
        # Initialize printer for this print job
        printer = initialize_printer()
        
        if not printer:
            return {
                'success': False,
                'message': 'Printer not available or failed to initialize'
            }
        
        # If no medication data provided, we'll use what's passed from the endpoint
        if medications_data is None:
            medications_data = []
        
        # Get user name from session storage (if available)
        # user_name = "Patient"
        
        # Format days helper
        day_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
        
        # Start building print content
        print_text = "BOTIBOT MEDICATION SCHEDULE\n"
        print_text += "=" * 32 + "\n"
        print_text += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        # print_text += f"Patient: {user_name}\n"
        print_text += "=" * 32 + "\n\n"
        
        if not medications_data or len(medications_data) == 0:
            print_text += "No active medications found.\n"
            print_text += "\nPlease add medications to\n"
            print_text += "your schedule through the\n"
            print_text += "BOTIBOT dashboard.\n"
        else:
            print_text += f"ACTIVE MEDICATIONS ({len(medications_data)}):\n"
            print_text += "-" * 32 + "\n"
            
            for i, med in enumerate(medications_data, 1):
                print_text += f"{i}. {med.get('medication_name', 'Unknown')}\n"
                print_text += f"   Dosage: {med.get('dosage', 'Not specified')}\n"
                
                # Format times
                times = med.get('times', [])
                if times:
                    formatted_times = []
                    for time_str in times:
                        try:
                            # Parse time and convert to 12-hour format
                            hour, minute = map(int, time_str.split(':'))
                            period = 'AM' if hour < 12 else 'PM'
                            display_hour = hour if hour <= 12 else hour - 12
                            if display_hour == 0:
                                display_hour = 12
                            formatted_times.append(f"{display_hour}:{minute:02d}{period}")
                        except:
                            formatted_times.append(time_str)
                    
                    print_text += f"   Times: {', '.join(formatted_times)}\n"
                
                # Format frequency and days
                frequency = med.get('frequency', 'daily')
                if frequency == 'specific_days':
                    days_of_week = med.get('days_of_week', [])
                    active_days = [day_names[day] for day in days_of_week if 0 <= day < 7]
                    if active_days:
                        print_text += f"   Days: {', '.join(active_days)}\n"
                else:
                    print_text += f"   Frequency: Daily\n"
                
                # Add dates if available
                start_date = med.get('start_date')
                end_date = med.get('end_date')
                if start_date:
                    try:
                        start_formatted = datetime.fromisoformat(start_date.replace('Z', '+00:00')).strftime('%m/%d/%Y')
                        print_text += f"   Start: {start_formatted}\n"
                    except:
                        print_text += f"   Start: {start_date}\n"
                
                if end_date:
                    try:
                        end_formatted = datetime.fromisoformat(end_date.replace('Z', '+00:00')).strftime('%m/%d/%Y')
                        print_text += f"   End: {end_formatted}\n"
                    except:
                        print_text += f"   End: {end_date}\n"
                
                # Add reminder status
                if med.get('reminder_enabled', False):
                    print_text += f"   Reminders: ON\n"
                
                # Add notes if available
                notes = med.get('notes', '').strip()
                if notes:
                    # Limit notes length for printing
                    if len(notes) > 50:
                        notes = notes[:47] + "..."
                    print_text += f"   Notes: {notes}\n"
                
                print_text += "\n"  # Space between medications
        
        print_text += "=" * 32 + "\n"
        print_text += "BOTIBOT Health Monitor\n"
        print_text += "Stay on track with your\n"
        print_text += "medication schedule!\n"
        print_text += "=" * 32 + "\n"
        
        # Print to thermal printer
        print("Printing medication schedule...")
        print(f"Print content:\n{print_text}")
        
        printer.text(print_text)
        printer.cut()
        
        print("✓ Schedule print successful")
        
        return {
            'success': True,
            'message': 'Medication schedule printed successfully',
            'printed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'medication_count': len(medications_data)
        }
        
    except Exception as e:
        error_msg = f"Schedule print error: {str(e)}"
        print(f"❌ {error_msg}")
        return {
            'success': False,
            'message': error_msg
        }

# MQTT callback functions - Compatible with older paho-mqtt versions
def on_connect(client, userdata, flags, rc):
    global mqtt_connected
    if rc == 0:
        mqtt_connected = True
        print(f"✓ Connected to MQTT broker: {MQTT_BROKER}:{MQTT_PORT}")
        
        # Subscribe to all relevant topics
        for topic_name, topic in MQTT_TOPICS.items():
            client.subscribe(topic)
            print(f"  📥 Subscribed to {topic}")
    else:
        print(f"❌ Failed to connect to MQTT broker (RC: {rc})")

def on_message(client, userdata, msg):
    global mqtt_sensor_data
    topic = msg.topic
    try:
        payload = msg.payload.decode()
        timestamp = datetime.now().isoformat()
        
        print(f"📊 Received from {topic}: {payload}")
        
        # Process different topics
        if topic == MQTT_TOPICS['gyro']:
            data = json.loads(payload)
            mqtt_sensor_data['gyro'] = {**data, 'timestamp': timestamp}
        elif topic == MQTT_TOPICS['accel']:
            data = json.loads(payload)
            mqtt_sensor_data['accel'] = {**data, 'timestamp': timestamp}
        elif topic == MQTT_TOPICS['temp']:
            # Handle both JSON and simple float formats
            try:
                temp_data = json.loads(payload)
                if isinstance(temp_data, dict):
                    if 'temp' in temp_data:
                        temp_value = float(temp_data['temp'])
                    elif 'temperature' in temp_data:
                        temp_value = float(temp_data['temperature'])
                    else:
                        temp_value = float(list(temp_data.values())[0])
                else:
                    temp_value = float(temp_data)
            except json.JSONDecodeError:
                temp_value = float(payload)
            mqtt_sensor_data['temp'] = {'value': temp_value, 'timestamp': timestamp}
        elif topic == MQTT_TOPICS['distance']:
            mqtt_sensor_data['distance'] = {'value': float(payload), 'timestamp': timestamp}
        elif topic == MQTT_TOPICS['weight_value']:
            mqtt_sensor_data['weight_value'] = {'value': float(payload), 'timestamp': timestamp}
        elif topic == MQTT_TOPICS['weight_status']:
            mqtt_sensor_data['weight_status'] = {'status': payload, 'timestamp': timestamp}
        elif topic == MQTT_TOPICS['gyro_y']:
            mqtt_sensor_data['gyro_y'] = {'value': float(payload), 'timestamp': timestamp}
        elif topic == MQTT_TOPICS['gyro_z']:
            mqtt_sensor_data['gyro_z'] = {'value': float(payload), 'timestamp': timestamp}
        elif topic == MQTT_TOPICS['load']:
            mqtt_sensor_data['load'] = {'value': float(payload), 'timestamp': timestamp}
        elif topic == MQTT_TOPICS['bpm']:
            bpm_value = float(payload)
            mqtt_sensor_data['bpm'] = {'value': bpm_value, 'timestamp': timestamp}
        elif topic == MQTT_TOPICS['alcohol']:
            # Handle both JSON and simple float formats (like your working code)
            try:
                alcohol_data = json.loads(payload)
                if isinstance(alcohol_data, dict) and 'alcohol_level' in alcohol_data:
                    alcohol_value = float(alcohol_data['alcohol_level'])
                elif isinstance(alcohol_data, dict) and 'alcohol' in alcohol_data:
                    alcohol_value = float(alcohol_data['alcohol'])
                else:
                    alcohol_value = float(payload)
            except json.JSONDecodeError:
                alcohol_value = float(payload)
            mqtt_sensor_data['alcohol'] = {'value': alcohol_value, 'timestamp': timestamp}
        
    except Exception as e:
        print(f"⚠️ Error processing message from {topic}: {e}")

def on_disconnect(client, userdata, rc):
    global mqtt_connected
    mqtt_connected = False
    if rc != 0:  # Only show message for unexpected disconnections
        print(f"❌ Unexpected disconnection from MQTT broker (RC: {rc})")
    else:
        print("🔌 MQTT connection closed cleanly")

def setup_mqtt():
    """Setup and start MQTT client for independent operation"""
    global mqtt_client
    
    # Use standard MQTT client (compatible with older paho-mqtt versions)
    try:
        mqtt_client = mqtt.Client()
        mqtt_client.on_connect = on_connect
        mqtt_client.on_message = on_message
        mqtt_client.on_disconnect = on_disconnect
        
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
        mqtt_client.loop_start()
        print(f"🔗 MQTT client started for {MQTT_BROKER}:{MQTT_PORT}")
        return True
    except Exception as e:
        print(f"❌ MQTT connection failed: {e}")
        return False

def stop_mqtt():
    """Stop MQTT client"""
    global mqtt_client, mqtt_connected
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        mqtt_connected = False
        print("🔌 MQTT client disconnected")

def get_live_sensor_data():
    """Get live sensor data from MQTT"""
    global mqtt_sensor_data
    
    if not mqtt_connected:
        print("⚠️ MQTT not connected, setting up connection...")
        if setup_mqtt():
            print("⏳ Waiting for MQTT data...")
            time.sleep(3)  # Wait for some data to come in
        else:
            print("❌ Failed to connect to MQTT")
    
    return mqtt_sensor_data

# For backwards compatibility and testing
if __name__ == "__main__":
    print("🖨️ BotiBot Thermal Printer - Live MQTT Mode")
    print("=" * 40)
    
    # Always use live MQTT data
    print("📡 Connecting to live MQTT sensor data...")
    if setup_mqtt():
        # Wait for connection and data reception
        print("⏳ Waiting for sensor data...")
        time.sleep(3)
        sensor_data = mqtt_sensor_data
    else:
        print("❌ MQTT connection failed - cannot proceed without live data")
        print("Please check:")
        print("  • ESP32 is powered on and broadcasting")
        print("  • WiFi connection to 192.168.4.1")
        print("  • MQTT broker is running on ESP32")
        sys.exit(1)
    
    print(f"📋 Live sensor data received:")
    for key, value in sensor_data.items():
        if isinstance(value, dict) and 'value' in value:
            print(f"  {key}: {value['value']}")
    
    print("\n🖨️ Starting print job...")
    result = print_current_readings(sensor_data)
    print("=" * 40)
    print("📋 Print result:", result)
    
    if result['success']:
        print("✅ Print completed successfully!")
    else:
        print("❌ Print failed!")
        print(f"   Error: {result['message']}")
        if "Device not found" in result['message']:
            print("💡 Printer troubleshooting:")
            print("  • Check USB cable connection")
            print("  • Verify printer power")
            print("  • Run 'lsusb' to confirm device detection")
    
    # Clean up MQTT connection
    if mqtt_connected:
        stop_mqtt()
    
    print(f"\n📡 MQTT Data Source: {MQTT_BROKER}:{MQTT_PORT}")
    print("🔗 Always connects to live ESP32 sensor data")
