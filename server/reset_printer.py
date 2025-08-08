#!/usr/bin/env python3
"""
Utility script to reset thermal printer when it gets stuck with "Resource busy" error
"""

import subprocess
import time
import sys

def reset_thermal_printer():
    """Reset the thermal printer USB connection"""
    
    print("🔄 Resetting thermal printer...")
    
    try:
        # Method 1: Find and reset USB device
        print("📍 Finding USB printer device...")
        result = subprocess.run(['lsusb'], capture_output=True, text=True)
        
        if "Printer" in result.stdout or "0483:5840" in result.stdout:
            print("✓ Printer device found")
            
            # Try to reset using usbreset if available
            try:
                # Find usbreset command
                usbreset_result = subprocess.run(['which', 'usbreset'], capture_output=True, text=True)
                if usbreset_result.returncode == 0:
                    print("🔄 Using usbreset command...")
                    subprocess.run(['sudo', 'usbreset', '0483:5840'], timeout=10)
                    print("✓ USB reset completed")
                else:
                    print("⚠️ usbreset not found, trying alternative method...")
                    raise FileNotFoundError
                    
            except (FileNotFoundError, subprocess.TimeoutExpired):
                # Alternative method: unbind and rebind USB driver
                print("🔄 Using driver unbind/rebind method...")
                
                # Find the USB device path
                bus_result = subprocess.run(['find', '/sys/bus/usb/devices/', '-name', '*0483:5840*'], 
                                          capture_output=True, text=True)
                
                if bus_result.stdout.strip():
                    device_path = bus_result.stdout.strip().split('\n')[0]
                    print(f"📍 Device path: {device_path}")
                    
                    # Try to unbind
                    try:
                        subprocess.run(['sudo', 'bash', '-c', f'echo "{device_path.split("/")[-1]}" > /sys/bus/usb/drivers/usblp/unbind'], 
                                     timeout=5, capture_output=True)
                        print("✓ Device unbound")
                        time.sleep(2)
                        
                        # Try to rebind
                        subprocess.run(['sudo', 'bash', '-c', f'echo "{device_path.split("/")[-1]}" > /sys/bus/usb/drivers/usblp/bind'], 
                                     timeout=5, capture_output=True)
                        print("✓ Device rebound")
                        time.sleep(2)
                        
                    except subprocess.TimeoutExpired:
                        print("⚠️ Unbind/rebind timeout")
                
        else:
            print("⚠️ Printer device not found in lsusb output")
            
        # Method 2: Kill any processes that might be using the printer
        print("🔍 Checking for processes using printer...")
        try:
            fuser_result = subprocess.run(['sudo', 'fuser', '/dev/usb/lp0'], 
                                        capture_output=True, text=True, timeout=5)
            if fuser_result.stdout.strip():
                print(f"📋 Processes using printer: {fuser_result.stdout.strip()}")
                # Kill the processes
                subprocess.run(['sudo', 'fuser', '-k', '/dev/usb/lp0'], timeout=5)
                print("✓ Killed processes using printer")
                time.sleep(2)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("⚠️ Could not check/kill printer processes")
            
        # Method 3: Restart USB subsystem (if needed)
        print("🔄 Refreshing USB subsystem...")
        try:
            subprocess.run(['sudo', 'modprobe', '-r', 'usblp'], timeout=5, capture_output=True)
            time.sleep(1)
            subprocess.run(['sudo', 'modprobe', 'usblp'], timeout=5, capture_output=True)
            print("✓ USB printer driver refreshed")
            time.sleep(2)
        except subprocess.TimeoutExpired:
            print("⚠️ Could not refresh USB driver")
        
        print("✅ Printer reset complete! Try printing again.")
        return True
        
    except Exception as e:
        print(f"❌ Reset failed: {e}")
        return False

if __name__ == "__main__":
    success = reset_thermal_printer()
    sys.exit(0 if success else 1)
