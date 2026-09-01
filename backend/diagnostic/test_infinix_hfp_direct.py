"""
AI Call Assistant - Phase 0B Direct HFP Diagnostic

Specifically tests the newly discovered Infinix Bluetooth HFP audio endpoints:
- Input: Device with 'Infinix' & 'Input' (or Index 24) -> Reads Caller Audio (16kHz)
- Output: Device with 'Infinix' & 'Output' (or Index 23) -> Injects AI/Audio to Caller (16kHz)

Usage:
  1. Ensure Phone Link call with Infinix is ACTIVE.
  2. Run:
     python backend/diagnostic/test_infinix_hfp_direct.py
"""

import sys
import time
import argparse
from pathlib import Path
import numpy as np
import sounddevice as sd
from scipy.io import wavfile

SAMPLE_RATE = 16000  # Native HFP mSBC wideband sample rate
CHANNELS = 1         # Mono


def find_infinix_devices():
    """Find input and output device indices matching the Infinix HFP profile."""
    devices = sd.query_devices()
    in_idx = None
    out_idx = None

    for i, dev in enumerate(devices):
        name = dev["name"]
        # Check for Infinix or bthhfenum with Hands-Free HF Audio
        if ("infinix" in name.lower() or "hands-free hf audio" in name.lower()) and "bthhfenum" in name.lower():
            if dev["max_input_channels"] > 0 and in_idx is None:
                in_idx = i
            if dev["max_output_channels"] > 0 and out_idx is None:
                out_idx = i

    # Fallback to known indices 24 and 23 if not found by string pattern
    if in_idx is None and len(devices) > 24 and devices[24]["max_input_channels"] > 0:
        in_idx = 24
    if out_idx is None and len(devices) > 23 and devices[23]["max_output_channels"] > 0:
        out_idx = 23

    return in_idx, out_idx


def generate_pleasant_chime(duration_sec=3.0, sample_rate=SAMPLE_RATE):
    """Generate a pleasant multi-tone chime to play to the caller."""
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
    # Chord progression: A4 (440Hz), C#5 (554.37Hz), E5 (659.25Hz), A5 (880Hz)
    chime = np.zeros_like(t)
    tones = [
        (0.0, 0.7, 440.0),    # A4
        (0.5, 1.2, 554.37),   # C#5
        (1.0, 1.7, 659.25),   # E5
        (1.5, 2.8, 880.0),    # A5
    ]
    for start, end, freq in tones:
        mask = (t >= start) & (t < end)
        t_segment = t[mask] - start
        envelope = np.exp(-3 * t_segment) * np.sin(np.pi * (t_segment / (end - start)))
        chime[mask] += 0.25 * np.sin(2 * np.pi * freq * t_segment) * envelope

    return (chime * 0.5).astype(np.float32).reshape(-1, 1)


def run_caller_capture_test(in_idx, duration=5.0):
    """Test capturing caller speech from Infinix HFP Input endpoint."""
    print()
    print("=" * 65)
    print("  STEP 1: CAPTURE CALLER AUDIO (Downlink)")
    print("=" * 65)
    print(f"  Target Device: [{in_idx}] {sd.query_devices(in_idx)['name']}")
    print(f"  Target Format: {SAMPLE_RATE}Hz, Mono")
    print()
    print("  --> Please ask the caller to speak clearly now:")
    print("      'Hello Sachindra, this is a test call for the AI assistant...'")
    print()

    input("  Press ENTER to record 5 seconds of caller voice...")
    print("  Recording in progress...", flush=True)

    try:
        recording = sd.rec(
            frames=int(duration * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            device=in_idx,
            dtype="float32",
            blocking=True
        )
        print("  Recording complete!")
    except Exception as e:
        print(f"  [FAIL] Failed to open/read from device [{in_idx}]: {e}")
        return None

    peak_val = float(np.max(np.abs(recording)))
    rms_val = float(np.sqrt(np.mean(recording ** 2)))

    print(f"  Audio Metrics: Peak = {peak_val:.5f}, RMS = {rms_val:.5f}")

    # Save audio
    out_dir = Path(__file__).resolve().parent.parent.parent / "recordings" / "diagnostic"
    out_dir.mkdir(parents=True, exist_ok=True)
    file_path = out_dir / "infinix_caller_audio.wav"

    rec_int16 = (recording * 32767).clip(-32768, 32767).astype(np.int16)
    wavfile.write(str(file_path), SAMPLE_RATE, rec_int16)
    print(f"  Saved caller audio to: {file_path}")

    if peak_val > 0.01:
        print("  [PASS] Valid audio signal detected from caller!")
    else:
        print("  [WARN] Very low signal/silence detected. Ensure caller was speaking.")

    return recording


def run_caller_inject_test(out_idx):
    """Test injecting synthesized audio to Infinix HFP Output endpoint."""
    print()
    print("=" * 65)
    print("  STEP 2: INJECT AUDIO TO CALLER (Uplink)")
    print("=" * 65)
    print(f"  Target Device: [{out_idx}] {sd.query_devices(out_idx)['name']}")
    print(f"  Target Format: {SAMPLE_RATE}Hz, Mono")
    print()
    print("  --> We will now play a 3-second chime sequence into the call.")
    print("      Ask the caller if they can hear the chime on their phone.")
    print()

    input("  Press ENTER to play chime into the phone call...")
    print("  Playing audio to caller...", flush=True)

    chime = generate_pleasant_chime(duration_sec=3.0, sample_rate=SAMPLE_RATE)

    try:
        sd.play(chime, samplerate=SAMPLE_RATE, device=out_idx, blocking=True)
        print("  Playback finished!")
        print("  [PASS] Audio stream was successfully written to the Infinix endpoint.")
    except Exception as e:
        print(f"  [FAIL] Failed to write to device [{out_idx}]: {e}")
        return False

    return True


def run_duplex_loopback_test(in_idx, out_idx, duration=6.0):
    """Test simultaneous bidirectional streaming."""
    print()
    print("=" * 65)
    print("  STEP 3: SIMULTANEOUS BIDIRECTIONAL TEST (Duplex)")
    print("=" * 65)
    print("  Playing audio to caller while simultaneously recording caller voice...")
    print()

    input("  Press ENTER to start duplex test...")
    chime = generate_pleasant_chime(duration_sec=duration, sample_rate=SAMPLE_RATE)

    try:
        rec = sd.playrec(
            chime,
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            device=(in_idx, out_idx),
            dtype="float32",
            blocking=True
        )
        print("  Duplex test completed without audio buffer collisions!")

        out_dir = Path(__file__).resolve().parent.parent.parent / "recordings" / "diagnostic"
        file_path = out_dir / "infinix_duplex_capture.wav"
        rec_int16 = (rec * 32767).clip(-32768, 32767).astype(np.int16)
        wavfile.write(str(file_path), SAMPLE_RATE, rec_int16)
        print(f"  Saved duplex captured audio to: {file_path}")
        print("  [PASS] Full bidirectional streaming confirmed on hardware level.")
        return True
    except Exception as e:
        print(f"  [FAIL] Duplex error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Infinix HFP Direct Endpoint Diagnostic")
    parser.add_argument("--input", type=int, help="Input device index (e.g. 24)")
    parser.add_argument("--output", type=int, help="Output device index (e.g. 23)")
    args = parser.parse_args()

    in_idx, out_idx = args.input, args.output
    if in_idx is None or out_idx is None:
        auto_in, auto_out = find_infinix_devices()
        in_idx = in_idx if in_idx is not None else auto_in
        out_idx = out_idx if out_idx is not None else auto_out

    print()
    print("=" * 65)
    print("  INFINIX ZERO 5G 2023 - BLUETOOTH HFP DIRECT ENDPOINT TEST")
    print("=" * 65)
    print(f"  Resolved Input Device Index:  [{in_idx}] {sd.query_devices(in_idx)['name'] if in_idx is not None else 'NOT FOUND'}")
    print(f"  Resolved Output Device Index: [{out_idx}] {sd.query_devices(out_idx)['name'] if out_idx is not None else 'NOT FOUND'}")

    if in_idx is None or out_idx is None:
        print("\n  [ERROR] Could not resolve both Infinix HFP endpoints.")
        print("  Please make sure Phone Link call is active and run:")
        print("  python backend/diagnostic/list_audio_devices.py")
        sys.exit(1)

    # Step 1: Capture
    rec = run_caller_capture_test(in_idx, duration=5.0)

    # Step 2: Inject
    run_caller_inject_test(out_idx)

    # Step 3: Duplex
    if rec is not None:
        run_duplex_loopback_test(in_idx, out_idx)

    print()
    print("=" * 65)
    print("  PHASE 0B HARDWARE DIAGNOSTIC COMPLETE")
    print("=" * 65)
    print("  Please check:")
    print("  1. Listen to `recordings/diagnostic/infinix_caller_audio.wav`")
    print("  2. Confirm caller heard the chime during Step 2")
    print("=" * 65)


if __name__ == "__main__":
    main()
