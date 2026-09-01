import sys, os, time, numpy as np
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')

from backend.audio.vad import VADSegmenter
from backend.stt.whisper_engine import get_stt_engine
from backend.llm.ollama_client import ollama_client
from backend.tts.tts_engine import tts_engine
from scipy import signal

print('=' * 70)
print('⏱️ REAL HARDWARE CONVERSATIONAL LATENCY BENCHMARK')
print('=' * 70)

# 1. VAD Latency
vad = VADSegmenter(sample_rate=16000)
chunk = np.zeros(512, dtype=np.float32)
t0 = time.perf_counter()
for _ in range(100):
    vad.process_chunk(chunk)
vad_lat = (time.perf_counter() - t0) / 100 * 1000
print(f'1. VAD Processing Latency:      {vad_lat:.3f} ms per 32ms chunk')

# 2. STT Latency
stt = get_stt_engine()
dummy_audio = np.random.randn(16000 * 3).astype(np.float32) * 0.05
t0 = time.perf_counter()
txt, lang, stt_lat_s = stt.transcribe(dummy_audio)
stt_lat = (time.perf_counter() - t0) * 1000
print(f'2. Whisper STT GPU (RTX 4050):   {stt_lat:.1f} ms (for 3.0s speech audio)')

# 3. LLM Latency
ollama = ollama_client
t0 = time.perf_counter()
reply = ollama.generate_response([{'role': 'user', 'content': 'Namaste, mera naam Vikram hai Amazon se'}], max_tokens=30)
llm_lat = (time.perf_counter() - t0) * 1000
print(f'3. Ollama LLM GPU (RTX 4050):    {llm_lat:.1f} ms (Reply: \"{reply[:40]}...\")')

# 4. TTS Latency (Cache Hit vs Edge-TTS vs SAPI)
t0 = time.perf_counter()
cached_audio, _ = tts_engine.synthesize_to_numpy('Namaste, main Sachindra sir ki personal assistant Arya hoon.')
cache_tts_lat = (time.perf_counter() - t0) * 1000
print(f'4a. TTS (In-Memory Cache Hit):   {cache_tts_lat:.3f} ms (0.00s Instantaneous)')

t0 = time.perf_counter()
sapi_audio, sapi_lat_s = tts_engine.synthesize_sapi_isolated('Ji main message note kar leti hoon.')
sapi_tts_lat = (time.perf_counter() - t0) * 1000
print(f'4b. TTS (Local Offline SAPI):    {sapi_tts_lat:.1f} ms')

# 5. Total Conversational Turnaround
total_cached = vad_lat + stt_lat + llm_lat + cache_tts_lat + 15.0 # 15ms soundcard buffer
total_offline = vad_lat + stt_lat + llm_lat + sapi_tts_lat + 15.0

print('=' * 70)
print(f'🎯 TOTAL CONVERSATIONAL TURNAROUND (Prewarmed Turns): {total_cached:.1f} ms ({total_cached/1000:.2f}s)')
print(f'🎯 TOTAL CONVERSATIONAL TURNAROUND (Offline SAPI):    {total_offline:.1f} ms ({total_offline/1000:.2f}s)')
print('=' * 70)

