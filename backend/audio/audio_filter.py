"""
Audio Pre-Processing & DSP Filter for AI Call Assistant.
Applies telephony bandpass filtering and noise gating to remove line hiss,
rumble, and breathing before feeding to speech recognition.
"""

import numpy as np
from scipy import signal

class AudioFilter:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        # 4th order Butterworth bandpass filter (250Hz - 3800Hz - Telephony voice band)
        nyquist = 0.5 * sample_rate
        low = 250.0 / nyquist
        high = 3800.0 / nyquist
        self.b, self.a = signal.butter(4, [low, high], btype='band')

    def apply_telephony_filter(self, audio: np.ndarray) -> np.ndarray:
        """Filters out low-frequency rumble (<250Hz) and high-frequency hiss (>3800Hz)."""
        if len(audio) < 32:
            return audio
        try:
            filtered = signal.lfilter(self.b, self.a, audio.astype(np.float32))
            return filtered.astype(np.float32)
        except Exception:
            return audio

    def apply_noise_gate(self, audio: np.ndarray, threshold_rms: float = 0.0025) -> np.ndarray:
        """Zeros out silence/ambient hiss below noise floor."""
        rms = float(np.sqrt(np.mean(audio ** 2))) if audio.size > 0 else 0.0
        if rms < threshold_rms:
            return np.zeros_like(audio)
        return audio

# Global singleton
audio_filter = AudioFilter(sample_rate=16000)
