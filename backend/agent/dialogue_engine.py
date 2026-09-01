"""
Next-Gen Hyper-Human In-Call Dialogue Engine for ARYA AI.
Engineered for emotional EQ, caller sentiment adaptation, micro-fillers, and zero-repetition flow.
Created and developed by Sachindra Shekhar Pandey.
"""

import re
import json
import logging
from typing import List, Dict, Any, Tuple
from backend.llm.ollama_client import ollama_client
from backend.llm.prompts import ENTERPRISE_ARYA_CALL_PROMPT

logger = logging.getLogger("DialogueEngine")

class DialogueEngine:
    def __init__(self):
        self.caller_name: str = ""
        self.caller_category: str = "general"  # recruiter, urgent, friend, general
        self.message: str = ""
        self.callback_requested: Any = None
        self.callback_asked: bool = False
        self.is_concluded: bool = False

    def reset(self, caller_number: str = "Unknown"):
        self.caller_name = ""
        self.caller_category = "general"
        self.message = ""
        self.callback_requested = None
        self.callback_asked = False
        self.is_concluded = False

    def _detect_sentiment_and_intent(self, text: str):
        lower = text.lower()
        if any(w in lower for w in ["urgent", "emergency", "bahut zaroori", "turant", "jaldi"]):
            self.caller_category = "urgent"
        elif any(w in lower for w in ["interview", "hr", "amazon", "google", "microsoft", "company", "recruiter", "hiring", "job"]):
            self.caller_category = "recruiter"
        elif any(w in lower for w in ["bhai", "yaar", "dost", "party", "kaisa hai"]):
            self.caller_category = "friend"

    def process_turn(self, caller_text: str, dialogue_history: List[Dict[str, str]]) -> Tuple[str, bool]:
        """
        Processes a caller turn with high-EQ sentiment adaptation and dynamic intelligence.
        Returns: (spoken_reply, should_auto_hangup)
        """
        raw_text = caller_text.strip()
        lower = raw_text.lower()
        self._detect_sentiment_and_intent(raw_text)

        # 0. Handle silence or inaudible utterance
        if not raw_text or len(raw_text) < 2:
            return ("Hello? Kya aap mujhe sun pa rahe hain?", False)

        # 1. Check for Immediate Exit / Hangup Intent (Devanagari + Romanized + English)
        exit_phrases = [
            "bye", "alvida", "thank you", "thanks", "bas itna hi", "cut the call", "call cut",
            "rakhta hoon", "rakhti hoon", "kuch nahi", "no that is all", "no that's all",
            "theek hai bye", "aur kuch nahi", "ok bye", "bye bye", "no thanks", "hang up",
            "disconnect kar do", "call disconnect kar do", "call kaat do", "call cut kar do",
            "cut kar do", "phone rakh do", "disconnect", "call disconnect", "kaat do", "phone kaat",
            "kaat do phone", "phone cut",
            # Devanagari Hindi exit phrases
            "कट", "काट", "काट दो", "काटो", "कट कर", "कटकल", "कॉल कट", "कॉल काटो", "कॉल काट",
            "डिस्कनेक्ट", "दिसकनेख", "दिसकनेक्ट", "दिसकनेक्ट कर", "रखो", "रख दो", "बाय",
            "अलविदा", "धन्यवाद", "शुक्रिया", "बस", "और कुछ नहीं", "कुछ नहीं", "कॉल रख"
        ]
        is_negated = any(neg in lower for neg in ["mat karo", "mat kato", "don't", "dont", "ruko", "wait", "nahi tum", "मत करो", "मत काटो"])
        if not is_negated and any(w in lower for w in exit_phrases):
            self.is_concluded = True
            return (
                "Theek hai ji! Main yeh message Sachindra sir tak zaroor pahuncha dungi. Main call ab disconnect kar rahi hoon. Have a wonderful day, bye-bye!",
                True
            )

        # 2. Extract Name if mentioned (Latin + Devanagari Hindi)
        NON_NAMES = {
            "sachindra", "sachin", "shekhar", "pandey", "hello", "namaste", "sir", "available",
            "nahi", "ek", "abhi", "theek", "free", "busy", "kaidi", "accha", "bura", "bhai",
            "yaar", "kaam", "ghar", "office", "call", "baat", "bol", "yahan", "wahan", "kal",
            "aaj", "kuch", "hai", "tha", "raha", "rahi", "hoon", "कैदी", "ठीक", "फ्री", "बिजी",
            "काम", "बात", "कॉल", "आवाज", "बोल", "सुन", "जी", "नहीं", "हाँ"
        }
        name_match = (
            re.search(r"(?:mera naam|shubh naam|my name is|मेरा नाम|शुभ नाम)\s+([A-Za-z\u0900-\u097F]+)", raw_text, re.IGNORECASE) or
            re.search(r"(?:main|i am|this is|मैं)\s+([A-Za-z\u0900-\u097F]+)\s+(?:bol raha|bol rahi|here|from|बोल रहा|बोल रही)", raw_text, re.IGNORECASE) or
            re.search(r"^(?:(?:haan|ji|namaste|hello)\s+)?([A-Za-z\u0900-\u097F]{3,15})\s*(?:bol raha|bol rahi|hai|hoon|है|हूँ)?$", raw_text, re.IGNORECASE)
        )
        if name_match and not self.caller_name:
            candidate = name_match.group(1).strip().capitalize()
            if candidate.lower() not in NON_NAMES and len(candidate) >= 3:
                self.caller_name = candidate
                logger.info(f"[DIALOGUE ENGINE] Captured caller name: {self.caller_name} (Category: {self.caller_category})")

        # 3. Check for Callback Response
        if self.callback_asked and self.callback_requested is None:
            is_asking_question = any(w in lower for w in ["batao", "kya", "kaun", "kab", "kahan", "kyun", "who", "what", "mat karo", "mat kato", "ruko", "wait"])
            if not is_asking_question:
                if any(w in lower for w in ["nahi", "no", "ji nahi", "mat karna", "nahi chahiye", "नहीं", "जी नहीं", "नो", "no callback"]):
                    self.callback_requested = False
                    self.is_concluded = True
                    return (
                        "Theek hai ji! Maine aapka message note kar liya hai aur main Sachindra sir ko update kar dungi. Main call ab disconnect kar rahi hoon. Have a wonderful day, bye-bye!",
                        True
                    )
                elif any(w in lower for w in ["haan", "yes", "call karein", "call back", "phone karein", "zaroor", "हाँ", "कॉल करें", "जी हाँ"]):
                    self.callback_requested = True
                    name_pref = f"{self.caller_name} ji" if self.caller_name else "ji"
                    return (
                        f"Ji {name_pref}, maine note kar liya hai ki aapko callback chahiye. Sachindra sir jaise hi free honge aapse connect karenge! Kya koi aur zaroori baat hai, ya main call disconnect karun?",
                        False
                    )

        # 4. Generate Dynamic High-IQ Response via LLM with Sentiment & Tone Inflexions
        known_slots = {
            "caller_name": self.caller_name or "Unknown (ask politely)",
            "caller_category": self.caller_category,
            "message": self.message or "In progress",
            "callback_requested": self.callback_requested,
            "callback_already_asked": self.callback_asked
        }
        
        system_prompt = (
            f"{ENTERPRISE_ARYA_CALL_PROMPT}\n\n"
            f"CURRENT CALL CONTEXT & DETECTED CATEGORY:\n{json.dumps(known_slots, indent=2)}\n\n"
            "EMOTIONAL INTELLIGENCE GUIDELINES:\n"
            "- If Category is 'urgent': Reassure them with high priority.\n"
            "- If Category is 'recruiter': Be sharp, courteous, and note exact interview details.\n"
            "- If Category is 'friend': Be warm, sweet, and polite.\n"
            "- Speak naturally, politely, and directly. Strictly 1-2 crisp Romanized Hinglish sentences.\n"
            "- NEVER start every reply with 'Areyji' or 'Arey'. Vary your sentences naturally."
        )

        try:
            llm_reply = ollama_client.generate_response(
                messages=dialogue_history,
                system_prompt=system_prompt,
                max_tokens=120,
                temperature=0.45
            )
            cleaned = re.sub(r"^(Arya:\s*|AI:\s*|Assistant:\s*)", "", llm_reply, flags=re.IGNORECASE).strip()
            # Sanitize any accidental placeholder brackets
            name_val = self.caller_name if self.caller_name else ""
            cleaned = re.sub(r"\[(?:Name|Caller Name|Caller|naam|shubh naam|insert name)\]", name_val, cleaned, flags=re.IGNORECASE).strip()
            
            # Strict Name Quarantine: Never allow false names if caller has not given their name
            if not self.caller_name:
                cleaned = re.sub(r"\b(Rahul|Harsh|Aditya|Amit|Sachindra|Sachin|John|Aap|Someone)\s+ji\b", "ji", cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(r"Namaste\s+ji\s*!?", "Namaste!", cleaned, flags=re.IGNORECASE)
            
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            
            # If LLM asked callback question, mark as asked
            if any(w in cleaned.lower() for w in ["call back", "callback", "aapse connect"]):
                self.callback_asked = True

            # If LLM said goodbye / disconnect, mark for hangup
            should_hangup = any(w in cleaned.lower() for w in ["disconnect kar rahi hoon", "bye-bye", "have a wonderful day"])
            return cleaned, should_hangup

        except Exception as e:
            logger.error(f"Dialogue generation error: {e}")
            name_pref = f"{self.caller_name} ji" if self.caller_name else "ji"
            return f"Ji {name_pref}, main sun rahi hoon. Boliye Sachindra sir ke liye kya zaroori message hai?", False

# Global singleton
dialogue_engine = DialogueEngine()
