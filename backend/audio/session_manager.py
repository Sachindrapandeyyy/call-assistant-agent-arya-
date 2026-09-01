"""
Call Session Lifecycle Manager for AI Call Assistant.
Coordinates telephony state, audio capture, VAD segmentation, and database logging
with robust duplicate event deduplication.
"""

import time
import uuid
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import numpy as np
from scipy.io import wavfile

from backend.config import settings
from backend.storage import db
from backend.audio.loopback_capture import LoopbackCaptureEngine
from backend.audio.cable_player import CablePlayerEngine

logger = logging.getLogger("SessionManager")

class CallSessionManager:
    def __init__(self):
        self.active_session_id: Optional[str] = None
        self.current_caller_number: Optional[str] = None
        self.segment_counter = 0
        self.session_dir: Optional[Path] = None
        self._last_event_time: Dict[str, float] = {}

        self.player = CablePlayerEngine(playback_sample_rate=settings.PLAYBACK_SAMPLE_RATE)
        self.capture = LoopbackCaptureEngine(
            on_speech_segment=self._handle_speech_segment,
            target_sample_rate=settings.AUDIO_SAMPLE_RATE,
            capture_sample_rate=settings.PLAYBACK_SAMPLE_RATE
        )

    def hangup_active_call(self):
        """Sends remote auto-hangup command to Android device over WebSocket."""
        try:
            from backend.app import broadcast_ws_message
            logger.info("[SESSION] Sending auto-hangup command to Android client...")
            broadcast_ws_message("hangup_call", {"session_id": self.active_session_id})
        except Exception as e:
            logger.error(f"Failed to send hangup signal: {e}")

    def handle_telephony_event(self, event_type: str, data: Dict[str, Any]):
        """Dispatches telephony events with deduplication."""
        number = data.get("number", "Unknown")
        now = time.time()

        # Deduplicate identical events within 3 seconds
        last_t = self._last_event_time.get(event_type, 0.0)
        if now - last_t < 3.0 and event_type in ["incoming_call", "call_answered"]:
            logger.info(f"Debounced duplicate '{event_type}' event within {now - last_t:.2f}s")
            return
        self._last_event_time[event_type] = now

        if event_type == "incoming_call":
            self._start_ringing(number, data)
        elif event_type == "call_answered":
            self._start_call(number, data)
        elif event_type == "call_ended":
            self._end_call(number, data)
        else:
            logger.info(f"Unhandled telephony event: {event_type} - {data}")
            db.log_telephony_event(self.active_session_id, event_type, str(data))

    def _start_ringing(self, number: str, data: Dict[str, Any]):
        if self.active_session_id and self.capture.is_running:
            return

        session_id = f"call_{datetime_now_str()}_{uuid.uuid4().hex[:6]}"
        self.active_session_id = session_id
        self.current_caller_number = number
        self.segment_counter = 0

        self.session_dir = settings.RECORDINGS_DIR / session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"[CALL SESSION] Incoming call ringing: {number} (Session: {session_id})")
        db.create_call_session(session_id, number)
        db.log_telephony_event(session_id, "incoming_call", str(data))

    def _start_call(self, number: str, data: Dict[str, Any]):
        if self.capture.is_running:
            logger.info(f"Call session {self.active_session_id} is already active. Ignoring duplicate call_answered.")
            return

        if not self.active_session_id:
            session_id = f"call_{datetime_now_str()}_{uuid.uuid4().hex[:6]}"
            self.active_session_id = session_id
            self.session_dir = settings.RECORDINGS_DIR / session_id
            self.session_dir.mkdir(parents=True, exist_ok=True)
            db.create_call_session(session_id, number)

        logger.info(f"[CALL SESSION] Call answered: {number} (Session: {self.active_session_id})")
        db.update_session_state(self.active_session_id, "ACTIVE")
        db.log_telephony_event(self.active_session_id, "call_answered", str(data))

        # Mute physical laptop microphone to block 100% room noise
        try:
            from backend.audio.mic_shield import mic_shield
            mic_shield.mute_physical_mic()
        except Exception as e:
            logger.debug(f"Mic shield note: {e}")

        # Start live WASAPI loopback capture & VAD
        self.capture.start(self.active_session_id)

        # Start live AI receptionist conversation
        try:
            from backend.agent.conversation_manager import conversation_manager
            conversation_manager.start_call(self.active_session_id, number)
        except Exception as e:
            logger.error(f"Error starting conversation manager: {e}")

    def _end_call(self, number: str, data: Dict[str, Any]):
        if not self.active_session_id:
            logger.warning("Received call_ended event but no active session was tracking.")
            return

        session_id = self.active_session_id
        logger.info(f"[CALL SESSION] Call ended: {number} (Session: {session_id})")

        # Restore physical laptop microphone
        try:
            from backend.audio.mic_shield import mic_shield
            mic_shield.unmute_physical_mic()
        except Exception as e:
            logger.debug(f"Mic unshield note: {e}")

        # Stop audio capture & save master WAV
        master_recording_path = self.capture.stop()
        duration = data.get("duration", 0.0)

        db.update_session_state(
            session_id,
            "ENDED",
            duration_sec=duration,
            recording_path=str(master_recording_path) if master_recording_path else None
        )
        db.log_telephony_event(session_id, "call_ended", str(data))

        # Reset session and finalize summary
        try:
            from backend.agent.conversation_manager import conversation_manager
            conversation_manager.end_call()
        except Exception as e:
            logger.error(f"Error ending conversation: {e}")

        self.active_session_id = None
        self.current_caller_number = None

    def _handle_speech_segment(self, audio_data: np.ndarray, start_offset: float, end_offset: float):
        """Called automatically when caller finishes a speech turn."""
        if not self.active_session_id or not self.session_dir:
            return

        self.segment_counter += 1
        seg_idx = self.segment_counter
        seg_path = self.session_dir / f"segment_{seg_idx:03d}.wav"

        # Save segment WAV
        audio_int16 = (audio_data * 32767).clip(-32768, 32767).astype(np.int16)
        wavfile.write(str(seg_path), settings.AUDIO_SAMPLE_RATE, audio_int16)

        duration = end_offset - start_offset
        logger.info(f"[VAD TURN] Segment #{seg_idx} saved: {seg_path.name} (Duration: {duration:.2f}s, [{start_offset:.1f}s -> {end_offset:.1f}s])")

        db.record_speech_segment(
            session_id=self.active_session_id,
            index=seg_idx,
            start_offset=start_offset,
            end_offset=end_offset,
            audio_path=str(seg_path)
        )

def datetime_now_str():
    import datetime
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

# Global singleton
session_manager = CallSessionManager()
