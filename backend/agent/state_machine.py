"""
Deterministic Conversation State Machine for AI Call Assistant.
Serves as the absolute authority for conversation state transitions, slot tracking,
safety guardrails, urgency handling, and call termination rules.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from enum import Enum

logger = logging.getLogger("StateMachine")

class CallState(str, Enum):
    IDLE = "IDLE"
    GREETING = "GREETING"
    LISTENING = "LISTENING"
    COLLECTING_INFO = "COLLECTING_INFO"
    HANDLING_URGENT = "HANDLING_URGENT"
    CLARIFYING = "CLARIFYING"
    WRAP_UP = "WRAP_UP"
    ENDING = "ENDING"

class SlotConfidence(str, Enum):
    UNKNOWN = "UNKNOWN"
    UNCERTAIN = "UNCERTAIN"
    CONFIRMED = "CONFIRMED"

@dataclass
class CallSlots:
    caller_name: Optional[str] = None
    name_confidence: SlotConfidence = SlotConfidence.UNKNOWN

    reason_for_call: Optional[str] = None
    reason_confidence: SlotConfidence = SlotConfidence.UNKNOWN

    message: Optional[str] = None
    message_confidence: SlotConfidence = SlotConfidence.UNKNOWN

    callback_requested: Optional[bool] = None
    urgency: str = "Medium"  # Low, Medium, High, Urgent

    phone_number: str = "Unknown"
    important_dates_times: Optional[str] = None
    company_organization: Optional[str] = None
    relationship: str = "Unknown"  # family, friend, company, recruiter, client, unknown

    language: str = "hinglish"  # hindi, hinglish, english

    clarification_count: int = 0
    max_clarification_attempts: int = 2

    silence_count: int = 0
    max_silence_attempts: int = 2

    interruption_count: int = 0
    transfer_requested: bool = False
    transfer_authorized: bool = False

    def is_slot_filled(self, slot_name: str) -> bool:
        val = getattr(self, slot_name, None)
        return val is not None and str(val).strip() != "" and str(val).lower() not in ["unknown", "none", "null"]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["name_confidence"] = self.name_confidence.value
        d["reason_confidence"] = self.reason_confidence.value
        d["message_confidence"] = self.message_confidence.value
        return d

class ConversationStateMachine:
    def __init__(self):
        self.state = CallState.IDLE
        self.slots = CallSlots()
        self.dialogue_history: List[Dict[str, str]] = []
        self.session_id: Optional[str] = None
        self.custom_vip_greeting: Optional[str] = None
        self.callback_asked: bool = False

    def start_call(self, session_id: str, caller_number: str):
        """Initializes state machine for new incoming call with VIP rule checks."""
        self.session_id = session_id
        self.state = CallState.GREETING
        self.slots = CallSlots(phone_number=caller_number)
        self.dialogue_history.clear()
        self.custom_vip_greeting = None
        self.callback_asked = False

        # Check VIP contacts database
        try:
            from backend.agent.vip_manager import vip_manager
            vip_info = vip_manager.get_vip_info(caller_number)
            if vip_info:
                self.slots.caller_name = vip_info.get("name")
                self.slots.relationship = vip_info.get("category", "family")
                self.slots.urgency = vip_info.get("urgency", "High")
                self.custom_vip_greeting = vip_info.get("custom_greeting")
                logger.info(f"[VIP CALL DETECTED] 👑 Contact: {self.slots.caller_name} ({self.slots.relationship})")
        except Exception as e:
            logger.debug(f"VIP check note: {e}")

        logger.info(f"[STATE MACHINE] Call started: {session_id} from {caller_number}")

    def get_initial_greeting(self) -> str:
        """Returns personalized VIP greeting or professional, warm Arya greeting."""
        if self.custom_vip_greeting:
            return self.custom_vip_greeting
        return "Namaste, main Sachindra sir ki personal assistant Arya hoon. Sachindra sir abhi busy hain, boliye main aapka kya message note kar sakti hoon?"

    def update_language(self, detected_lang: str):
        """Sets detected language for downstream TTS matching."""
        if detected_lang in ["hi", "hindi"]:
            self.slots.language = "hindi"
        elif detected_lang in ["en", "english"]:
            self.slots.language = "english"
        else:
            self.slots.language = "hinglish"

    def apply_extracted_entities(self, entities: Dict[str, Any]):
        """Deterministically updates slots from entity extractor with anti-hallucination checks."""
        # 1. Caller Name
        name = entities.get("caller_name")
        if name and name.strip() and name.lower() not in ["unknown", "none", "null", "caller", "user"]:
            self.slots.caller_name = name.strip()
            self.slots.name_confidence = SlotConfidence.CONFIRMED

        # 2. Company / Organization
        org = entities.get("company_organization")
        if org and org.strip() and org.lower() not in ["unknown", "none", "null"]:
            self.slots.company_organization = org.strip()

        # 3. Reason for Call
        reason = entities.get("reason_for_call")
        if reason and reason.strip() and reason.lower() not in ["unknown", "none", "null"]:
            self.slots.reason_for_call = reason.strip()
            self.slots.reason_confidence = SlotConfidence.CONFIRMED

        # 4. Message
        msg = entities.get("message")
        if msg and msg.strip() and msg.lower() not in ["unknown", "none", "null"]:
            self.slots.message = msg.strip()
            self.slots.message_confidence = SlotConfidence.CONFIRMED

        # 5. Dates / Times
        dt = entities.get("important_dates_times")
        if dt and dt.strip() and dt.lower() not in ["unknown", "none", "null"]:
            self.slots.important_dates_times = dt.strip()

        # 6. Callback requested
        cb = entities.get("callback_requested")
        if isinstance(cb, bool):
            self.slots.callback_requested = cb
            self.callback_asked = True

        # 7. Urgency
        urg = entities.get("urgency")
        if urg in ["Low", "Medium", "High", "Urgent"]:
            self.slots.urgency = urg

        # 8. Relationship
        rel = entities.get("relationship")
        if rel and rel.lower() not in ["unknown", "none"]:
            self.slots.relationship = rel

        logger.info(f"[STATE MACHINE] Updated slots: Name={self.slots.caller_name}, Reason={self.slots.reason_for_call}, Urgency={self.slots.urgency}, Callback={self.slots.callback_requested}")

    def evaluate_next_step(self, user_text: str, is_unclear: bool = False, is_silent: bool = False) -> Dict[str, Any]:
        """
        Deterministic decision engine that determines state transition and prompt guidance.
        Returns: { 'action': str, 'prompt_guidance': str, 'force_response': Optional[str], 'should_hangup': bool }
        """
        lower = user_text.lower().strip()

        # 1. Handle Unclear / Noise
        if is_unclear:
            self.slots.clarification_count += 1
            if self.slots.clarification_count > self.slots.max_clarification_attempts:
                self.state = CallState.ENDING
                return {
                    "action": "END_CALL",
                    "force_response": "Maaf kijiye, connection clear nahi hai. Aap please Sachindra sir ko message ya WhatsApp kar dijiye. Dhanyawad, bye!",
                    "should_hangup": True
                }
            self.state = CallState.CLARIFYING
            return {
                "action": "CLARIFY",
                "force_response": "Maaf kijiye, aapki awaaz thodi clear nahi aa rahi hai. Kya aap ek baar dobara bata sakte hain?"
            }
        else:
            self.slots.clarification_count = 0

        # 2. Handle Silence
        if is_silent:
            self.slots.silence_count += 1
            if self.slots.silence_count > self.slots.max_silence_attempts:
                self.state = CallState.ENDING
                return {
                    "action": "END_CALL",
                    "force_response": "Aapki aawaz nahi aa rahi hai. Main call disconnect kar rahi hoon. Aapka din shubh ho, bye!",
                    "should_hangup": True
                }
            return {
                "action": "PROMPT_SILENCE",
                "force_response": "Hello? Kya aap mujhe sun pa rahe hain?"
            }
        else:
            self.slots.silence_count = 0

        # 3. Check for Caller Exit Phrases (Polite Disconnect with Auto-Hangup)
        exit_words = [
            "bye", "alvida", "thank you", "thanks", "bas itna hi", "cut the call", "call cut",
            "rakhta hoon", "rakhti hoon", "kuch nahi", "no that is all", "no that's all",
            "theek hai ji", "theek hai bye", "aur kuch nahi", "bas", "ok bye", "bye bye",
            "no thanks", "nahi", "no", "ji nahi", "mat karna", "nahi chahiye", "नहीं", "जी नहीं"
        ]
        if any(w in lower for w in exit_words) and self.callback_asked:
            self.state = CallState.ENDING
            return {
                "action": "END_CALL",
                "force_response": "Theek hai ji! Main yeh message Sachindra sir tak zaroor pahuncha dungi. Main call ab disconnect kar rahi hoon. Have a wonderful day, bye-bye!",
                "should_hangup": True
            }

        # 4. Check for Urgency
        if self.slots.urgency in ["High", "Urgent"] or any(w in lower for w in ["urgent", "emergency", "zaroori hai", "bahut urgent"]):
            self.state = CallState.HANDLING_URGENT
            self.slots.transfer_requested = True
            return {
                "action": "HANDLE_URGENT",
                "force_response": "Ji samajh gayi, main Sachindra sir ko turant inform karti hoon."
            }

        # 5. Direct Handling of General & Factual Questions (Latin + Devanagari)
        if any(w in lower for w in ["capital", "कैपिटल", "rajdhani", "राजधानी", "kya hai", "क्या है", "kaise", "what is", "who is", "kahan", "कहाँ", "kon hai", "कौन है"]):
            if any(w in lower for w in ["capital", "कैपिटल", "rajdhani", "राजधानी", "काप्टल"]):
                return {
                    "action": "GENERAL_QA",
                    "force_response": "India ki capital New Delhi hai! Waise aapka shubh naam kya hai aur Sachindra sir ke liye kya message hai?"
                }
            if any(w in lower for w in ["kab", "कब", "when", "free", "फ्री", "time"]):
                return {
                    "action": "EXECUTIVE_QA",
                    "force_response": "Sachindra sir abhi ek critical technical meeting mein hain aur shaam tak free honge! Waise aapka shubh naam kya hai?"
                }

        # 6. Missing Essential Information Flow
        # If we don't have caller's name:
        if not self.slots.is_slot_filled("caller_name"):
            self.state = CallState.COLLECTING_INFO
            if any(w in lower for w in ["hello", "haan", "hi", "sun rahe ho", "sun rahi ho", "awaaz", "namaste"]):
                return {
                    "action": "ASK_NAME_FAST",
                    "force_response": "Haanji hello! Main sun rahi hoon, aapka shubh naam kya hai?"
                }
            return {
                "action": "ASK_NAME",
                "force_response": "Ji main sun rahi hoon, aapka shubh naam kya hai?"
            }

        name_prefix = f"{self.slots.caller_name} ji" if self.slots.caller_name else "ji"
        if not self.slots.is_slot_filled("reason_for_call") and not self.slots.is_slot_filled("message"):
            self.state = CallState.COLLECTING_INFO
            return {
                "action": "ASK_REASON",
                "force_response": f"Namaste {name_prefix}! Sachindra sir ke liye aapka kya zaroori message hai?"
            }

        if not self.callback_asked and self.slots.callback_requested is None:
            self.callback_asked = True
            self.state = CallState.COLLECTING_INFO
            return {
                "action": "ASK_CALLBACK",
                "force_response": f"Ji {name_prefix}, maine aapka message note kar liya hai. Kya aap chahte hain ki Sachindra sir aapse call back karein?"
            }

        # 7. Multi-Turn Open Dialogue & Smart Executive Assistant Q&A
        if any(w in lower for w in ["kab", "when", "free", "time", "kahan", "work", "kya karte", "who", "kon", "number"]):
            if any(w in lower for w in ["kab", "when", "free", "time"]):
                return {
                    "action": "EXECUTIVE_QA",
                    "force_response": "Sachindra sir abhi ek critical technical meeting mein hain, expected hai ki shaam tak free hokar aapse connect karenge! Kya koi aur zaroori baat hai, ya main call wrap up karun?"
                }
            if any(w in lower for w in ["kya karte", "work", "engineer", "job"]):
                return {
                    "action": "EXECUTIVE_QA",
                    "force_response": "Sachindra sir ek passionate AI engineer aur software innovator hain jo cutting-edge systems build karte hain! Kya aapko unke liye koi aur message chhodna hai?"
                }

        # If caller answers the callback question with "nahi" / "no"
        if any(w in lower for w in ["nahi", "no", "ji nahi", "mat karna", "nahi chahiye", "नहीं", "जी नहीं"]):
            self.slots.callback_requested = False
            self.state = CallState.ENDING
            return {
                "action": "END_CALL",
                "force_response": "Theek hai ji! Main yeh message Sachindra sir tak zaroor pahuncha dungi. Main call ab disconnect kar rahi hoon. Have a wonderful day, bye-bye!",
                "should_hangup": True
            }

        # Otherwise, open continuation
        return {
            "action": "OPEN_CONTINUATION",
            "force_response": f"Ji {name_prefix}, maine sab note kar liya hai! Kya aapko Sachindra sir ke liye kuch aur bhi batana hai, ya main call disconnect karun?"
        }

    def end_call(self) -> Dict[str, Any]:
        """Finalizes call state and returns full structured summary parameters."""
        self.state = CallState.ENDING
        return self.slots.to_dict()

# Global singleton
state_machine = ConversationStateMachine()
