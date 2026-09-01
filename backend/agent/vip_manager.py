"""
VIP Contacts and Custom Greetings Manager for AI Call Assistant.
Provides personalized greetings, VIP categorization, and auto-urgency escalation.
"""

import json
import re
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from backend.config import settings

logger = logging.getLogger("VIPManager")

VIP_FILE_PATH = settings.DATA_DIR / "vip_contacts.json"

class VIPManager:
    def __init__(self, vip_file: Path = VIP_FILE_PATH):
        self.vip_file = vip_file
        self.vip_cache: Dict[str, Dict[str, Any]] = {}
        self.load_vip_contacts()

    def _normalize_phone(self, phone: str) -> str:
        """Removes spaces, hyphens, and standardizes to 10-digit or E.164."""
        cleaned = re.sub(r"[^\d+]", "", phone)
        if cleaned.startswith("+91") and len(cleaned) == 13:
            return cleaned[3:]
        elif cleaned.startswith("91") and len(cleaned) == 12:
            return cleaned[2:]
        elif cleaned.startswith("0") and len(cleaned) == 11:
            return cleaned[1:]
        return cleaned

    def load_vip_contacts(self):
        """Loads VIP contacts from JSON file."""
        if not self.vip_file.exists():
            self.vip_cache = {}
            return

        try:
            with open(self.vip_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                self.vip_cache = {}
                for num, meta in raw_data.items():
                    norm = self._normalize_phone(num)
                    self.vip_cache[norm] = meta
            logger.info(f"Loaded {len(self.vip_cache)} VIP contact rules.")
        except Exception as e:
            logger.error(f"Error loading VIP contacts: {e}")

    def get_vip_info(self, caller_number: str) -> Optional[Dict[str, Any]]:
        """Returns VIP metadata for a phone number if matched, otherwise None."""
        if not caller_number or caller_number == "Unknown":
            return None
        norm = self._normalize_phone(caller_number)
        return self.vip_cache.get(norm)

    def save_vip_contact(self, number: str, name: str, category: str, custom_greeting: str, urgency: str = "High"):
        """Adds or updates a VIP contact dynamically."""
        self.load_vip_contacts()
        norm = self._normalize_phone(number)
        
        # Read raw
        raw = {}
        if self.vip_file.exists():
            try:
                with open(self.vip_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
            except Exception:
                pass
        
        raw[number] = {
            "name": name,
            "category": category,
            "custom_greeting": custom_greeting,
            "urgency": urgency,
            "auto_alert": True
        }

        self.vip_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.vip_file, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2, ensure_ascii=False)

        self.load_vip_contacts()
        logger.info(f"Added VIP contact: {name} ({number})")

# Global singleton
vip_manager = VIPManager()
