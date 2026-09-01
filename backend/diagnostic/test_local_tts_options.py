"""
Benchmarking local offline TTS engines vs cloud TTS.
"""

import time
import os
import pyttsx3
import numpy as np
from scipy.io import wavfile

def test_pyttsx3():
    print("--- 1. Testing pyttsx3 (100% Offline Local Windows SAPI) ---")
    t0 = time.time()
    engine = pyttsx3.init()
    engine.setProperty('rate', 170)
    
    voices = engine.getProperty('voices')
    for v in voices:
        print(f"  Voice: {v.name} ({v.id})")

    out_file = "test_local_pyttsx3.wav"
    sample_text = "Namaste, main Sachindra sir ki executive assistant bol rahi hoon. Sachindra sir abhi meeting mein hain."
    
    t_start = time.time()
    engine.save_to_file(sample_text, out_file)
    engine.runAndWait()
    dt = time.time() - t_start
    
    if os.path.exists(out_file):
        size = os.path.getsize(out_file)
        sr, data = wavfile.read(out_file)
        dur = len(data) / float(sr)
        print(f"  ✅ [PASS] Synthesized {dur:.2f}s of audio in {dt:.3f}s! (File size: {size} bytes)")
        return True
    return False

if __name__ == "__main__":
    test_pyttsx3()
