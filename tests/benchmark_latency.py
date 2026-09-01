"""
Precise Latency Profiling Benchmark for AI Call Assistant.
Measures real-time execution duration for each stage of the conversational pipeline:
1. VAD Turn Segmentation
2. Whisper STT (CUDA GPU FP16/int8)
3. Entity Extraction (Rule + Qwen LLM)
4. Response Generation (Qwen2.5-3B)
5. TTS Synthesis (Local SAPI / Edge-TTS / Cached)
6. Dual Audio Injection Playback Kick-off
"""

import sys
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

from backend.config import settings
from backend.stt.whisper_engine import get_stt_engine
from backend.llm.ollama_client import ollama_client
from backend.llm.slot_extractor import slot_extractor
from backend.agent.state_machine import ConversationStateMachine
from backend.tts.tts_engine import tts_engine
from backend.audio.cable_player import cable_player

def benchmark_full_pipeline():
    print("=" * 75)
    print("  AURA AI — DETAILED CONVERSATIONAL LATENCY PROFILING")
    print("=" * 75)

    timings = {}

    # Sample Hinglish spoken utterance
    sample_text = "Mera naam Harsh hai, kal 10 baje interview schedule karna hai."

    # --- Step 1: VAD Silence Threshold ---
    t_vad_silence = settings.SILENCE_TIMEOUT
    timings["1. VAD End-of-Turn Silence"] = t_vad_silence
    print(f"  [1/6] VAD Silence Timeout:       {t_vad_silence*1000:.1f} ms")

    # --- Step 2: Whisper STT ---
    stt = get_stt_engine()
    dummy_audio = (0.05 * np.random.randn(32000)).astype(np.float32)
    t0 = time.time()
    transcript, lang, stt_lat = stt.transcribe(dummy_audio, language="en")
    t_stt = time.time() - t0
    timings["2. Whisper STT on CUDA"] = t_stt
    print(f"  [2/6] Whisper GPU Transcription: {t_stt*1000:.1f} ms (Device: {stt.device})")

    # --- Step 3: Entity / Slot Extraction ---
    t0 = time.time()
    slots = slot_extractor.extract_from_utterance(sample_text, [])
    t_slots = time.time() - t0
    timings["3. Entity Slot Extraction"] = t_slots
    print(f"  [3/6] Entity Slot Extraction:    {t_slots*1000:.1f} ms (Extracted: Name='{slots.get('caller_name')}', Time='{slots.get('important_dates_times')}')")

    # --- Step 4: State Machine & Qwen LLM ---
    sm = ConversationStateMachine()
    sm.start_call("bench_session", "+919876543210")
    sm.apply_extracted_entities(slots)
    decision = sm.evaluate_next_step(sample_text)

    t0 = time.time()
    dialogue = [
        {"role": "assistant", "content": sm.get_initial_greeting()},
        {"role": "user", "content": sample_text}
    ]
    reply = ollama_client.generate_response(dialogue)
    t_llm = time.time() - t0
    timings["4. Qwen2.5-3B Generation"] = t_llm
    print(f"  [4/6] Qwen LLM Generation:       {t_llm*1000:.1f} ms (Reply: \"{reply[:50]}...\")")

    # --- Step 5: TTS Synthesis (Cached vs Uncached) ---
    # Uncached response
    t0 = time.time()
    audio_data, tts_lat = tts_engine.synthesize_to_numpy(reply[:60])
    t_tts_uncached = time.time() - t0
    timings["5a. TTS Synthesis (New text)"] = t_tts_uncached
    print(f"  [5a/6] TTS Synthesis (Uncached): {t_tts_uncached*1000:.1f} ms ({len(audio_data)/48000:.1f}s audio)")

    # Cached response (e.g. Initial Greeting)
    t0 = time.time()
    cached_audio, _ = tts_engine.synthesize_to_numpy(sm.get_initial_greeting())
    t_tts_cached = time.time() - t0
    timings["5b. TTS Synthesis (Cached)"] = t_tts_cached
    print(f"  [5b/6] TTS Synthesis (Cached):   {t_tts_cached*1000:.2f} ms")

    # --- Step 6: Audio Playback Initiation ---
    t0 = time.time()
    # Play tiny 50ms chunk to measure injection startup latency
    cable_player.play_audio_blocking(audio_data[:2400], source_sample_rate=48000)
    t_play_start = time.time() - t0
    timings["6. Audio Injection Start"] = t_play_start
    print(f"  [6/6] Audio Injection Kick-off:  {t_play_start*1000:.1f} ms")

    # --- End-to-End Totals ---
    total_cached = t_vad_silence + t_stt + t_slots + t_llm + t_tts_cached + t_play_start
    total_uncached = t_vad_silence + t_stt + t_slots + t_llm + t_tts_uncached + t_play_start

    print("\n" + "=" * 75)
    print("  LATENCY SUMMARY BREAKDOWN")
    print("=" * 75)
    for k, v in timings.items():
        print(f"  {k:<35}: {v*1000:6.1f} ms")
    print("-" * 75)
    print(f"  ⚡ TOTAL TURN LATENCY (Cached turn):    {total_cached*1000:6.1f} ms ({total_cached:.2f}s)")
    print(f"  ⚡ TOTAL TURN LATENCY (Full generation): {total_uncached*1000:6.1f} ms ({total_uncached:.2f}s)")
    print("=" * 75)

if __name__ == "__main__":
    benchmark_full_pipeline()
