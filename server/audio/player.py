"""
Audio Player for BotiBot
Handles sound playback with proper error handling and fallbacks
"""

import os
import time
from playsound import playsound
from typing import Optional
from botibot.config.audio_config import SOUND_PATHS, AUDIO_CONFIG

class AudioPlayer:
    """
    Handles audio playback for BotiBot with proper error handling
    """
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.sound_paths = SOUND_PATHS
        self.config = AUDIO_CONFIG
        # Get the base directory for sounds (now in audio/sounds)
        self.sounds_base_dir = os.path.join(os.path.dirname(__file__), 'sounds')
        
    def _resolve_sound_path(self, sound_name: str) -> Optional[str]:
        """
        Resolve sound path, checking both config paths and sounds folder
        
        Args:
            sound_name: Name of sound or path
            
        Returns:
            Optional[str]: Resolved path or None if not found
        """
        # Check if it's a direct path that exists
        if os.path.exists(sound_name):
            return sound_name
            
        # Check if it's in sound_paths config
        if sound_name in self.sound_paths:
            config_path = self.sound_paths[sound_name]
            # If config path is absolute and exists, use it
            if os.path.isabs(config_path) and os.path.exists(config_path):
                return config_path
            # Otherwise, try relative to sounds folder
            sounds_folder_path = os.path.join(self.sounds_base_dir, os.path.basename(config_path))
            if os.path.exists(sounds_folder_path):
                return sounds_folder_path
        
        # Try in sounds folder with sound_name as filename
        sounds_folder_path = os.path.join(self.sounds_base_dir, sound_name)
        if os.path.exists(sounds_folder_path):
            return sounds_folder_path
            
        # Try common audio extensions
        for ext in ['.wav', '.mp3', '.ogg']:
            test_path = os.path.join(self.sounds_base_dir, f"{sound_name}{ext}")
            if os.path.exists(test_path):
                return test_path
        
        return None
        
    def play_sound(self, sound_name: str, fallback_path: Optional[str] = None) -> bool:
        """
        Play a sound by name with fallback options
        
        Args:
            sound_name: Key from SOUND_PATHS or direct file path
            fallback_path: Alternative path if primary fails
            
        Returns:
            bool: True if sound played successfully
        """
        # Resolve the sound path
        sound_path = self._resolve_sound_path(sound_name)
        
        # Try fallback if primary resolution failed
        if not sound_path and fallback_path:
            sound_path = self._resolve_sound_path(fallback_path)
        
        if not sound_path:
            if self.verbose:
                print(f"❌ Sound not found: {sound_name}")
            return False
        
        # Attempt to play with retries
        for attempt in range(self.config["retry_attempts"]):
            try:
                if self.verbose:
                    print(f"🔊 Playing sound: {os.path.basename(sound_path)}")
                
                playsound(sound_path)
                return True
                
            except Exception as e:
                if self.verbose:
                    print(f"❌ Audio playback failed (attempt {attempt + 1}): {e}")
                
                if attempt < self.config["retry_attempts"] - 1:
                    time.sleep(0.5)  # Brief pause before retry
        
        return False
    
    def play_health_alert(self, alert_type: str) -> bool:
        """
        Play health-related alert sounds
        
        Args:
            alert_type: Type of health alert (bpm, temperature, etc.)
            
        Returns:
            bool: True if sound played successfully
        """
        sound_map = {
            "high_bpm": "warning_abnormal_heart_rate",
            "normal_bpm": "pulse_detected",
            "high_temp": "warning_high_temperature",
            "temp_measure": "measuring_temperature",
            "alcohol_detected": "alcohol_detected_blocked",
            "alcohol_disabled": "alcohol_detected_disabled"
        }
        
        if alert_type in sound_map:
            return self.play_sound(sound_map[alert_type])
        
        if self.verbose:
            print(f"❌ Unknown health alert type: {alert_type}")
        return False
    
    def play_motion_alert(self) -> bool:
        """Play motion detection sound"""
        return self.play_sound("motion_detected")
    
    def play_medication_alert(self, med_type: str = "time_to_take") -> bool:
        """
        Play medication-related sounds
        
        Args:
            med_type: Type of medication alert
            
        Returns:
            bool: True if sound played successfully
        """
        sound_map = {
            "time_to_take": "time_to_take_medicine",
            "dispensing": "dispensing_medicine",
            "complete": "dispensing_complete",
            "confirmed": "dosage_confirmed",
            "delayed": "medication_delayed"
        }
        
        if med_type in sound_map:
            return self.play_sound(sound_map[med_type])
        
        if self.verbose:
            print(f"❌ Unknown medication alert type: {med_type}")
        return False
    
    def play_system_status(self, status_type: str) -> bool:
        """
        Play system status sounds
        
        Args:
            status_type: Type of system status
            
        Returns:
            bool: True if sound played successfully
        """
        sound_map = {
            "online": "system_online",
            "setup_complete": "setup_complete",
            "sensors_active": "sensors_active",
            "error": "error_check_wiring",
            "scan_start": "initializing_health_scan"
        }
        
        if status_type in sound_map:
            return self.play_sound(sound_map[status_type])
        
        if self.verbose:
            print(f"❌ Unknown system status type: {status_type}")
        return False
    
    def play_user_interaction(self, interaction_type: str) -> bool:
        """
        Play user interaction sounds
        
        Args:
            interaction_type: Type of user interaction
            
        Returns:
            bool: True if sound played successfully
        """
        sound_map = {
            "identified": "user_identified",
            "touch_screen": "touch_screen_to_begin",
            "press_button": "press_button_to_confirm",
            "do_not_move": "do_not_move"
        }
        
        if interaction_type in sound_map:
            return self.play_sound(sound_map[interaction_type])
        
        if self.verbose:
            print(f"❌ Unknown user interaction type: {interaction_type}")
        return False
    
    def test_all_sounds(self) -> dict:
        """
        Test all available sounds
        
        Returns:
            dict: Results of sound tests
        """
        results = {}
        
        if self.verbose:
            print("🧪 Testing all sounds...")
            print(f"Sounds base directory: {self.sounds_base_dir}")
        
        for sound_name, sound_path in self.sound_paths.items():
            if self.verbose:
                print(f"Testing: {sound_name}")
            
            resolved_path = self._resolve_sound_path(sound_name)
            success = self.play_sound(sound_name)
            results[sound_name] = {
                "success": success,
                "original_path": sound_path,
                "resolved_path": resolved_path,
                "exists": resolved_path and os.path.exists(resolved_path)
            }
            
            if not success:
                if self.verbose:
                    print(f"❌ Failed: {sound_name}")
            else:
                if self.verbose:
                    print(f"✅ Success: {sound_name}")
            
            # Small delay between sounds
            time.sleep(1)
        
        return results
    
    def list_available_sounds(self) -> list:
        """
        List all available sounds
        
        Returns:
            list: List of available sound names
        """
        return list(self.sound_paths.keys())
    
    def get_sound_path(self, sound_name: str) -> Optional[str]:
        """
        Get the full path for a sound name
        
        Args:
            sound_name: Name of the sound
            
        Returns:
            Optional[str]: Full path to sound file or None if not found
        """
        return self._resolve_sound_path(sound_name)