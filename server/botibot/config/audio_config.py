"""
Audio configuration for BotiBot
Defines sound file paths and audio settings
"""

import os

# Audio configuration settings
AUDIO_CONFIG = {
    "retry_attempts": 3,
    "default_volume": 0.8,
    "timeout_seconds": 10
}

# Base directory for audio files
AUDIO_BASE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'sounds')

# Sound file paths mapping
SOUND_PATHS = {
    # Health alerts
    "warning_abnormal_heart_rate": "warning_abnormal_heart_rate.wav",
    "pulse_detected": "pulse_detected.wav",
    "warning_high_temperature": "warning_high_temperature.wav",
    "measuring_temperature": "measuring_temperature.wav",
    "alcohol_detected_blocked": "alcohol_detected_blocked.wav",
    "alcohol_detected_disabled": "alcohol_detected_disabled.wav",
    
    # Motion detection
    "motion_detected": "motion_detected.wav",
    
    # Medication alerts
    "time_to_take_medicine": "time_to_take_medicine.wav",
    "dispensing_medicine": "dispensing_medicine.wav",
    "dispensing_complete": "dispensing_complete.wav",
    "dosage_confirmed": "dosage_confirmed.wav",
    "medication_delayed": "medication_delayed.wav",
    
    # System status
    "system_online": "system_online.wav",
    "setup_complete": "setup_complete.wav",
    "sensors_active": "sensors_active.wav",
    "error_check_wiring": "error_check_wiring.wav",
    "initializing_health_scan": "initializing_health_scan.wav",
    
    # User interactions
    "user_identified": "user_identified.wav",
    "touch_screen_to_begin": "touch_screen_to_begin.wav",
    "press_button_to_confirm": "press_button_to_confirm.wav",
    "do_not_move": "do_not_move.wav"
}
