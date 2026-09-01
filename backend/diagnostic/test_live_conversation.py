"""
AI Call Assistant - Full Live Conversation Diagnostic

Tests the complete end-to-end conversation loop:
Phone Call -> WASAPI Loopback -> VAD -> faster-whisper -> Qwen2.5-3B -> Female Indian TTS -> VB-Cable -> Caller.

Usage:
  1. Call is ACTIVE in Phone Link.
  2. Run:
     python backend/diagnostic/test_live_conversation.py
"""

import sys
import time
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import settings
from backend.audio.device_manager import DeviceManager
from backend.audio.session_manager import session_manager

def main():
    print()
    print("=" * 70)
    print("  AI PERSONAL CALL ASSISTANT — FULL CONVERSATION TEST")
    print("=" * 70)

    loopback, uplink = DeviceManager.get_devices()
    print(f"  Downlink (Capture): {loopback.name if loopback else '[FAIL] Not Found'}")
    print(f"  Uplink (VB-Cable):  {uplink.name if uplink else '[FAIL] Not Found'}")
    print()

    if not loopback or not uplink:
        print("  [ERROR] Audio devices not ready.")
        sys.exit(1)

    print("  --> INSTRUCTIONS:")
    print("      1. Keep the Phone Link call ACTIVE with the caller on the line.")
    print("      2. Press ENTER to simulate call answer.")
    print("      3. The AI Receptionist will speak the initial greeting to the caller:")
    print("         'Namaste, main Sachindra ki personal assistant hoon...'")
    print("      4. Speak back to the AI in Hindi, Hinglish, or English.")
    print("      5. Have a natural 30-45 second conversation (e.g. leave a message).")
    print("      6. Press CTRL+C when you want to hang up.")
    print()

    input("  Press ENTER to start the live conversation...")

    test_caller = "+91-TEST-CONVERSATION"
    print("\n  [CALL START] Answering call and starting AI receptionist...", flush=True)
    session_manager.handle_telephony_event("incoming_call", {"number": test_caller})
    time.sleep(0.5)
    session_manager.handle_telephony_event("call_answered", {"number": test_caller})

    print("\n  --> AI is actively in conversation with the caller. (Press CTRL+C to end call) <--\n")

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n\n  [CALL TERMINATION] Ending call session...")
        session_manager.handle_telephony_event("call_ended", {"number": test_caller, "duration": 35.0})
        print("\n  Session closed. Check above for full transcript and summary.")

if __name__ == "__main__":
    main()
