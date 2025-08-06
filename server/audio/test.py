#!/usr/bin/env python3
"""
Test script for AudioPlayer functionality
Tests sound resolution, playback, and error handling
"""

import os
import sys
import time
from pathlib import Path

# Add the project root to path so we can import botibot modules
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from botibot.audio.player import AudioPlayer

def test_audio_player():
    """Test basic AudioPlayer functionality"""
    print("🧪 Testing AudioPlayer...")
    
    # Test with verbose output
    player = AudioPlayer(verbose=True)
    
    print(f"Sounds base directory: {player.sounds_base_dir}")
    print(f"Directory exists: {os.path.exists(player.sounds_base_dir)}")
    
    # List available sounds
    print("\n📋 Available sounds:")
    available_sounds = player.list_available_sounds()
    for sound in available_sounds:
        sound_path = player.get_sound_path(sound)
        exists = "✅" if sound_path and os.path.exists(sound_path) else "❌"
        print(f"  {exists} {sound}: {sound_path}")
    
    return player

def test_individual_sounds(player):
    """Test individual sound categories"""
    print("\n🔊 Testing individual sound categories...")
    
    # Test health alerts
    print("\n💓 Testing health alerts:")
    health_tests = [
        ("high_bpm", "High BPM alert"),
        ("normal_bpm", "Normal BPM sound"),
        ("high_temp", "High temperature alert"),
        ("temp_measure", "Temperature measurement"),
        ("alcohol_detected", "Alcohol detected"),
        ("alcohol_disabled", "Alcohol disabled")
    ]
    
    for alert_type, description in health_tests:
        print(f"  Testing {description}...")
        success = player.play_health_alert(alert_type)
        print(f"    Result: {'✅ Success' if success else '❌ Failed'}")
        time.sleep(1)
    
    # Test motion alerts
    print("\n🚶 Testing motion detection:")
    success = player.play_motion_alert()
    print(f"  Motion alert: {'✅ Success' if success else '❌ Failed'}")
    time.sleep(1)
    
    # Test medication alerts
    print("\n💊 Testing medication alerts:")
    med_tests = [
        ("time_to_take", "Time to take medicine"),
        ("dispensing", "Dispensing medicine"),
        ("complete", "Dispensing complete"),
        ("confirmed", "Dosage confirmed"),
        ("delayed", "Medication delayed")
    ]
    
    for med_type, description in med_tests:
        print(f"  Testing {description}...")
        success = player.play_medication_alert(med_type)
        print(f"    Result: {'✅ Success' if success else '❌ Failed'}")
        time.sleep(1)
    
    # Test system status
    print("\n⚙️ Testing system status:")
    status_tests = [
        ("online", "System online"),
        ("setup_complete", "Setup complete"),
        ("sensors_active", "Sensors active"),
        ("error", "Error check wiring"),
        ("scan_start", "Initializing health scan")
    ]
    
    for status_type, description in status_tests:
        print(f"  Testing {description}...")
        success = player.play_system_status(status_type)
        print(f"    Result: {'✅ Success' if success else '❌ Failed'}")
        time.sleep(1)
    
    # Test user interactions
    print("\n👤 Testing user interactions:")
    interaction_tests = [
        ("identified", "User identified"),
        ("touch_screen", "Touch screen to begin"),
        ("press_button", "Press button to confirm"),
        ("do_not_move", "Do not move")
    ]
    
    for interaction_type, description in interaction_tests:
        print(f"  Testing {description}...")
        success = player.play_user_interaction(interaction_type)
        print(f"    Result: {'✅ Success' if success else '❌ Failed'}")
        time.sleep(1)

def test_error_handling(player):
    """Test error handling and fallbacks"""
    print("\n⚠️ Testing error handling...")
    
    # Test non-existent sound
    print("  Testing non-existent sound...")
    success = player.play_sound("non_existent_sound")
    print(f"    Result: {'❌ Failed (expected)' if not success else '✅ Unexpected success'}")
    
    # Test invalid alert types
    print("  Testing invalid alert types...")
    invalid_tests = [
        ("invalid_health", player.play_health_alert),
        ("invalid_med", player.play_medication_alert),
        ("invalid_status", player.play_system_status),
        ("invalid_interaction", player.play_user_interaction)
    ]
    
    for invalid_type, test_func in invalid_tests:
        success = test_func(invalid_type)
        print(f"    {test_func.__name__} with '{invalid_type}': {'❌ Failed (expected)' if not success else '✅ Unexpected success'}")

def test_all_sounds_comprehensive(player):
    """Run comprehensive sound test"""
    print("\n🎵 Running comprehensive sound test...")
    
    # Allow user to skip this test
    response = input("This will play all sounds. Continue? (y/n): ")
    if response.lower() != 'y':
        print("Skipping comprehensive sound test.")
        return
    
    results = player.test_all_sounds()
    
    print("\n📊 Test Results Summary:")
    success_count = sum(1 for r in results.values() if r["success"])
    total_count = len(results)
    
    print(f"Successful: {success_count}/{total_count}")
    print(f"Failed: {total_count - success_count}/{total_count}")
    
    # Show failed sounds
    failed_sounds = [name for name, result in results.items() if not result["success"]]
    if failed_sounds:
        print("\n❌ Failed sounds:")
        for sound in failed_sounds:
            result = results[sound]
            print(f"  - {sound}")
            print(f"    Original path: {result['original_path']}")
            print(f"    Resolved path: {result['resolved_path']}")
            print(f"    File exists: {result['exists']}")

def main():
    """Main test function"""
    print("🚀 BotiBot AudioPlayer Test Suite")
    print("=" * 50)
    
    try:
        # Initialize player
        player = test_audio_player()
        
        # Test individual components
        test_individual_sounds(player)
        
        # Test error handling
        test_error_handling(player)
        
        # Comprehensive test (optional)
        test_all_sounds_comprehensive(player)
        
        print("\n✅ Test suite completed!")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're running this from the project root directory.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
