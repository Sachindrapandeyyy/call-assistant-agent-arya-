"""
Voice Activity Detection (VAD) Engine for AI Call Assistant.
Segments caller's continuous audio stream into discrete speech turns.
"""

import time
import logging
from typing import List, Tuple, Optional
import numpy as np

logger = logging.getLogger("VADEngine")

class VADSegmenter:
    def __init__(
        self,
        sample_rate: int = 16000,
        energy_threshold: float = 0.032,         # Immune to ambient room/speaker hiss
        silence_timeout_sec: float = 0.85,       # Snappy 850ms turn completion
        min_speech_duration_sec: float = 0.45,   # 450ms minimum to reject clicks/pops
        max_speech_duration_sec: float = 7.5,    # 7.5s max to prevent runaway ambient clips
    ):
        self.sample_rate = sample_rate
        self.energy_threshold = energy_threshold
        self.silence_timeout_sec = silence_timeout_sec
        self.min_speech_duration_sec = min_speech_duration_sec
        self.max_speech_duration_sec = max_speech_duration_sec

        self.is_speaking = False
        self.speech_start_time = 0.0
        self.last_speech_time = 0.0
        self.active_speech_frames: List[np.ndarray] = []
        self.pre_buffer: List[np.ndarray] = []
        self.pre_buffer_frames_max = int(0.35 * (sample_rate / 512)) # 350ms pre-speech buffer

    def reset(self):
        """Reset state between turns."""
        self.is_speaking = False
        self.speech_start_time = 0.0
        self.last_speech_time = 0.0
        self.active_speech_frames.clear()
        self.pre_buffer.clear()

    def process_chunk(self, audio_chunk: np.ndarray, now: Optional[float] = None) -> Optional[Tuple[np.ndarray, float, float]]:
        """
        Processes a raw audio chunk (mono float32, expected ~16kHz).
        Returns (speech_audio, start_offset, end_offset) when a completed speech turn is detected.
        """
        if now is None:
            now = time.time()
        rms = float(np.sqrt(np.mean(audio_chunk ** 2))) if audio_chunk.size > 0 else 0.0
        is_active = rms > self.energy_threshold

        if not self.is_speaking:
            self.pre_buffer.append(audio_chunk)
            if len(self.pre_buffer) > self.pre_buffer_frames_max:
                self.pre_buffer.pop(0)

            if is_active:
                self.is_speaking = True
                self.speech_start_time = now
                self.last_speech_time = now
                self.active_speech_frames = list(self.pre_buffer)
                self.active_speech_frames.append(audio_chunk)
                self.pre_buffer.clear()
                logger.debug(f"Caller speech started (RMS: {rms:.5f})")
        else:
            self.active_speech_frames.append(audio_chunk)

            if is_active:
                self.last_speech_time = now

            silence_duration = now - self.last_speech_time
            total_duration = now - self.speech_start_time

            # Natural pause reached or max duration exceeded
            if (silence_duration >= self.silence_timeout_sec) or (total_duration >= self.max_speech_duration_sec):
                segment_duration = total_duration - silence_duration if silence_duration >= self.silence_timeout_sec else total_duration

                if segment_duration >= self.min_speech_duration_sec:
                    full_segment = np.concatenate(self.active_speech_frames, axis=0)
                    # Trim trailing dead silence (keep only 150ms buffer) to accelerate Whisper STT
                    trailing_silence_samples = int(max(0, silence_duration - 0.15) * self.sample_rate)
                    if trailing_silence_samples > 0 and len(full_segment) > trailing_silence_samples + int(0.2 * self.sample_rate):
                        full_segment = full_segment[:-trailing_silence_samples]

                    start_off = self.speech_start_time
                    end_off = self.last_speech_time
                    logger.info(f"Completed caller turn: {segment_duration:.2f}s (Clean audio: {len(full_segment)/self.sample_rate:.2f}s)")

                    self.reset()
                    return full_segment, start_off, end_off
                else:
                    self.reset()

        return None

    def flush(self) -> Optional[Tuple[np.ndarray, float, float]]:
        """Flush remaining speech when call ends."""
        if self.is_speaking and self.active_speech_frames:
            full_segment = np.concatenate(self.active_speech_frames, axis=0)
            start_off = self.speech_start_time
            end_off = self.last_speech_time
            self.reset()
            return full_segment, start_off, end_off
        return None
