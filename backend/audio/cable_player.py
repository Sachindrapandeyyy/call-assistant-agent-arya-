"""
VB-Cable and Direct Bluetooth Audio Injection Engine with Real-Time Barge-In Interruption.
Plays synthesized speech into CABLE Input AND directly to Infinix Hands-Free Bluetooth Output.
Supports instantaneous interruption (<50ms) when caller begins speaking.
"""

import time
import threading
import logging
from typing import Optional
import numpy as np
import soundcard as sc
import sounddevice as sd
from scipy import signal

from backend.audio.device_manager import DeviceManager

logger = logging.getLogger("CablePlayer")

class CablePlayerEngine:
    def __init__(self, playback_sample_rate: int = 48000):
        self.playback_sample_rate = playback_sample_rate
        self.is_playing = False
        self._lock = threading.Lock()
        self._stop_requested = threading.Event()
        self._cached_infinix_idx: Optional[int] = None
        self._resolve_infinix_device()

    def _resolve_infinix_device(self):
        """Finds direct Infinix Bluetooth Hands-Free output device index."""
        try:
            for idx, dev in enumerate(sd.query_devices()):
                name = dev.get("name", "").lower()
                if "infinix" in name and dev.get("max_output_channels", 0) > 0:
                    self._cached_infinix_idx = idx
                    logger.info(f"Resolved Direct Infinix Bluetooth Output Device [{idx}]: {dev['name']}")
                    return
        except Exception as e:
            logger.debug(f"Bluetooth device discovery note: {e}")

    def stop_playback(self):
        """Immediately halts ongoing audio playback on barge-in / caller interruption."""
        if self.is_playing:
            logger.info("[BARGE-IN] 🛑 Halting active audio playback due to caller interruption!")
            self._stop_requested.set()
            try:
                sd.stop()
            except Exception:
                pass

    def play_audio_blocking(self, audio_data: np.ndarray, source_sample_rate: int = 48000) -> bool:
        """
        Plays audio with chunked streaming and barge-in detection.
        Returns True if played to completion, False if interrupted by caller.
        """
        if audio_data.size == 0:
            return True

        with self._lock:
            self.is_playing = True
            self._stop_requested.clear()
            was_interrupted = False

            try:
                mono = audio_data.flatten().astype(np.float32)

                # 0. Append assistant voice to master recording so WAV file has both caller + Arya
                try:
                    from backend.audio.session_manager import session_manager
                    if session_manager.capture and session_manager.capture.is_running:
                        session_manager.capture.append_assistant_playback(mono, source_sample_rate)
                except Exception as rec_err:
                    logger.debug(f"Note on assistant recording append: {rec_err}")

                # 1. Play to direct Infinix Bluetooth endpoint if present
                self._resolve_infinix_device()
                if self._cached_infinix_idx is not None:
                    try:
                        bt_audio = signal.resample_poly(mono, 1, source_sample_rate // 16000).astype(np.float32) if source_sample_rate != 16000 else mono
                        sd.play(bt_audio, samplerate=16000, device=self._cached_infinix_idx)
                    except Exception as bt_err:
                        logger.debug(f"Direct BT playback note: {bt_err}")

                # 2. Play to CABLE Input via chunked speaker playback for barge-in checks
                if source_sample_rate != self.playback_sample_rate:
                    num_samples = int(len(mono) * self.playback_sample_rate / source_sample_rate)
                    cable_audio = signal.resample(mono, num_samples).astype(np.float32)
                else:
                    cable_audio = mono

                speaker = DeviceManager.get_uplink_speaker()
                if speaker is not None:
                    # Stream in 50ms chunks to allow instant (<50ms) barge-in interruption
                    chunk_size = int(self.playback_sample_rate * 0.05)  # 2400 samples
                    audio_stereo = np.column_stack([cable_audio, cable_audio])

                    with speaker.player(samplerate=self.playback_sample_rate, channels=2) as spk_stream:
                        for i in range(0, len(audio_stereo), chunk_size):
                            if self._stop_requested.is_set():
                                was_interrupted = True
                                break
                            chunk = audio_stereo[i:i + chunk_size]
                            spk_stream.play(chunk)

                # Wait for any lingering BT playback or check interruption
                if self._stop_requested.is_set():
                    was_interrupted = True
                    try:
                        sd.stop()
                    except Exception:
                        pass
                elif self._cached_infinix_idx is not None:
                    try:
                        sd.wait()
                    except Exception:
                        pass

            except Exception as e:
                logger.error(f"Error during audio playback to caller: {e}")
            finally:
                self.is_playing = False
                self._stop_requested.clear()

            return not was_interrupted

    def play_audio(self, audio_data: np.ndarray, source_sample_rate: int = 48000) -> bool:
        """Alias for synchronous blocking playback."""
        return self.play_audio_blocking(audio_data, source_sample_rate)

# Global singleton
cable_player = CablePlayerEngine()
