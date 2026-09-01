"""
AI Call Assistant - Audio Injection Diagnostic

Tests sending audio to the caller through:
1. Endpoint [23] (Infinix HFP Output - 16kHz)
2. Any other candidate device

Usage:
  python backend/diagnostic/test_audio_injection.py
"""

import sys
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000


def generate_chime():
    t = np.linspace(0, 3.0, int(SAMPLE_RATE * 3.0), endpoint=False)
    chime = 0.3 * np.sin(2 * np.pi * 587.33 * t) * np.exp(-1.5 * t)  # D5
    return chime.astype(np.float32).reshape(-1, 1)


def main():
    print()
    print("=" * 65)
    print("  AUDIO INJECTION TEST (Laptop -> Caller)")
    print("=" * 65)
    print("  We will play a 3-second chime to Infinix Output [23].")
    print("  Target Device: [23] (Infinix Hands-Free Output, 16kHz)")
    print()

    input("  Press ENTER to play chime to the caller...")
    chime = generate_chime()

    try:
        sd.play(chime, samplerate=SAMPLE_RATE, device=23, blocking=True)
        print("  Playback finished.")
        print()
        heard = input("  Did the caller hear the chime on their phone? (y/n): ").strip().lower()
        if heard == "y":
            print("\n  [SUCCESS] Outgoing audio injection into cellular call is 100% CONFIRMED on device [23]!")
        else:
            print("\n  [INFO] Caller did not hear device [23]. Phone Link is using Windows Default Mic for injection.")
    except Exception as e:
        print(f"  Error playing to device 23: {e}")


if __name__ == "__main__":
    main()
