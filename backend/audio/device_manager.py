"""
Audio Device Manager for AI Call Assistant.
Dynamically resolves input (WASAPI Loopback) and output (VB-Cable) devices
by name and capabilities rather than brittle numerical indices.
"""

import logging
from typing import Optional, Tuple
import soundcard as sc

logger = logging.getLogger("AudioDeviceManager")

class DeviceManager:
    @staticmethod
    def get_loopback_microphone(target_name_substring: str = "speaker") -> Optional[sc.Microphone]:
        """
        Finds the speaker loopback microphone for capturing caller audio from Phone Link.
        Searches all loopback-capable endpoints.
        """
        mics = sc.all_microphones(include_loopback=True)
        # 1. Match by substring
        for mic in mics:
            if target_name_substring.lower() in mic.name.lower() and mic.isloopback:
                logger.info(f"Resolved loopback capture device: {mic.name}")
                return mic
        
        # 2. Fallback to any loopback device
        for mic in mics:
            if mic.isloopback:
                logger.info(f"Fallback loopback capture device: {mic.name}")
                return mic

        # 3. Last resort: default loopback mic
        try:
            return sc.default_microphone(include_loopback=True)
        except Exception as e:
            logger.error(f"Failed to resolve any loopback microphone: {e}")
            return None

    @staticmethod
    def get_uplink_speaker(target_name_substring: str = "cable input") -> Optional[sc.Speaker]:
        """
        Finds the CABLE Input playback device to inject AI audio into Phone Link.
        """
        speakers = sc.all_speakers()
        # 1. Exact match for VB-Cable Input
        for spk in speakers:
            if target_name_substring.lower() in spk.name.lower():
                logger.info(f"Resolved uplink injection device: {spk.name}")
                return spk

        # 2. Match any VB-Audio device
        for spk in speakers:
            if "vb-audio" in spk.name.lower() or "cable" in spk.name.lower():
                logger.info(f"Resolved alternate uplink injection device: {spk.name}")
                return spk

        logger.warning("Could not find VB-Cable Input. Audio injection to caller will not work until VB-Cable is installed.")
        return None

    @staticmethod
    def get_devices() -> Tuple[Optional[sc.Microphone], Optional[sc.Speaker]]:
        """Returns (loopback_mic, uplink_speaker) tuple."""
        loopback = DeviceManager.get_loopback_microphone()
        uplink = DeviceManager.get_uplink_speaker()
        return loopback, uplink
