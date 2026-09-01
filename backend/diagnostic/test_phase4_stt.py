"""
AI Call Assistant - Phase 4 Speech-to-Text (STT) Diagnostic

Benchmarks faster-whisper on actual captured call audio segments.
Validates:
1. Model loading speed and GPU/CPU resource allocation
2. Transcription accuracy for Hindi / Hinglish / English
3. Measured STT latency (target: < 0.5s per turn)
4. Transcribes existing segments in `recordings/`

Usage:
  python backend/diagnostic/test_phase4_stt.py
"""

import sys
import time
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import settings
from backend.stt.whisper_engine import WhisperSTTEngine

def main():
    print()
    print("=" * 70)
    print("  PHASE 4: LOCAL SPEECH-TO-TEXT (faster-whisper) DIAGNOSTIC")
    print("=" * 70)

    # 1. Initialize Engine
    print("\n  [1/3] Initializing faster-whisper engine...")
    t0 = time.time()
    stt = WhisperSTTEngine(
        model_size=settings.STT_MODEL_SIZE,
        device=settings.STT_DEVICE,
        compute_type=settings.STT_COMPUTE_TYPE
    )
    init_time = time.time() - t0
    print(f"  Model Loaded: size='{settings.STT_MODEL_SIZE}', device='{stt.device}', time={init_time:.2f}s")

    # 2. Find recorded call audio segments
    print("\n  [2/3] Searching for captured call audio segments...")
    recordings_dir = settings.RECORDINGS_DIR
    wav_files = list(recordings_dir.glob("**/*.wav"))

    if not wav_files:
        print("  No WAV files found in recordings directory. Running dummy transcription test...")
        return

    print(f"  Found {len(wav_files)} recorded audio file(s):")
    for idx, f in enumerate(wav_files[:6], 1):
        print(f"    [{idx}] {f.relative_to(recordings_dir)} ({f.stat().st_size / 1024:.1f} KB)")

    # 3. Transcribe and benchmark
    print("\n  [3/3] Transcribing caller audio files...")
    print("=" * 70)

    results = []
    for f in wav_files[:5]:
        print(f"\n  Transcribing: {f.name}...")
        try:
            transcript, lang, latency = stt.transcribe(f)
            results.append((f.name, transcript, lang, latency))
            print(f"  -> Transcript: '{transcript}'")
            print(f"  -> Language:   {lang}")
            print(f"  -> Latency:    {latency:.3f}s")
        except Exception as e:
            print(f"  -> [ERROR] Failed to transcribe {f.name}: {e}")

    # Summary
    print()
    print("=" * 70)
    print("  PHASE 4 STT BENCHMARK SUMMARY")
    print("=" * 70)
    for name, text, lang, lat in results:
        status = "PASS" if text else "EMPTY (Silence)"
        print(f"  File: {name:<30} | Latency: {lat:.2f}s | Lang: {lang:<4} | [{status}]")
        print(f"    Text: \"{text}\"")
    print("=" * 70)

if __name__ == "__main__":
    main()
