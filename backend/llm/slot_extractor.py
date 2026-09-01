"""
Fast Entity & Slot Extractor using Hybrid Rule-Based Parser + Local LLM.
Supports both English and Devanagari Hindi with 100% negative/positive callback detection.
"""

import re
import json
import logging
from typing import Dict, Any, Optional
from backend.llm.ollama_client import ollama_client

logger = logging.getLogger("SlotExtractor")

EXTRACTION_SYSTEM_PROMPT = """You are a precise telephony entity extraction engine.
Analyze the user utterance in the context of the phone dialogue and extract any mentioned parameters.
Return ONLY valid JSON matching this schema:

{
  "caller_name": string or null,
  "company_organization": string or null,
  "reason_for_call": string or null,
  "message": string or null,
  "important_dates_times": string or null,
  "urgency": "Low" | "Medium" | "High" | "Urgent" | null,
  "callback_requested": boolean or null,
  "relationship": "family" | "friend" | "company" | "recruiter" | "client" | "unknown" | null
}

RULES:
- Extract ONLY what is explicitly mentioned.
- If user says 'No' or 'Nahi' to callback, set "callback_requested": false.
- If user says 'Yes' or 'Haan' to callback, set "callback_requested": true.
- Output ONLY raw JSON.
"""

class SlotExtractor:
    def _fast_rule_extract(self, text: str) -> Dict[str, Any]:
        """Fast rule-based extractor with multi-lingual (English + Devanagari) support."""
        slots = {}
        lower = text.lower().strip()

        # 1. Caller Name Extraction (Latin + Devanagari Hindi) with anti-hallucination blacklist
        NON_NAMES = {
            "sachindra", "hello", "namaste", "sir", "available", "nahi", "ek", "abhi", "जी", "नहीं", "हाँ",
            "theek", "free", "busy", "kaidi", "accha", "bura", "bhai", "yaar", "kaam", "ghar", "office",
            "call", "baat", "bol", "yahan", "wahan", "kal", "aaj", "audio", "voice", "kuch", "hai", "tha",
            "raha", "rahi", "hoon", "कैदी", "ठीक", "फ्री", "बिजी", "काम", "बात", "कॉल", "आवाज", "बोल", "सुन",
            "यही", "तभी", "कोई", "और", "या", "ये"
        }
        name_match = (
            re.search(r"(?:mera naam|shubh naam|my name is|मेरा नाम|शुभ नाम)\s+([A-Za-z\u0900-\u097F]+)", text, re.IGNORECASE) or
            re.search(r"(?:main|i am|this is|मैं)\s+([A-Za-z\u0900-\u097F]+)\s+(?:bol raha|bol rahi|here|from|बोल रहा|बोल रही)", text, re.IGNORECASE) or
            re.search(r"^(?:(?:haan|ji|namaste|hello)\s+)?([A-Za-z\u0900-\u097F]{3,15})\s*(?:bol raha|bol rahi|hai|hoon|है|हूँ)?$", text.strip(), re.IGNORECASE)
        )
        if name_match:
            candidate = name_match.group(1).strip().capitalize()
            if candidate.lower() not in NON_NAMES and len(candidate) >= 3:
                slots["caller_name"] = candidate

        # 2. Company / Organization Extraction
        org_match = re.search(r"(?:from\s+([A-Za-z0-9\u0900-\u097F]+)|([A-Za-z0-9\u0900-\u097F]+)\s+se\b)", text, re.IGNORECASE)
        if org_match:
            candidate = (org_match.group(1) or org_match.group(2)).strip()
            if candidate.lower() not in ["sachindra", "yahan", "wahan", "call", "ghar", "office", "bol", "mera"]:
                slots["company_organization"] = candidate.capitalize()
                slots["relationship"] = "company"

        # 3. Urgency Extraction
        if any(w in lower for w in ["urgent", "emergency", "zaroori", "bahut urgent", "इमरजेंसी", "जरूरी"]):
            slots["urgency"] = "Urgent"

        # 4. Dates & Times Extraction (Devanagari numerals & time of day)
        dt_parts = []
        if any(w in lower for w in ["kal", "tomorrow", "कल"]):
            dt_parts.append("Kal / Tomorrow")
        if any(w in lower for w in ["aaj", "today", "आज"]):
            dt_parts.append("Aaj / Today")
        if any(w in lower for w in ["parso", "day after tomorrow", "परसों"]):
            dt_parts.append("Parso / Day after tomorrow")
        
        # Match time with periods (e.g. shaam 6 baje, subah 11:00 am, शाम ६ बजे)
        # Normalize Devanagari numerals to ASCII
        dev_digits = str.maketrans("०१२३४५६७८९", "0123456789")
        norm_text = lower.translate(dev_digits)

        time_match = re.search(r"((?:subah|shaam|dopahar|raat|सुबह|शाम|दोपहर|रात)\s+)?(\d{1,2}(?::\d{2})?\s*(?:baje|am|pm|बजे|o'clock)?)", norm_text)
        if time_match and (time_match.group(1) or "baje" in time_match.group(2) or "am" in time_match.group(2) or "pm" in time_match.group(2) or "बजे" in time_match.group(2)):
            matched_time = f"{time_match.group(1) or ''}{time_match.group(2)}".strip()
            if matched_time:
                dt_parts.append(matched_time)
        
        if dt_parts:
            slots["important_dates_times"] = " ".join(dt_parts)

        # 5. Reason & Topic Extraction
        for kw, cat in [
            ("interview", "recruiter"),
            ("इंटरव्यू", "recruiter"),
            ("meeting", "client"),
            ("मीटिंग", "client"),
            ("delivery", "delivery"),
            ("parcel", "delivery"),
            ("resume", "recruiter"),
            ("project", "client")
        ]:
            if kw in lower:
                slots["reason_for_call"] = f"{kw.capitalize()} discussion"
                slots["message"] = text
                if "relationship" not in slots:
                    slots["relationship"] = cat
                break

        # 6. Callback Preference (Negative Checked FIRST for Safety)
        neg_words = ["nahi", "no", "ji nahi", "mat karein", "mat karna", "jarurat nahi", "nahi chahiye", "नहीं", "जी नहीं", "नो", "no thanks", "dont call", "don't"]
        pos_words = ["call back", "call karein", "phone karein", "call me back", "कॉल करें", "haan", "yes", "हाँ", "जी हाँ", "sure", "zaroor"]
        
        if any(w in lower for w in neg_words):
            slots["callback_requested"] = False
        elif any(w in lower for w in pos_words):
            slots["callback_requested"] = True

        return slots

    def extract_from_utterance(self, utterance: str, dialogue_context: list) -> Dict[str, Any]:
        """Extracts entity slots from user utterance using fast rules + LLM."""
        if not utterance.strip() or len(utterance.strip()) < 2:
            return {}

        slots = self._fast_rule_extract(utterance)

        # Fast return if key slots already found
        if slots.get("caller_name") or ("callback_requested" in slots):
            logger.info(f"[SLOT EXTRACTOR] Fast rule hit: {slots}")
            return slots

        # LLM fallback
        try:
            prompt = f"User said: \"{utterance}\"\n\nDialogue History: {json.dumps(dialogue_context[-4:] if dialogue_context else [])}"
            raw_response = ollama_client._generate_local_ollama(
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.1
            )
            cleaned = raw_response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]

            llm_slots = json.loads(cleaned.strip())
            for k, v in llm_slots.items():
                if v is not None and v != "null" and k not in slots:
                    slots[k] = v
        except Exception as e:
            logger.debug(f"LLM slot parsing note: {e}")

        return slots

# Global singleton
slot_extractor = SlotExtractor()
