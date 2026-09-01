"""
AI Call Assistant - Phase 2 Engine Diagnostic

Tests the complete Phase 2 foundational audio pipeline:
1. Resolves dynamic WASAPI loopback & VB-Cable devices by name
2. Simulates / tracks a complete Call Session in SQLite
3. Injects a 3-second chime to the caller via VB-Cable
4. Continuously runs WASAPI Loopback + VAD for 10 seconds while caller speaks
5. Segments caller speech into timestamped turn files (segment_001.wav, segment_002.wav, etc.)
6. Saves the master call recording
7. Prints a full diagnostic report verifying VAD turn detection and database logging

Usage:
  1. Call is ACTIVE in Phone Link with the caller on the line.
  2. Run:
     python backend/diagnostic/test_phase2_engine.py
"""

import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import settings
from backend.storage import db
from backend.audio.device_manager import DeviceManager
from backend.audio.session_manager import session_manager

def run_phase2_diagnostic():
    print()
    print("=" * 70)
    print("  PHASE 2 FOUNDATIONAL AUDIO ENGINE & VAD DIAGNOSTIC")
    print("=" * 70)

    # 1. Check Device Discovery
    loopback, uplink = DeviceManager.get_devices()
    print(f"  Downlink Device (WASAPI Loopback): {loopback.name if loopback else '[FAIL] Not Found'}")
    print(f"  Uplink Device (VB-Cable):          {uplink.name if uplink else '[FAIL] Not Found'}")
    print()

    if not loopback or not uplink:
        print("  [ERROR] Required audio devices could not be resolved.")
        print("  Ensure VB-Cable is installed and Speakers are active.")
        sys.exit(1)

    print("  --> INSTRUCTIONS FOR PHYSICAL TEST:")
    print("      1. Keep the Phone Link call ACTIVE with your phone.")
    print("      2. When the test starts, the caller will hear a chime on their phone.")
    print("      3. After the chime, the caller should speak 2 separate sentences with pauses:")
    print("         Sentence 1: 'Hello, this is a test call.'")
    print("         (pause for 1-2 seconds)")
    print("         Sentence 2: 'Can you hear me clearly?'")
    print()

    input("  Press ENTER when the call is ready...")

    # 2. Simulate Incoming & Answered Telephony Events
    test_number = "+91-TEST-PHASE2"
    print("\n  [1/4] Triggering Call Session Start...", flush=True)
    session_manager.handle_telephony_event("incoming_call", {"number": test_number})
    time.sleep(0.5)
    session_manager.handle_telephony_event("call_answered", {"number": test_number})

    # 3. Inject Chime to Caller
    print("  [2/4] Injecting chime to caller via VB-Cable...", flush=True)
    session_manager.player.play_test_chime(duration_sec=3.0)

    # 4. Listen and run VAD for 10 seconds
    print("  [3/4] Chime sent. Listening for caller speech & running VAD for 10s...", flush=True)
    print("        --> CALLER SHOULD SPEAK 2 SENTENCES WITH A PAUSE NOW! <--")
    
    for sec in range(10, 0, -1):
        print(f"\r        Listening... {sec:2d}s remaining [Segments detected so far: {session_manager.segment_counter}]", end="", flush=True)
        time.sleep(1.0)
    print()

    # 5. End Call Session
    print("\n  [4/4] Ending Call Session and finalizing database records...", flush=True)
    session_manager.handle_telephony_event("call_ended", {"number": test_number, "duration": 10.5})

    # 6. Verify Results
    time.sleep(0.5)
    conn = db.get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM call_sessions ORDER BY start_time DESC LIMIT 1")
    session_row = cursor.fetchone()

    cursor.execute("SELECT * FROM speech_segments WHERE session_id = ?", (session_row["session_id"],))
    segments = cursor.fetchall()
    conn.close()

    print()
    print("=" * 70)
    print("  PHASE 2 DIAGNOSTIC REPORT")
    print("=" * 70)
    print(f"  Session ID:               {session_row['session_id']}")
    print(f"  Session State:            {session_row['state']}")
    print(f"  Master Recording:         {session_row['recording_path']}")
    print(f"  VAD Speech Turns Saved:   {len(segments)}")
    print()

    for idx, seg in enumerate(segments, 1):
        print(f"    Segment #{idx}: Duration = {seg['duration_sec']:.2f}s, File: {Path(seg['audio_file_path']).name}")

    print("-" * 70)
    vad_passed = len(segments) >= 1
    master_rec_passed = session_row['recording_path'] is not None and Path(session_row['recording_path']).exists()

    if vad_passed and master_rec_passed:
        print("  STATUS: [PASS] Phase 2 Audio Engine & VAD segmentation fully functional!")
        print("  -> The caller's speech turns were automatically segmented into WAV files.")
        print("  -> Master recording and database records were successfully created.")
    else:
        print("  STATUS: [WARN] Segments were not detected. Ensure caller spoke audibly during seconds 3-10.")
    print("=" * 70)

if __name__ == "__main__":
    run_phase2_diagnostic()
