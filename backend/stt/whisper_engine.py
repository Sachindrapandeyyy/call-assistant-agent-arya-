"""
faster-whisper Speech-to-Text Engine for AI Call Assistant.
GPU-accelerated on RTX 4050 with DSP audio purification,
filler-word removal, and clean text normalization.
"""

import os
import re
import sys
import time
import logging
from pathlib import Path
from typing import Tuple, List, Optional, Union
import numpy as np

from backend.config import settings
from backend.audio.audio_filter import audio_filter

logger = logging.getLogger("WhisperSTT")

def _setup_cuda_dlls():
    """Auto-discover NVIDIA pip packages and add their bin/lib dirs to Windows DLL search path."""
    if sys.platform == "win32":
        try:
            import site
            for sp in site.getsitepackages():
                nvidia_path = Path(sp) / "nvidia"
                if nvidia_path.exists():
                    for sub in nvidia_path.iterdir():
                        for d in ["bin", "lib"]:
                            target = sub / d
                            if target.exists():
                                os.add_dll_directory(str(target))
                                os.environ["PATH"] = str(target) + os.pathsep + os.environ.get("PATH", "")
        except Exception as e:
            logger.debug(f"CUDA DLL setup: {e}")

_setup_cuda_dlls()

# Words and tokens that represent pure line noise or vocal filler
PURE_FILLER_WORDS = {
    "hm", "hmm", "um", "umm", "uh", "uhh", "ah", "ahh", "ha", "haan",
    "oh", "oho", "shh", "ss", "sh", "thanks for watching", "subscribe",
    "amara.org", "the end", "subtitles by"
}

def clean_transcript(text: str) -> str:
    """Removes filler sounds, background noise artifacts, and normalizes spoken text."""
    if not text:
        return ""

    # Remove non-alphanumeric noise symbols
    cleaned = re.sub(r'[\(\)\[\]\<\>\{\}\~\_\*]+', ' ', text)
    # Remove repetitive character loops caused by audio line hum (e.g. जाएजाएजाए or abababab)
    cleaned = re.sub(r'(.{1,8})\1{3,}', r'\1', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # Split into words and filter isolated noise tokens
    words = cleaned.split()
    filtered_words = []
    for w in words:
        w_lower = re.sub(r'[^\w]', '', w.lower())
        if w_lower and w_lower not in PURE_FILLER_WORDS:
            filtered_words.append(w)

    result = " ".join(filtered_words).strip()
    
    # If the user only said a single filler word or noise
    if len(result) < 2:
        return ""

    return result

class WhisperSTTEngine:
    def __init__(
        self,
        model_size: str = settings.STT_MODEL_SIZE,
        device: str = settings.STT_DEVICE,
        compute_type: str = settings.STT_COMPUTE_TYPE,
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None
        self._init_model()

    def _init_model(self):
        from faster_whisper import WhisperModel
        logger.info(f"Loading faster-whisper '{self.model_size}' on '{self.device}' ({self.compute_type})...")
        t0 = time.time()
        try:
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            # Warm up CUDA kernels
            dummy = np.zeros(16000, dtype=np.float32)
            list(self.model.transcribe(dummy, language="hi"))
            load_time = time.time() - t0
            logger.info(f"faster-whisper '{self.model_size}' ready on {self.device} in {load_time:.2f}s!")
        except Exception as e:
            logger.warning(f"CUDA init failed ({e}). Falling back to CPU...")
            self.device = "cpu"
            self.compute_type = "int8"
            self.model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="int8",
                cpu_threads=8,
            )
            logger.info("faster-whisper loaded on CPU fallback.")

    def transcribe(
        self,
        audio: Union[str, Path, np.ndarray],
        language: Optional[str] = None,
        beam_size: int = 1,
    ) -> Tuple[str, str, float]:
        """
        Applies DSP bandpass filtering, transcribes audio, and purifies output text.
        """
        if self.model is None:
            self._init_model()

        t0 = time.time()

        if isinstance(audio, (str, Path)):
            audio_input = str(audio)
        else:
            raw_audio = audio.flatten().astype(np.float32)
            # Apply telephony bandpass filter (250Hz - 3800Hz) to remove line noise
            filtered_audio = audio_filter.apply_telephony_filter(raw_audio)
            audio_input = audio_filter.apply_noise_gate(filtered_audio)

        # Clean, natural Hinglish conversation prior without hallucination-inducing phrases
        initial_prompt = "Namaste, haanji, Sachindra, message, call."

        try:
            segments, info = self.model.transcribe(
                audio_input,
                beam_size=beam_size,
                temperature=0.0,
                vad_filter=False,
                language=language,
                initial_prompt=initial_prompt,
                condition_on_previous_text=False,
                no_speech_threshold=0.7,
                compression_ratio_threshold=2.4,
            )

            raw_text = " ".join([s.text.strip() for s in segments]).strip()
            purified_text = clean_transcript(raw_text)
            latency = time.time() - t0

            detected_lang = info.language if info.language in ["hi", "en", "ur", "mr", "pa", "gu"] else "hi"

            logger.info(f"[STT] Raw: '{raw_text}' -> Purified: '{purified_text}' (in {latency:.2f}s)")
            return purified_text, detected_lang, latency

        except Exception as e:
            logger.error(f"Error during transcription: {e}")
            return "", "hi", 0.0

# Global singleton
stt_engine: Optional[WhisperSTTEngine] = None

def get_stt_engine() -> WhisperSTTEngine:
    global stt_engine
    if stt_engine is None:
        stt_engine = WhisperSTTEngine()
    return stt_engine
