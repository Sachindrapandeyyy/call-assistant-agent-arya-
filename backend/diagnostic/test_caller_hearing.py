"""
Test script to send a direct spoken greeting through VB-Cable to the caller.
Use this while a phone call is active in Phone Link to verify the caller hears the AI voice.
"""

import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Force UTF-8 encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from backend.tts.tts_engine import tts_engine
from backend.audio.cable_player import cable_player

def test_speech_injection():
    print("==================================================================")
    print("  CALLER AUDIO HEARING TEST (Laptop -> Phone Call)")
    print("==================================================================")
    print("  Testing audio injection through CABLE Input to Phone Link...")
    print()
    
    test_phrase = "Hello! Namaste, main Sachindra ki personal assistant hoon. Kya aapko meri aawaz saaf sunayi de rahi hai?"
    print(f"  [>] Synthesizing test voice: \"{test_phrase}\"")
    
    audio_data, latency = tts_engine.synthesize_to_numpy(test_phrase, target_sample_rate=48000)
    
    if audio_data is None or len(audio_data) == 0:
        print("  ❌ Failed to generate TTS audio!")
        return

    duration = len(audio_data) / 48000.0
    print(f"  [+] Generated {duration:.1f}s of audio in {latency:.2f}s.")
    print("  [>] Playing directly into CABLE Input (VB-Audio Virtual Cable)...")
    print("  --> Listen to your phone receiver now! <--")
    
    cable_player.play_audio_blocking(audio_data, source_sample_rate=48000)
    
    print("\n  ✅ Playback finished!")
    print("==================================================================")

if __name__ == "__main__":
    test_speech_injection()
