"""
AI Call Assistant - Safe WASAPI Speaker Loopback Probe

Captures audio played through Windows Default Speakers (Realtek)
using standard user-mode WASAPI loopback.

Usage:
  1. Call is ACTIVE in Phone Link with caller talking.
  2. Run:
     python backend/diagnostic/safe_wasapi_probe.py
"""

import sys
import time
from pathlib import Path
import numpy as np
import soundcard as sc
from scipy.io import wavfile

DURATION = 5.0
SAMPLE_RATE = 48000
OUT_DIR = Path(__file__).resolve().parent.parent.parent / "recordings" / "diagnostic"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def test_safe_loopback():
    print()
    print("=" * 65)
    print("  SAFE WASAPI SPEAKER LOOPBACK TEST")
    print("=" * 65)
    print("  Capturing audio from: Windows Default Speakers (Realtek)")
    print("  Mode: WASAPI User-Mode Loopback")
    print("  Target: Caller's voice playing through Phone Link")
    print()

    # Get speaker loopback microphone
    loopback_mic = sc.get_microphone("Speakers", include_loopback=True)
    print(f"  Target Loopback Device: {loopback_mic.name}")
    print()

    input("  Press ENTER while caller is speaking...")
    print(f"  Recording {DURATION} seconds...", flush=True)

    try:
        data = loopback_mic.record(samplerate=SAMPLE_RATE, numframes=int(SAMPLE_RATE * DURATION))

        # Convert stereo to mono by taking mean of channels
        if len(data.shape) > 1 and data.shape[1] > 1:
            mono_data = np.mean(data, axis=1)
        else:
            mono_data = data.flatten()

        peak_val = float(np.max(np.abs(mono_data)))
        rms_val = float(np.sqrt(np.mean(mono_data ** 2)))

        file_path = OUT_DIR / "safe_wasapi_caller_audio.wav"
        data_int16 = (mono_data * 32767).clip(-32768, 32767).astype(np.int16)
        wavfile.write(str(file_path), SAMPLE_RATE, data_int16)

        print()
        print("  Recording complete!")
        print(f"  Peak Level: {peak_val:.5f}")
        print(f"  RMS Level:  {rms_val:.5f}")
        print(f"  Saved WAV:  {file_path}")
        print()

        if peak_val > 0.01:
            print("  [SUCCESS] Caller audio successfully captured via WASAPI Loopback!")
            print("  -> Listen to the WAV file to verify clarity.")
        else:
            print("  [INFO] Very low audio level. Ensure caller was speaking audibly through laptop speakers.")
        return True

    except Exception as e:
        print(f"  [FAIL] Error during WASAPI loopback: {e}")
        return False


if __name__ == "__main__":
    test_safe_loopback()
