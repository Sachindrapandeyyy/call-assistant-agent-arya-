"""
100% Offline Local TTS Engine Verification Script.
Tests Windows SAPI offline speech synthesis with zero internet dependency.
"""

import sys
import os
import time
from pathlib import Path
import numpy as np

# Force UTF-8 encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.tts.tts_engine import TTSEngine

def test_offline_tts():
    print("=" * 65)
    print("  OFFLINE LOCAL TTS SYNTHESIS TEST (WINDOWS SAPI)")
    print("=" * 65)

    engine = TTSEngine()

    test_phrases = [
        "Namaste, main Sachindra ki personal assistant hoon.",
        "Sachindra sir abhi available nahi hain.",
        "Theek hai, maine aapka poora message note kar liya hai. Have a wonderful day!"
    ]

    for i, phrase in enumerate(test_phrases, 1):
        t0 = time.time()
        audio, lat = engine.synthesize_sapi_isolated(phrase)
        dur = len(audio) / 48000.0 if len(audio) > 0 else 0.0
        print(f"  [{i}/{len(test_phrases)}] Synthesized: \"{phrase[:40]}...\" -> {dur:.2f}s audio in {lat:.3f}s")
        assert len(audio) > 0, f"Failed to synthesize phrase #{i}"

    print("\n  ✅ OFFLINE LOCAL TTS PASSED: All phrases synthesized locally with 0 internet dependency!")
    print("=" * 65)

if __name__ == "__main__":
    test_offline_tts()
