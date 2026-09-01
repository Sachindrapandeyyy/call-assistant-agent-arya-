"""
Unified Text-to-Speech (TTS) Engine for AI Call Assistant.
Synthesizes speech with a natural Female Indian voice (hi-IN-SwaraNeural)
with instant in-memory audio caching and 100% crash-proof offline SAPI fallback.
"""

import io
import os
import time
import asyncio
import tempfile
import logging
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Dict
import numpy as np
from scipy.io import wavfile
from scipy import signal

from backend.config import settings

logger = logging.getLogger("TTSEngine")

class TTSEngine:
    def __init__(self, voice: str = settings.EDGE_VOICE):
        self.voice = voice
        self._cache: Dict[str, np.ndarray] = {}
        logger.info(f"Initialized TTSEngine with Indian female voice: '{self.voice}'")

    async def _synthesize_edge_tts_async(self, text: str) -> bytes:
        import edge_tts
        communicate = edge_tts.Communicate(text, self.voice, rate="+18%", pitch="+0Hz")
        mp3_buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_buffer.write(chunk["data"])
        mp3_buffer.seek(0)
        return mp3_buffer.read()

    def synthesize_sapi_isolated(self, text: str, target_sample_rate: int = 48000) -> Tuple[np.ndarray, float]:
        """Crash-proof local SAPI synthesis running in an isolated worker process with fast natural speed."""
        t0 = time.time()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_wav = f.name

        try:
            clean_text = text.replace("'", " ").replace('"', ' ')
            ps_script = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = 2
$synth.SetOutputToWaveFile('{tmp_wav}')
$synth.Speak('{clean_text}')
$synth.Dispose()
"""
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, check=True)
            sr, data = wavfile.read(tmp_wav)
            if data.dtype == np.int16:
                arr_float = (data / 32768.0).astype(np.float32)
            else:
                arr_float = data.astype(np.float32)

            if len(arr_float.shape) > 1 and arr_float.shape[1] > 1:
                arr_mono = np.mean(arr_float, axis=1)
            else:
                arr_mono = arr_float.flatten()

            if sr != target_sample_rate:
                num_samples = int(len(arr_mono) * target_sample_rate / sr)
                full_audio = signal.resample(arr_mono, num_samples).astype(np.float32)
            else:
                full_audio = arr_mono

            lat = time.time() - t0
            logger.info(f"[SAPI TTS] Synthesized in {lat:.3f}s")
            return full_audio, lat
        except Exception as e:
            logger.error(f"SAPI synthesis error: {e}")
            return np.zeros(1, dtype=np.float32), 0.0
        finally:
            if os.path.exists(tmp_wav):
                try:
                    os.remove(tmp_wav)
                except Exception:
                    pass

    def synthesize_to_numpy(self, text: str, target_sample_rate: int = 48000) -> Tuple[np.ndarray, float]:
        """
        Synthesizes text and returns (audio_float32_array, latency_sec).
        Checks in-memory cache first for instant 0.00s response.
        """
        clean_key = text.strip()
        if clean_key in self._cache:
            logger.info(f"[TTS] Instant cache hit for '{clean_key[:40]}...' (0.00s)")
            return self._cache[clean_key].copy(), 0.001

        # Primary: High-fidelity natural female Indian voice
        try:
            import av
            t0 = time.time()
            # Thread-safe async execution: create a dedicated event loop for edge-tts
            try:
                loop = asyncio.get_running_loop()
                # If we're in an already-running loop, use a new thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    mp3_bytes = pool.submit(lambda: asyncio.run(self._synthesize_edge_tts_async(clean_key))).result(timeout=15)
            except RuntimeError:
                # No running loop — safe to use asyncio.run directly
                mp3_bytes = asyncio.run(self._synthesize_edge_tts_async(clean_key))
            container = av.open(io.BytesIO(mp3_bytes))
            audio_stream = next(s for s in container.streams if s.type == 'audio')
            
            samples_list = []
            source_sr = audio_stream.rate or 24000

            for frame in container.decode(audio_stream):
                arr = frame.to_ndarray()
                if arr.dtype == np.int16:
                    arr_float = (arr / 32768.0).astype(np.float32)
                else:
                    arr_float = arr.astype(np.float32)
                
                if len(arr_float.shape) > 1 and arr_float.shape[0] > 1:
                    arr_mono = np.mean(arr_float, axis=0)
                else:
                    arr_mono = arr_float.flatten()
                samples_list.append(arr_mono)

            if not samples_list:
                return np.zeros(1, dtype=np.float32), 0.0

            full_audio = np.concatenate(samples_list, axis=0)
            if source_sr != target_sample_rate and source_sr == 24000 and target_sample_rate == 48000:
                full_audio = signal.resample_poly(full_audio, 2, 1).astype(np.float32)
            elif source_sr != target_sample_rate:
                num_samples = int(len(full_audio) * target_sample_rate / source_sr)
                full_audio = signal.resample(full_audio, num_samples).astype(np.float32)

            latency = time.time() - t0
            self._cache[clean_key] = full_audio
            logger.info(f"[TTS] Synthesized '{clean_key[:40]}...' in {latency:.2f}s (Audio: {len(full_audio)/target_sample_rate:.1f}s)")
            return full_audio, latency

        except Exception as e:
            logger.warning(f"Primary TTS network error ({e}), switching to crash-proof local SAPI...")
            audio, lat = self.synthesize_sapi_isolated(clean_key, target_sample_rate)
            self._cache[clean_key] = audio
            return audio, lat

    def prewarm_cache(self, texts: list):
        """Pre-synthesizes phrases into in-memory cache."""
        for t in texts:
            try:
                self.synthesize_to_numpy(t)
            except Exception as e:
                logger.warning(f"Error prewarming TTS cache for '{t}': {e}")

# Global singleton
tts_engine = TTSEngine()
