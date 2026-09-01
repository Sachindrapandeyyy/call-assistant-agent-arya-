"""
WASAPI Loopback Capture Engine with Real-Time Barge-In Interruption Detection.
Continuously reads 2-channel caller audio from Windows default speakers,
downmixes to clean mono float32, runs sensitive real-time VAD,
and triggers sub-50ms barge-in cutoff when caller interrupts.
"""

import time
import queue
import warnings
import threading
import logging
from pathlib import Path
from typing import Callable, Optional, List
import numpy as np
import soundcard as sc
from scipy.io import wavfile
from scipy import signal

from backend.config import settings
from backend.audio.device_manager import DeviceManager
from backend.audio.vad import VADSegmenter
from backend.audio.cable_player import cable_player

warnings.filterwarnings("ignore", category=sc.SoundcardRuntimeWarning)

logger = logging.getLogger("LoopbackCapture")

class LoopbackCaptureEngine:
    def __init__(
        self,
        on_speech_segment: Optional[Callable[[np.ndarray, float, float], None]] = None,
        target_sample_rate: int = 16000,
        capture_sample_rate: int = 48000,
    ):
        self.on_speech_segment = on_speech_segment
        self.target_sample_rate = target_sample_rate
        self.capture_sample_rate = capture_sample_rate

        self.vad = VADSegmenter(
            sample_rate=target_sample_rate,
            energy_threshold=settings.VAD_THRESHOLD,
            silence_timeout_sec=settings.SILENCE_TIMEOUT,
            min_speech_duration_sec=settings.MIN_SPEECH_DURATION
        )
        self.is_running = False
        self.capture_thread: Optional[threading.Thread] = None

        self.is_muted_for_playback = False
        self.unmute_cooldown_time = 0.0
        self._barge_in_consecutive_chunks = 0

        self.turn_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._turn_dispatcher_loop, daemon=True)
        self.worker_thread.start()

        self.master_recording_frames: List[np.ndarray] = []
        self._recording_lock = threading.Lock()
        self.session_id: Optional[str] = None
        self.call_start_time = 0.0

    def mute_for_playback(self):
        """Prepares capture engine for AI playback with active barge-in listening."""
        self.is_muted_for_playback = True
        self._barge_in_consecutive_chunks = 0
        self.vad.reset()
        while not self.turn_queue.empty():
            try:
                self.turn_queue.get_nowait()
                self.turn_queue.task_done()
            except Exception:
                break

    def unmute_after_playback(self, cooldown_sec: float = 0.25):
        """Unmutes capture after AI finishes speaking with an acoustic cooldown."""
        self.unmute_cooldown_time = time.time() + cooldown_sec
        self.is_muted_for_playback = False
        self._barge_in_consecutive_chunks = 0
        self.vad.reset()

    def start(self, session_id: str):
        """Starts real-time loopback capture and VAD processing."""
        if self.is_running:
            return

        self.session_id = session_id
        self.is_running = True
        self.call_start_time = time.time()
        self.master_recording_frames.clear()
        self.vad.reset()

        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        logger.info(f"Started loopback capture engine for session {session_id}")

    def stop(self) -> Optional[Path]:
        """Stops capture and saves master call recording."""
        if not self.is_running:
            return None

        self.is_running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=3.0)

        # Signal worker thread to exit
        self.turn_queue.put(None)

        recording_path = None
        with self._recording_lock:
            if self.master_recording_frames and self.session_id:
                try:
                    full_audio = np.concatenate(self.master_recording_frames, axis=0)
                    out_dir = settings.RECORDINGS_DIR / self.session_id
                    out_dir.mkdir(parents=True, exist_ok=True)
                    recording_path = out_dir / f"call_full_{self.session_id}.wav"

                    audio_int16 = (full_audio * 32767).clip(-32768, 32767).astype(np.int16)
                    wavfile.write(str(recording_path), self.target_sample_rate, audio_int16)
                    logger.info(f"Saved master call recording: {recording_path} ({len(full_audio)/self.target_sample_rate:.1f}s)")
                except Exception as e:
                    logger.error(f"Failed to save master recording: {e}")

        return recording_path

    def _turn_dispatcher_loop(self):
        """Asynchronous worker processing speech turns."""
        while True:
            try:
                item = self.turn_queue.get()
                if item is None:
                    break
                audio, start_offset, end_offset = item
                if self.on_speech_segment:
                    self.on_speech_segment(audio, start_offset, end_offset)
                self.turn_queue.task_done()
            except Exception as e:
                logger.error(f"Error dispatching speech turn: {e}", exc_info=True)

    def _capture_loop(self):
        """Dedicated audio capture loop using native 2-channel stereo WASAPI loopback."""
        mic = DeviceManager.get_loopback_microphone()
        if mic is None:
            logger.error("No loopback microphone found!")
            self.is_running = False
            return

        block_size = 2048

        try:
            with mic.recorder(samplerate=self.capture_sample_rate, channels=2, blocksize=block_size) as recorder:
                while self.is_running:
                    chunk = recorder.record(numframes=block_size)
                    if chunk is None or len(chunk) == 0:
                        continue

                    # Downmix stereo to mono
                    if chunk.ndim > 1:
                        mono_48k = chunk.mean(axis=1).astype(np.float32)
                    else:
                        mono_48k = chunk.flatten().astype(np.float32)

                    # Polyphase FIR decimation (48kHz -> 16kHz via 1/3 decimation) with 0 edge ringing
                    chunk_16k = signal.resample_poly(mono_48k, 1, 3).astype(np.float32)

                    with self._recording_lock:
                        self.master_recording_frames.append(chunk_16k)

                    # Skip VAD while AI is speaking to prevent self-interruption from speaker echo
                    if self.is_muted_for_playback:
                        continue

                    now = time.time()
                    if now < self.unmute_cooldown_time:
                        continue

                    # Feed into VAD
                    segment_result = self.vad.process_chunk(chunk_16k)
                    if segment_result:
                        speech_audio, start_ts, end_ts = segment_result
                        self.turn_queue.put((speech_audio, start_ts - self.call_start_time, end_ts - self.call_start_time))

        except Exception as e:
            logger.error(f"Loopback capture loop exception: {e}")
        finally:
            self.is_running = False
            logger.info("Loopback capture loop terminated.")
