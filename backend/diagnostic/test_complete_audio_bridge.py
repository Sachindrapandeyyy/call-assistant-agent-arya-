"""
AI Call Assistant - Complete Bidirectional Audio Bridge Test

Validates both directions simultaneously:
1. Downlink: Captures caller's speech via WASAPI Speaker Loopback.
2. Uplink: Plays AI test voice / chime into CABLE Input (VB-Audio Virtual Cable)
   so the caller hears it directly on their phone.

Usage:
  1. Complete 10-second VB-Cable setup (Run VBCABLE_Setup_x64.exe as Administrator).
  2. In Windows Sound settings or Phone Link, set Microphone to 'CABLE Output'.
  3. Start a Phone Link call with your phone.
  4. Run:
     python backend/diagnostic/test_complete_audio_bridge.py
"""

import sys
import time
from pathlib import Path
import numpy as np
import soundcard as sc
from scipy.io import wavfile

SAMPLE_RATE = 48000
DURATION = 6.0
OUT_DIR = Path(__file__).resolve().parent.parent.parent / "recordings" / "diagnostic"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_test_audio(duration_sec=4.0):
    """Generate a clean test melody to send to the caller."""
    t = np.linspace(0, duration_sec, int(SAMPLE_RATE * duration_sec), endpoint=False)
    audio = np.zeros_like(t)

    # 4-note ascending chime (C5, E5, G5, C6)
    notes = [
        (0.0, 0.8, 523.25),  # C5
        (0.8, 1.6, 659.25),  # E5
        (1.6, 2.4, 783.99),  # G5
        (2.4, 3.8, 1046.50), # C6
    ]
    for start, end, freq in notes:
        mask = (t >= start) & (t < end)
        t_segment = t[mask] - start
        envelope = np.exp(-2.5 * t_segment)
        audio[mask] += 0.35 * np.sin(2 * np.pi * freq * t_segment) * envelope

    return audio.astype(np.float32).reshape(-1, 1)


def find_cable_speaker():
    """Find the CABLE Input playback device."""
    speakers = sc.all_speakers()
    for s in speakers:
        if "cable input" in s.name.lower() or "vb-audio" in s.name.lower():
            return s
    return None


def main():
    print()
    print("=" * 70)
    print("  PHASE 0: COMPLETE BIDIRECTIONAL AUDIO BRIDGE TEST")
    print("=" * 70)

    cable_spk = find_cable_speaker()
    if cable_spk is None:
        print("\n  [ATTENTION] 'CABLE Input' device not found.")
        print("  Please install VB-Cable first:")
        print(r"  1. Go to: C:\Users\Sachi\.gemini\antigravity\scratch\ai-call-assistant\vbcable")
        print("  2. Right-click 'VBCABLE_Setup_x64.exe' -> Click 'Run as administrator'")
        print("  3. Click 'Install Driver'")
        print("  4. Re-run this script.")
        print()
        sys.exit(1)

    print(f"  [OK] Found Virtual Uplink: {cable_spk.name}")

    loopback_mic = sc.get_microphone("Speakers", include_loopback=True)
    print(f"  [OK] Found Downlink Capture: {loopback_mic.name}")
    print()
    print("  --> Step A: Ensure Phone Link call is ACTIVE.")
    print("  --> Step B: In Windows Settings > System > Sound > Input (or Phone Link settings):")
    print("              Set Microphone to 'CABLE Output (VB-Audio Virtual Cable)'.")
    print()

    input("  Press ENTER when ready to start bidirectional test...")
    print("\n  [TEST RUNNING] Injecting test audio to caller & recording caller voice...", flush=True)

    test_audio = generate_test_audio(duration_sec=4.0)

    # Play to cable input while recording from speaker loopback
    try:
        # Start recording caller loopback in background
        with loopback_mic.recorder(samplerate=SAMPLE_RATE, channels=1, blocksize=1024) as mic:
            # Play chime into CABLE Input (which feeds Phone Link -> Caller)
            cable_spk.play(test_audio, samplerate=SAMPLE_RATE)
            
            # Record caller response
            frames = []
            start = time.time()
            while time.time() - start < DURATION:
                chunk = mic.record(numframes=1024)
                frames.append(chunk)

        if frames:
            data = np.concatenate(frames, axis=0)
            peak_val = float(np.max(np.abs(data)))
            rms_val = float(np.sqrt(np.mean(data ** 2)))

            file_path = OUT_DIR / "bidirectional_caller_captured.wav"
            data_int16 = (data * 32767).clip(-32768, 32767).astype(np.int16)
            wavfile.write(str(file_path), SAMPLE_RATE, data_int16)

            print()
            print("=" * 70)
            print("  BIDIRECTIONAL TEST COMPLETED")
            print("=" * 70)
            print(f"  Captured Caller Audio: {file_path}")
            print(f"  Caller Signal Peak:    {peak_val:.5f} (RMS: {rms_val:.5f})")
            print()
            print("  Please check:")
            print("  1. Did the caller hear the 4-note chime on their phone? (YES / NO)")
            print("  2. Did you verify the captured caller voice in the WAV file? (YES / NO)")
            print("=" * 70)
        else:
            print("  [FAIL] No loopback frames captured.")

    except Exception as e:
        print(f"  [FAIL] Error during bridge test: {e}")


if __name__ == "__main__":
    main()
