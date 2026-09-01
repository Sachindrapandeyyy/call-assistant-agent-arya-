"""
VB-Cable Loopback Transmission Test.
Verifies that audio played to 'CABLE Input' is successfully received on 'CABLE Output'.
"""

import time
import threading
import numpy as np
import soundcard as sc
from backend.audio.device_manager import DeviceManager

def test_cable_transmission():
    print("==================================================================")
    print("  VB-CABLE TRANSMISSION & LEVEL VERIFICATION")
    print("==================================================================")

    speaker = DeviceManager.get_uplink_speaker("cable input")
    if not speaker:
        print("❌ Error: 'CABLE Input' speaker not found!")
        return False

    mic = None
    for m in sc.all_microphones():
        if "cable output" in m.name.lower() or "vb-audio" in m.name.lower():
            mic = m
            break

    if not mic:
        print("❌ Error: 'CABLE Output' microphone not found!")
        return False

    print(f"  [+] Output Endpoint (AI Writes): {speaker.name}")
    print(f"  [+] Input Endpoint (Phone Reads): {mic.name}")

    # Generate 2-second 440Hz test sine wave (A4 tone)
    samplerate = 48000
    duration = 2.0
    t = np.linspace(0, duration, int(samplerate * duration), endpoint=False)
    sine_wave = (np.sin(2 * np.pi * 440 * t) * 0.8).astype(np.float32)
    stereo_audio = np.column_stack([sine_wave, sine_wave])

    captured_chunks = []
    recording_active = threading.Event()
    recording_active.set()

    def record_thread():
        try:
            with mic.recorder(samplerate=samplerate, channels=2, blocksize=1024) as recorder:
                while recording_active.is_set():
                    data = recorder.record(numframes=1024)
                    captured_chunks.append(data)
        except Exception as e:
            print(f"  ❌ Recorder error: {e}")

    rec_t = threading.Thread(target=record_thread, daemon=True)
    rec_t.start()

    time.sleep(0.2)
    print("  [>] Playing test tone into CABLE Input...")
    speaker.play(stereo_audio, samplerate=samplerate)
    time.sleep(0.5)

    recording_active.clear()
    rec_t.join(timeout=2.0)

    if not captured_chunks:
        print("  ❌ No audio captured from CABLE Output!")
        return False

    full_audio = np.concatenate(captured_chunks, axis=0)
    rms = np.sqrt(np.mean(full_audio ** 2))
    max_peak = np.max(np.abs(full_audio))

    print(f"  [+] Captured {len(full_audio)} frames from CABLE Output.")
    print(f"  [+] Measured Signal RMS: {rms:.6f} | Max Peak: {max_peak:.6f}")

    if rms > 0.05:
        print("  🎉 [PASS] VB-Cable transmission is working perfectly! Audio flows from Input -> Output.")
        return True
    else:
        print("  ⚠️ [FAIL] Audio level too low or muted. Check Windows Sound Control Panel for VB-Cable volume.")
        return False

if __name__ == "__main__":
    test_cable_transmission()
