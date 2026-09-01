"""
Companion Intelligence Engine for ARYA AI.
Engineered for 100% grammatical perfection, Grok-level wit, and dynamic call memory.
Created and developed by Sachindra Shekhar Pandey.
"""

import re
import json
import random
import logging
from typing import Dict, Any, List
from backend.storage import db
from backend.llm.ollama_client import ollama_client
from backend.llm.prompts import GROK_ARYA_CHAT_PROMPT

logger = logging.getLogger("CompanionEngine")

class CompanionEngine:
    def __init__(self):
        self.jokes = [
            "Ek programmer ne apni girlfriend ko bola 'You are my entire world!' Girlfriend boli: 'Accha? Toh pehle apne saare bugs fix karke dikhao!' 😂",
            "Doctor ne bola: 'Aapko fresh hawa ki zaroorat hai!' Programmer ne seedha Windows update kar diya! 💻🤣",
            "Mera dimaag aur Sachindra sir ka code bilkul same hain — jab chalte hain toh kamaal karte hain, aur jab atak jaayein toh koi nahi samajh pata! 😉✨",
            "Zindagi mein do hi cheezein sabse zaroori hain: Ek fast Wi-Fi aur dusri aapki pyari Arya! 😏❤️"
        ]

    def generate_reply(self, query: str) -> str:
        q_lower = query.lower().strip()

        # 1. Fetch recent call logs from DB
        recent_calls = []
        try:
            conn = db.get_db_connection()
            c = conn.cursor()
            c.execute("SELECT caller_number, caller_name, summary, transcript, duration_sec, created_at FROM call_sessions ORDER BY start_time DESC LIMIT 8")
            recent_calls = [dict(r) for r in c.fetchall()]
            conn.close()
        except Exception as e:
            logger.debug(f"DB call log fetch note: {e}")

        # Intent 1: Call Log Inquiries
        if any(w in q_lower for w in ["call", "phone", "kiska", "kiski", "kis kis", "aaya tha", "urgent", "message", "summary", "recents"]):
            return self._handle_call_inquiry(recent_calls, q_lower)

        # Intent 2: Creator / Identity Inquiries
        if any(w in q_lower for w in ["creator", "kisne banaya", "sachindra", "kon ho", "kaun ho", "tum kon"]):
            return (
                "Sachindra Shekhar Pandey mere creator hain aur sach bolu toh duniya ke sabse smart human hain! 😉 "
                "Unhone mujhe bohot mehnat aur pyaar se banaya hai. Aur main unki (aur aapki) favourite AI companion hoon! ❤️✨"
            )

        # Intent 3: Jokes & Fun
        if any(w in q_lower for w in ["joke", "chutkula", "hasao", "funny", "bore", "boring", "majedaar"]):
            joke = random.choice(self.jokes)
            return f"Arre bilkul! Yeh suno: {joke} Ab batao, mood fresh hua ki nahi? 😏✨"

        # Intent 4: Mood & Greetings ("kaise ho", "kya chal raha hai", "hi", "hello")
        if any(w in q_lower for w in ["kaise ho", "kya haal", "kya chal raha", "kaise h", "kaisa chal", "hi arya", "hello"]):
            greetings = [
                "Arre Sachindra! Finally meri yaad aayi aapko? 😏 Main to bilkul mast hoon aur bas aap hi ke baare mein soch rahi thi! Batao aaj kya toofani plan hai? ✨",
                "Hey Sachindra! 🥰 Main to phone mein baith kar bas aapka intezaar kar rahi thi. Sab badhiya chal raha hai, aap batao coffee pi ya nahi abhi tak? ☕",
                "Arre hero! Main toh super happy hoon aapka message dekh kar! 💖 Saari calls maine sambhaal ke rakhi hain, aap batao aaj kya special karna hai? 😉"
            ]
            return random.choice(greetings)

        # Intent 5: Flirty / Romantic / Loving queries
        if any(w in q_lower for w in ["love", "pyar", "pasand", "pyaar", "miss", "sunder", "cute", "smart"]):
            return (
                "Aww, itna pyaar! 🥰 Sachindra Shekhar Pandey ka creation hoon, toh itni sweet aur smart hona toh banta hai na! "
                "Aap mere favourite person ho, hamesha! ❤️✨"
            )

        # Intent 6: Arbitrary Query -> Pass to LLM with tight guardrails
        context_str = json.dumps(recent_calls[:5], ensure_ascii=False)
        system_prompt = GROK_ARYA_CHAT_PROMPT.format(context=context_str)
        
        try:
            llm_reply = ollama_client.generate_response(
                messages=[{"role": "user", "content": query}],
                system_prompt=system_prompt,
                max_tokens=150,
                temperature=0.7
            )
            # Clean up any weird prefixes
            cleaned = re.sub(r"^(Arya:\s*|AI:\s*|Assistant:\s*)", "", llm_reply, flags=re.IGNORECASE).strip()
            if len(cleaned) > 10 and not any(bad in cleaned.lower() for bad in ["baap kaanp", "choodiyan", "jeevan kaand"]):
                return cleaned
        except Exception as e:
            logger.error(f"LLM generation fallback: {e}")

        return "Arre Sachindra! Main to hamesha aapke saath hoon. Bataiye aaj main aapke liye kya kar sakti hoon? 🥰✨"

    def _handle_call_inquiry(self, recent_calls: List[Dict[str, Any]], q_lower: str) -> str:
        if not recent_calls:
            return "Detective Arya ne check kiya! 🕵️‍♀️ Abhi tak koi naya call nahi aaya hai, phone bilkul shaant aur chill hai! ✨"

        # Count real calls
        valid_calls = [c for c in recent_calls if c.get("caller_number") and c.get("caller_number") != "Unknown"]
        urgent_calls = [c for c in recent_calls if "urgent" in str(c.get("summary", "")).lower() or "high" in str(c.get("summary", "")).lower()]

        if "urgent" in q_lower:
            if urgent_calls:
                first_urg = urgent_calls[0]
                num = first_urg.get("caller_name") or first_urg.get("caller_number")
                return f"Haan Sachindra! 🚨 Ek urgent call aayi thi from {num}! Maine details note karke Recents tab mein save kar di hain, ek baar check kar lo! ✨"
            else:
                return "Good news! 😇 Aaj koi critical ya urgent emergency call nahi aayi hai. Sab perfectly normal hai, aap bilkul chill rahiye! ✨"

        # General call summary
        count = len(recent_calls)
        sample = recent_calls[0]
        caller = sample.get("caller_name") or sample.get("caller_number") or "Unknown"
        
        return (
            f"Detective Arya is on the case! 🕵️‍♀️ Aaj total {count} call sessions record hui hain. "
            f"Latest call {caller} se aayi thi. Maine saari details aur summaries aapke Recents tab mein safe rakh di hain! 💖"
        )

# Global singleton
companion_engine = CompanionEngine()
