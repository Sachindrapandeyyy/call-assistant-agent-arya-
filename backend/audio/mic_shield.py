"""
Physical Hardware Microphone Shield for AI Call Assistant.
Automatically mutes the laptop's physical microphone during active cellular calls
to ensure 100% room silence and prevent surrounding people/fan noise from leaking into the call.
Restores physical microphone unmuted state when call ends.
Created and developed by Sachindra Shekhar Pandey.
"""

import sys
import logging
from typing import Optional
import ctypes

logger = logging.getLogger("MicShield")

class PhysicalMicShield:
    def __init__(self):
        self._vol_interface = None
        self._original_mute_state = 0
        self._is_shielded = False

    def _init_interface(self):
        try:
            try:
                ctypes.windll.ole32.CoInitialize(None)
            except Exception:
                pass

            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            mic = AudioUtilities.GetMicrophone()
            if mic:
                interface = mic.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self._vol_interface = cast(interface, POINTER(IAudioEndpointVolume))
        except Exception as e:
            logger.debug(f"Mic shield init note: {e}")

    def mute_physical_mic(self):
        """Mutes physical laptop microphone to block all room noise during call."""
        if self._is_shielded:
            logger.debug("[MIC SHIELD] Already shielded, skipping duplicate mute.")
            return
        if self._vol_interface is None:
            self._init_interface()
        if self._vol_interface:
            try:
                self._original_mute_state = self._vol_interface.GetMute()
                self._vol_interface.SetMute(1, None)
                self._is_shielded = True
                logger.info("[MIC SHIELD] 🔇 Physical laptop microphone MUTED (Room audio bleed blocked 100%).")
            except Exception as e:
                logger.warning(f"Failed to mute physical mic: {e}")

    def unmute_physical_mic(self):
        """Restores physical laptop microphone state when call terminates."""
        if self._vol_interface and self._is_shielded:
            try:
                self._vol_interface.SetMute(self._original_mute_state, None)
                self._is_shielded = False
                logger.info("[MIC SHIELD] 🎙️ Physical laptop microphone RESTORED to normal.")
            except Exception as e:
                logger.warning(f"Failed to unmute physical mic: {e}")

# Global singleton
mic_shield = PhysicalMicShield()
