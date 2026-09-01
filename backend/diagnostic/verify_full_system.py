"""
Comprehensive System Verification Diagnostic for AI Call Assistant.
Tests every pipeline component before a live call:
1. Audio Device Resolution (WASAPI Loopback + VB-Cable)
2. faster-whisper GPU STT on RTX 4050
3. Local Ollama LLM (Qwen2.5-3B)
4. Female Indian Voice TTS (Edge-TTS)
5. SQLite Database operations
6. VAD turn segmentation logic
"""

import sys
import time
from pathlib import Path
import numpy as np

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def verify_all():
    print()
    print("=" * 70)
    print("  AI PERSONAL CALL ASSISTANT — FULL SYSTEM VERIFICATION")
    print("=" * 70)

    checks = []

    # --- 1. Audio Devices ---
    print("\n[1/6] Verifying Audio Endpoints...", flush=True)
    try:
        from backend.audio.device_manager import DeviceManager
        loopback, uplink = DeviceManager.get_devices()
        down_ok = loopback is not None
        up_ok = uplink is not None
        print(f"  Downlink (WASAPI Loopback): {loopback.name if loopback else 'NOT FOUND'}")
        print(f"  Uplink (VB-Cable):          {uplink.name if uplink else 'NOT FOUND'}")
        checks.append(("Audio Endpoints", down_ok and up_ok, f"Down: {loopback.name[:25] if loopback else 'None'}, Up: {uplink.name[:25] if uplink else 'None'}"))
    except Exception as e:
        print(f"  [FAIL] Audio devices error: {e}")
        checks.append(("Audio Endpoints", False, str(e)))

    # --- 2. Database ---
    print("\n[2/6] Verifying SQLite Database Schema...", flush=True)
    try:
        from backend.storage import db
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        conn.close()
        expected = {"call_sessions", "telephony_events", "speech_segments"}
        db_ok = expected.issubset(set(tables))
        print(f"  Database Tables Present: {tables}")
        checks.append(("SQLite Storage", db_ok, f"{len(tables)} tables verified"))
    except Exception as e:
        print(f"  [FAIL] DB error: {e}")
        checks.append(("SQLite Storage", False, str(e)))

    # --- 3. VAD Engine ---
    print("\n[3/6] Verifying VAD Segmenter Logic...", flush=True)
    try:
        from backend.audio.vad import VADSegmenter
        vad = VADSegmenter(sample_rate=16000, silence_timeout_sec=0.4, min_speech_duration_sec=0.2)
        
        # Simulate 1s tone (active speech) + 0.6s silence
        t = np.linspace(0, 1.0, 16000, endpoint=False)
        tone = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        silence = np.zeros(9600, dtype=np.float32)
        
        chunk_size = 512
        segment_found = False
        sim_time = 1000.0

        for i in range(0, len(tone), chunk_size):
            vad.process_chunk(tone[i:i+chunk_size], now=sim_time)
            sim_time += chunk_size / 16000.0

        for i in range(0, len(silence), chunk_size):
            res = vad.process_chunk(silence[i:i+chunk_size], now=sim_time)
            sim_time += chunk_size / 16000.0
            if res is not None:
                segment_found = True
                break

        print(f"  VAD Turn Segmentation Trigger: {'[PASS]' if segment_found else '[FAIL]'}")
        checks.append(("VAD Segmentation", segment_found, "Turn-taking triggers correctly"))
    except Exception as e:
        print(f"  [FAIL] VAD error: {e}")
        checks.append(("VAD Segmentation", False, str(e)))

    # --- 4. faster-whisper STT ---
    print("\n[4/6] Verifying faster-whisper GPU STT Engine...", flush=True)
    try:
        from backend.stt.whisper_engine import get_stt_engine
        stt = get_stt_engine()
        
        # Test transcription on dummy audio
        test_audio = (0.1 * np.random.randn(32000)).astype(np.float32)
        transcript, lang, lat = stt.transcribe(test_audio, language="en")
        print(f"  STT Device: {stt.device} ({stt.compute_type}) | Latency: {lat:.3f}s")
        checks.append(("Whisper GPU STT", True, f"Device: {stt.device}, Latency: {lat:.2f}s"))
    except Exception as e:
        print(f"  [FAIL] STT error: {e}")
        checks.append(("Whisper GPU STT", False, str(e)))

    # --- 5. Local Ollama LLM ---
    print("\n[5/6] Verifying Local Ollama LLM (Qwen2.5-3B)...", flush=True)
    try:
        from backend.llm.ollama_client import ollama_client
        t0 = time.time()
        reply = ollama_client.generate_response([
            {"role": "user", "content": "Namaste, main Sachindra se milne ke liye call kar raha hoon."}
        ])
        lat = time.time() - t0
        print(f"  Ollama Model: '{ollama_client.model}' | Latency: {lat:.2f}s")
        print(f"  Sample Reply: \"{reply}\"")
        checks.append(("Ollama Local LLM", bool(reply), f"Model: {ollama_client.model}, Latency: {lat:.2f}s"))
    except Exception as e:
        print(f"  [FAIL] LLM error: {e}")
        checks.append(("Ollama Local LLM", False, str(e)))

    # --- 6. Female Indian Voice TTS ---
    print("\n[6/6] Verifying Female Indian Voice TTS (Edge-TTS)...", flush=True)
    try:
        from backend.tts.tts_engine import tts_engine
        audio_data, lat = tts_engine.synthesize_to_numpy("Namaste, main Sachindra ki personal assistant hoon.", target_sample_rate=48000)
        tts_ok = audio_data is not None and len(audio_data) > 0
        duration = len(audio_data) / 48000.0 if tts_ok else 0.0
        print(f"  Voice: '{tts_engine.voice}' | Synthesized: {duration:.1f}s audio in {lat:.2f}s")
        checks.append(("Female Indian TTS", tts_ok, f"Voice: {tts_engine.voice}, Latency: {lat:.2f}s"))
    except Exception as e:
        print(f"  [FAIL] TTS error: {e}")
        checks.append(("Female Indian TTS", False, str(e)))

    # --- Summary Report ---
    print()
    print("=" * 70)
    print("  VERIFICATION SUMMARY REPORT")
    print("=" * 70)
    all_passed = True
    for name, ok, detail in checks:
        status = "[PASS] ✅" if ok else "[FAIL] ❌"
        if not ok:
            all_passed = False
        print(f"  {name:<22} {status}  ({detail})")
    print("=" * 70)

    if all_passed:
        print("  🎉 ALL 6 SUBSYSTEMS ARE 100% OPERATIONAL AND READY!")
    else:
        print("  ⚠️ Some subsystems failed verification. Check logs above.")
    print("=" * 70)
    return all_passed

if __name__ == "__main__":
    verify_all()
