"""
AI Call Assistant - Multi-Endpoint Call Audio Probe

Tests multiple candidate capture points simultaneously during an active call:
1. Infinix HFP Endpoint [24] (WDM-KS Input)
2. Infinix HFP Endpoint [23] (WDM-KS Output)
3. Stereo Mix [13] (Realtek Hardware Loopback)
4. WASAPI Loopback (captures audio played to laptop speakers)
5. Default Microphone [9]

Saves each capture as a separate WAV file so you can listen and verify
which one contains the clean caller audio.
"""

import sys
import time
from pathlib import Path
import numpy as np
import sounddevice as sd
from scipy.io import wavfile

DURATION = 4.0
OUT_DIR = Path(__file__).resolve().parent.parent.parent / "recordings" / "diagnostic"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def test_device_capture(dev_idx, name, sample_rate=16000, channels=1):
    """Record from a sounddevice index and return metrics."""
    try:
        data = sd.rec(
            frames=int(DURATION * sample_rate),
            samplerate=sample_rate,
            channels=channels,
            device=dev_idx,
            dtype="float32",
            blocking=True,
        )
        peak_val = float(np.max(np.abs(data)))
        rms_val = float(np.sqrt(np.mean(data ** 2)))

        # Save to file
        safe_name = name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        file_path = OUT_DIR / f"probe_{dev_idx}_{safe_name}.wav"
        data_int16 = (data * 32767).clip(-32768, 32767).astype(np.int16)
        wavfile.write(str(file_path), sample_rate, data_int16)

        return peak_val, rms_val, str(file_path), None
    except Exception as e:
        return 0.0, 0.0, None, str(e)


def test_wasapi_loopback():
    """Capture loopback from default speakers via soundcard library."""
    try:
        import soundcard as sc
        default_speaker = sc.default_speaker()
        with default_speaker.recorder(samplerate=48000, channels=1, blocksize=1024) as mic:
            frames = []
            start = time.time()
            while time.time() - start < DURATION:
                chunk = mic.record(numframes=1024)
                frames.append(chunk)
            
            if frames:
                data = np.concatenate(frames, axis=0)
                peak_val = float(np.max(np.abs(data)))
                rms_val = float(np.sqrt(np.mean(data ** 2)))
                file_path = OUT_DIR / "probe_wasapi_speaker_loopback.wav"
                data_int16 = (data * 32767).clip(-32768, 32767).astype(np.int16)
                wavfile.write(str(file_path), 48000, data_int16)
                return peak_val, rms_val, str(file_path), None
            else:
                return 0.0, 0.0, None, "No frames captured"
    except Exception as e:
        return 0.0, 0.0, None, str(e)


def main():
    print()
    print("=" * 70)
    print("  MULTI-ENDPOINT CALL AUDIO PROBE")
    print("=" * 70)
    print("  This script will test 4 capture methods in sequence while")
    print("  the caller is talking:")
    print()
    print("  1. Infinix HFP [24] (WDM-KS Input)")
    print("  2. Stereo Mix [13] (Realtek Loopback)")
    print("  3. WASAPI Speaker Loopback (Captures what Phone Link plays)")
    print("  4. Laptop Microphone [9] (Acoustic)")
    print()
    print("  --> Ensure Phone Link call is ACTIVE and caller is speaking.")
    print()

    input("  Press ENTER to begin probing (keep caller talking)...")

    results = []

    # Probe 1: Device 24 (Infinix HFP Input)
    print("\n[1/4] Probing Infinix HFP Input [24] (16kHz)...", flush=True)
    p, r, f, err = test_device_capture(24, "Infinix_HFP_Input_24", sample_rate=16000, channels=1)
    results.append(("Infinix HFP [24]", p, r, f, err))

    # Probe 2: Device 13 (Stereo Mix)
    print("[2/4] Probing Stereo Mix [13] (48kHz)...", flush=True)
    p, r, f, err = test_device_capture(13, "Realtek_Stereo_Mix_13", sample_rate=48000, channels=2)
    results.append(("Stereo Mix [13]", p, r, f, err))

    # Probe 3: WASAPI Speaker Loopback
    print("[3/4] Probing WASAPI Speaker Loopback (48kHz)...", flush=True)
    p, r, f, err = test_wasapi_loopback()
    results.append(("WASAPI Speaker Loopback", p, r, f, err))

    # Probe 4: Microphone Array [9]
    print("[4/4] Probing Laptop Microphone Array [9] (48kHz)...", flush=True)
    p, r, f, err = test_device_capture(9, "Realtek_Mic_Array_9", sample_rate=48000, channels=2)
    results.append(("Laptop Mic Array [9]", p, r, f, err))

    # Print Report
    print()
    print("=" * 70)
    print("  PROBE RESULTS SUMMARY")
    print("=" * 70)
    for name, p_val, r_val, f_path, err_msg in results:
        if err_msg:
            print(f"  {name:<25} ERROR: {err_msg}")
        else:
            status = "** SIGNAL DETECTED **" if p_val > 0.01 else "Silence / No Audio"
            print(f"  {name:<25} Peak: {p_val:.5f}  RMS: {r_val:.5f}  [{status}]")
            if f_path:
                print(f"    -> Saved: {f_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
