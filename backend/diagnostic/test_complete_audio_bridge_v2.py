"""
AI Call Assistant - Non-Blocking Bidirectional Audio Bridge Test (v2)

Fixes buffer discontinuity by running audio playback and WASAPI loopback
recording on separate parallel threads.

Test Flow:
1. Seconds 0-3: Plays a 3-second chime to the caller's phone.
2. Seconds 3-8: Prompts the caller to speak.
3. Records all 8 seconds continuously from Speakers loopback.
4. Generates a comprehensive summary with peak/RMS levels.
"""

import sys
import time
import threading
from pathlib import Path
import numpy as np
import soundcard as sc
from scipy.io import wavfile

SAMPLE_RATE = 48000
TOTAL_DURATION = 8.0
OUT_DIR = Path(__file__).resolve().parent.parent.parent / "recordings" / "diagnostic"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_chime(duration_sec=3.0):
    """Generate a clean 3-second chime sequence."""
    t = np.linspace(0, duration_sec, int(SAMPLE_RATE * duration_sec), endpoint=False)
    audio = np.zeros_like(t)
    tones = [
        (0.0, 0.6, 523.25),  # C5
        (0.6, 1.2, 659.25),  # E5
        (1.2, 1.8, 783.99),  # G5
        (1.8, 2.8, 1046.50), # C6
    ]
    for start, end, freq in tones:
        mask = (t >= start) & (t < end)
        t_seg = t[mask] - start
        env = np.exp(-2.5 * t_seg)
        audio[mask] += 0.35 * np.sin(2 * np.pi * freq * t_seg) * env

    return audio.astype(np.float32).reshape(-1, 1)


def find_cable_speaker():
    for s in sc.all_speakers():
        if "cable input" in s.name.lower() or "vb-audio" in s.name.lower():
            return s
    return None


def main():
    print()
    print("=" * 70)
    print("  PHASE 0: PARALLEL BIDIRECTIONAL AUDIO BRIDGE TEST (v2)")
    print("=" * 70)

    cable_spk = find_cable_speaker()
    if cable_spk is None:
        print("  [ERROR] CABLE Input not found. Ensure VB-Cable is installed.")
        sys.exit(1)

    loopback_mic = sc.get_microphone("Speakers", include_loopback=True)
    print(f"  [OK] Uplink Target (AI -> Caller):   {cable_spk.name}")
    print(f"  [OK] Downlink Target (Caller -> AI): {loopback_mic.name}")
    print()
    print("  --> INSTRUCTIONS:")
    print("      1. Keep Phone Link call ACTIVE.")
    print("      2. In the first 3 seconds, the caller will hear a chime on their phone.")
    print("      3. After the chime, the caller should speak naturally:")
    print("         'Namaste, main Sachindra ke liye call kar raha hoon.'")
    print()

    input("  Press ENTER when ready to start the 8-second test...")
    print("\n  [TEST IN PROGRESS - 8 SECONDS]", flush=True)

    recorded_chunks = []
    stop_event = threading.Event()

    # Thread 1: Continuous Loopback Recording (Zero Discontinuity)
    def record_worker():
        try:
            with loopback_mic.recorder(samplerate=SAMPLE_RATE, channels=1, blocksize=1024) as mic:
                while not stop_event.is_set():
                    chunk = mic.record(numframes=1024)
                    recorded_chunks.append(chunk)
        except Exception as e:
            print(f"\n  [ERROR] Record thread: {e}")

    rec_thread = threading.Thread(target=record_worker, daemon=True)
    rec_thread.start()

    # Give recording thread 200ms to initialize buffer
    time.sleep(0.2)

    # Thread 2: Play chime into CABLE Input
    print("  --> [0s - 3s] Playing chime to caller's phone...", flush=True)
    chime_data = generate_chime(duration_sec=3.0)
    cable_spk.play(chime_data, samplerate=SAMPLE_RATE)

    print("  --> [3s - 8s] CHIME FINISHED. CALLER SHOULD SPEAK NOW! ...", flush=True)
    time.sleep(4.8)

    # Stop recording
    stop_event.set()
    rec_thread.join(timeout=2.0)

    if recorded_chunks:
        full_recording = np.concatenate(recorded_chunks, axis=0)
        peak_val = float(np.max(np.abs(full_recording)))
        rms_val = float(np.sqrt(np.mean(full_recording ** 2)))

        out_file = OUT_DIR / "bidirectional_parallel_test.wav"
        rec_int16 = (full_recording * 32767).clip(-32768, 32767).astype(np.int16)
        wavfile.write(str(out_file), SAMPLE_RATE, rec_int16)

        print()
        print("=" * 70)
        print("  PHASE 0 TEST RESULTS")
        print("=" * 70)
        print(f"  Total Duration:      {len(full_recording) / SAMPLE_RATE:.1f}s")
        print(f"  Peak Audio Level:    {peak_val:.5f}")
        print(f"  RMS Audio Level:     {rms_val:.5f}")
        print(f"  Saved WAV File:      {out_file}")
        print()

        if peak_val > 0.01:
            print("  [SUCCESS] Bidirectional audio capture & playback confirmed!")
            print("  -> Listen to the WAV file: you should hear the caller's voice clearly.")
        else:
            print("  [WARN] Audio level low. Ensure the caller spoke audibly during seconds 3-8.")
        print("=" * 70)
    else:
        print("  [FAIL] No audio frames were captured.")


if __name__ == "__main__":
    main()
