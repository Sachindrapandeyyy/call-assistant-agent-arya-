"""
Production Conversation Manager for AI Call Assistant.
Integrates Deterministic State Machine, Slot Extractor, Whisper STT, Qwen LLM,
Crash-proof TTS, Dual Audio Injection, and Real-Time Barge-In Interruption with UTF-8 safety.
"""

import sys
import time
import json
import threading
import logging
from typing import List, Dict, Optional, Any
import numpy as np

# Force UTF-8 encoding on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from backend.config import settings
from backend.storage import db
from backend.stt.whisper_engine import get_stt_engine
from backend.llm.ollama_client import ollama_client
from backend.llm.slot_extractor import slot_extractor
from backend.agent.state_machine import ConversationStateMachine, CallState
from backend.tts.tts_engine import tts_engine
from backend.audio.session_manager import session_manager
from backend.audio.cable_player import cable_player

logger = logging.getLogger("ConversationManager")

def safe_broadcast(event_type: str, data: dict):
    try:
        from backend.app import broadcast_ws_message
        broadcast_ws_message(event_type, data)
    except Exception:
        pass

class ConversationManager:
    def __init__(self):
        self.state_machine = ConversationStateMachine()
        self.dialogue_history: List[Dict[str, str]] = []
        self.caller_number = "Unknown"
        self.session_id: Optional[str] = None
        self.is_speaking = False
        self._speak_lock = threading.Lock()
        threading.Thread(target=self._prewarm_cache, daemon=True).start()

    def _prewarm_cache(self):
        """Pre-synthesizes initial greeting, VIP greetings, and common conversational turns for 0.00s instant playback."""
        time.sleep(1)
        greetings = [
            "Namaste, main Sachindra sir ki personal assistant Arya hoon. Sachindra sir abhi busy hain, boliye main aapka kya message note kar sakti hoon?",
            "Haanji hello! Main sun rahi hoon, aapka shubh naam kya hai?",
            "Ji main sun rahi hoon, aapka shubh naam kya hai?",
            "Theek hai ji! Main yeh message Sachindra sir tak zaroor pahuncha dungi. Main call ab disconnect kar rahi hoon. Have a wonderful day, bye-bye!",
            "Maaf kijiye, aapki awaaz thodi clear nahi aa rahi hai. Kya aap ek baar dobara bata sakte hain?",
            "Hello? Kya aap mujhe sun pa rahe hain?",
            "Ji samajh gayi, main Sachindra sir ko turant inform karti hoon.",
            "Sachindra sir abhi ek critical technical meeting mein hain, expected hai ki shaam tak free hokar aapse connect karenge! Kya koi aur zaroori baat hai, ya main call wrap up karun?"
        ]
        try:
            from backend.agent.vip_manager import vip_manager
            for meta in vip_manager.vip_cache.values():
                if meta.get("custom_greeting"):
                    greetings.append(meta["custom_greeting"])
        except Exception as e:
            logger.debug(f"VIP prewarm note: {e}")

        tts_engine.prewarm_cache(greetings)

    def start_call(self, session_id: str, caller_number: str):
        """Triggered automatically when a cellular call is answered."""
        self.session_id = session_id
        self.caller_number = caller_number
        self.dialogue_history.clear()
        self.state_machine.start_call(session_id, caller_number)
        from backend.agent.dialogue_engine import dialogue_engine
        dialogue_engine.reset(caller_number)

        logger.info(f"[CONVERSATION] 🚀 Session started: {session_id} for {caller_number}")

        # Hook VAD turn handler
        session_manager.capture.on_speech_segment = self.on_caller_speech_turn

        # Speak initial greeting
        greeting_text = self.state_machine.get_initial_greeting()
        threading.Thread(target=self.speak_response, args=(greeting_text,), daemon=True).start()

    def on_caller_speech_turn(self, audio_data: np.ndarray, start_offset: float, end_offset: float):
        """Called automatically when caller finishes speaking a turn."""
        try:
            if self.is_speaking:
                logger.info("[CONVERSATION] Caller turn received during AI playback (Barge-In). Processing turn...")

            turn_duration = end_offset - start_offset
            logger.info(f"[CONVERSATION] Processing caller turn ({turn_duration:.2f}s)...")

            # 1. Transcribe audio with GPU faster-whisper + DSP filter
            stt = get_stt_engine()
            transcript, lang, stt_latency = stt.transcribe(audio_data)

            # Check for unclear speech
            is_unclear = not transcript.strip() or len(transcript.strip()) < 2

            if not is_unclear:
                safe_transcript = transcript.encode('utf-8', errors='replace').decode('utf-8')
                logger.info(f"[CALLER] ({lang}) -> '{safe_transcript}'")
                self.dialogue_history.append({"role": "user", "content": transcript})
                self.state_machine.update_language(lang)

                # Extract and update state machine entity slots in real-time
                try:
                    extracted = slot_extractor.extract_from_utterance(transcript, self.dialogue_history)
                    if extracted:
                        self.state_machine.apply_extracted_entities(extracted)
                except Exception as ex:
                    logger.debug(f"Slot extraction note: {ex}")

            # 2. Dynamic Dialogue Processing with Full Memory & Q&A
            from backend.agent.dialogue_engine import dialogue_engine
            ai_reply, should_hangup = dialogue_engine.process_turn(transcript, self.dialogue_history)
            logger.info(f"[DIALOGUE DECISION] Reply: '{ai_reply}' | Should Hangup: {should_hangup}")

            # Broadcast live turn to Android
            safe_broadcast("live_transcript", {
                "role": "caller",
                "text": transcript
            })

            # 3. Speak response to caller
            self.speak_response(ai_reply)

            # 4. Auto-Hangup if call has reached its conclusion
            if should_hangup:
                logger.info("[CONVERSATION] Call concluded. Scheduling auto-hangup in 2.2s...")
                def _delayed_hangup():
                    time.sleep(2.2)
                    session_manager.hangup_active_call()
                threading.Thread(target=_delayed_hangup, daemon=True).start()

        except Exception as e:
            logger.error(f"Error handling caller speech turn: {e}", exc_info=True)
            self.speak_response("Ji main sun rahi hoon. Aap bata sakte hain.")

    def speak_response(self, text: str):
        """Synthesizes speech and injects into VB-Cable + Infinix Bluetooth with atomic locking."""
        if not text or not text.strip():
            return

        with self._speak_lock:
            self.is_speaking = True
            safe_text = text.encode('utf-8', errors='replace').decode('utf-8')
            logger.info(f"[AI ASSISTANT] Speaking -> '{safe_text}'")
            self.dialogue_history.append({"role": "assistant", "content": text})

            # Broadcast Arya turn to Android
            safe_broadcast("live_transcript", {
                "role": "arya",
                "text": text
            })

            session_manager.capture.mute_for_playback()

            try:
                audio_data, tts_latency = tts_engine.synthesize_to_numpy(
                    text, target_sample_rate=settings.PLAYBACK_SAMPLE_RATE
                )
                # Chunked playback with sub-50ms barge-in interruption capability
                cable_player.play_audio_blocking(audio_data, source_sample_rate=settings.PLAYBACK_SAMPLE_RATE)
            except Exception as e:
                logger.error(f"Error speaking response: {e}")
            finally:
                self.is_speaking = False
                session_manager.capture.unmute_after_playback(cooldown_sec=0.25)

    def end_call(self):
        """Called automatically when call disconnects. Finalizes summary and SQLite storage."""
        full_transcript = []
        for d in self.dialogue_history:
            speaker = "Caller" if d["role"] == "user" else "AI Assistant"
            full_transcript.append(f"{speaker}: {d['content']}")

        transcript_str = "\n".join(full_transcript)
        logger.info(f"[CALL CONCLUDED] Transcript turns: {len(self.dialogue_history)}")

        summary_data = self.state_machine.end_call()

        if self.dialogue_history and ollama_client.is_available():
            try:
                llm_summary = ollama_client.generate_summary(transcript_str)
                # Merge LLM summary with deterministic state machine slots
                merged_summary = {
                    "caller_name": summary_data.get("caller_name") or llm_summary.get("caller_name", "Unknown"),
                    "caller_phone": self.caller_number,
                    "company_organization": summary_data.get("company_organization") or llm_summary.get("category", "Unknown"),
                    "category": summary_data.get("relationship") or llm_summary.get("category", "General"),
                    "urgency": summary_data.get("urgency") or llm_summary.get("urgency", "Medium"),
                    "reason_for_call": summary_data.get("reason_for_call") or llm_summary.get("reason_for_call", "N/A"),
                    "message": summary_data.get("message") or llm_summary.get("message", "N/A"),
                    "callback_requested": summary_data.get("callback_requested") if summary_data.get("callback_requested") is not None else llm_summary.get("callback_requested", False),
                    "important_dates_or_times": summary_data.get("important_dates_times") or llm_summary.get("important_dates_or_times", "None"),
                    "follow_up_action_required": llm_summary.get("follow_up_action_required", "Inform Sachindra sir")
                }

                logger.info(f"[CALL SUMMARY] Caller: {merged_summary['caller_name']} | Urgency: {merged_summary['urgency']} | Reason: {merged_summary['reason_for_call']}")

                if self.session_id:
                    try:
                        db.update_session_state(
                            self.session_id,
                            "ENDED",
                            summary=json.dumps(merged_summary, ensure_ascii=False),
                            transcript=transcript_str,
                            processing_status="COMPLETED"
                        )
                        logger.info(f"Persisted structured summary to SQLite for session {self.session_id}")
                        safe_broadcast("call_summary_updated", {
                            "session_id": self.session_id,
                            "caller_number": self.caller_number,
                            "summary": merged_summary
                        })
                    except Exception as db_err:
                        logger.warning(f"Error saving summary to database: {db_err}")

                try:
                    from backend.notifications.telegram_notifier import telegram_notifier
                    master_rec = settings.RECORDINGS_DIR / self.session_id / f"call_full_{self.session_id}.wav" if self.session_id else None
                    telegram_notifier.send_call_summary(
                        caller_number=self.caller_number,
                        summary=merged_summary,
                        transcript=transcript_str,
                        audio_path=master_rec if master_rec and master_rec.exists() else None
                    )
                except Exception as e:
                    logger.debug(f"Telegram notification dispatch note: {e}")

            except Exception as e:
                logger.error(f"Error generating structured summary: {e}")

        self.state_machine.state = CallState.IDLE

# Global singleton
conversation_manager = ConversationManager()
