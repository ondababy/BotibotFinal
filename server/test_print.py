#!/usr/bin/env python3
"""
Simple test script to test thermal printer functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from print import print_current_readings

def test_print():
    """Test the print functionality"""
    print("🧪 Testing thermal printer functionality...")
    
    # Test data
    test_sensor_data = {
        'temp': {'value': 36.5, 'timestamp': '2025-08-08T08:42:00'},
        'bpm': {'value': 72, 'timestamp': '2025-08-08T08:42:00'},
        'alcohol': {'value': 0.0, 'timestamp': '2025-08-08T08:42:00'},
        'weight_value': {'value': 70.5, 'timestamp': '2025-08-08T08:42:00'},
        'distance': {'value': 15.2, 'timestamp': '2025-08-08T08:42:00'},
    }
    
    print("📋 Test sensor data:")
    for key, value in test_sensor_data.items():
        print(f"  {key}: {value['value']}")
    
    print("\n🖨️ Attempting to print...")
    result = print_current_readings(test_sensor_data)
    
    print("\n📋 Print result:")
    print(f"  Success: {result['success']}")
    print(f"  Message: {result['message']}")
    
    if result['success']:
        print("✅ Print test successful!")
        return True
    else:
        print("❌ Print test failed!")
        return False

if __name__ == "__main__":
    success = test_print()
    sys.exit(0 if success else 1)
