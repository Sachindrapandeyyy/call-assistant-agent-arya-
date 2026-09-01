"""
Telegram Notification Delivery Engine for AI Call Assistant.
Sends structured call summaries, urgency alerts, and audio recordings
directly to Sachindra's Telegram at ₹0 cost.
"""

import json
import logging
import html
from pathlib import Path
from typing import Dict, Any, Optional
import httpx

from backend.config import settings

logger = logging.getLogger("TelegramNotifier")

class TelegramNotifier:
    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ):
        self._bot_token = bot_token
        self._chat_id = chat_id

    @property
    def bot_token(self) -> str:
        return self._bot_token or settings.TELEGRAM_BOT_TOKEN

    @property
    def chat_id(self) -> str:
        return self._chat_id or settings.TELEGRAM_CHAT_ID

    @property
    def base_url(self) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}"

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id and len(self.bot_token) > 10)

    def send_call_summary(
        self,
        caller_number: str,
        summary: Dict[str, Any],
        transcript: str,
        duration_sec: float = 0.0,
        audio_path: Optional[Path] = None,
    ) -> bool:
        """Sends a structured call summary card to Telegram with safe HTML entity escaping."""
        if not self.is_configured():
            logger.info("Telegram Bot token/chat_id not configured in .env. Skipping notification.")
            return False

        caller_name = html.escape(str(summary.get("caller_name", "Unknown")))
        caller_num = html.escape(str(caller_number))
        category = html.escape(str(summary.get("category", "General")))
        urgency = html.escape(str(summary.get("urgency", "Low")))
        reason = html.escape(str(summary.get("reason_for_call", "N/A")))
        message = html.escape(str(summary.get("message", "N/A")))
        callback = "Yes (Callback Requested)" if summary.get("callback_requested") else "No"
        action = html.escape(str(summary.get("follow_up_action_required", "None")))

        urgency_emoji = "🚨" if urgency in ["High", "Urgent"] else "📞"

        # Build clean, readable turn-by-turn dialogue transcript
        transcript_formatted = ""
        if transcript and len(transcript.strip()) > 5:
            lines = []
            for line in transcript.strip().split("\n"):
                if line.startswith("AI Assistant:"):
                    clean_line = line.replace("AI Assistant:", "").strip()
                    lines.append(f"🤖 <b>Arya:</b> {html.escape(clean_line)}")
                elif line.startswith("Caller:"):
                    clean_line = line.replace("Caller:", "").strip()
                    lines.append(f"👤 <b>Caller:</b> {html.escape(clean_line)}")
                else:
                    lines.append(html.escape(line))
            
            transcript_body = "\n".join(lines)
            transcript_formatted = (
                f"\n💬 <b>Full Conversation Transcript:</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"{transcript_body}\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            )

        summary_card = (
            f"{urgency_emoji} <b>AI CALL SUMMARY — Sachindra</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Caller:</b> {caller_name} ({caller_num})\n"
            f"🏷️ <b>Category:</b> {category}\n"
            f"⚡ <b>Urgency:</b> {urgency}\n"
            f"⏱️ <b>Duration:</b> {duration_sec:.1f}s\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 <b>Message:</b>\n{message}\n\n"
            f"🎯 <b>Action Required:</b> {action}\n"
            f"🔄 <b>Callback Needed:</b> {callback}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
        )

        full_message = summary_card + transcript_formatted

        try:
            with httpx.Client(timeout=15.0) as client:
                # 1. Send formatted text summary (with transcript)
                if len(full_message) <= 4000:
                    res = client.post(
                        f"{self.base_url}/sendMessage",
                        json={
                            "chat_id": self.chat_id,
                            "text": full_message,
                            "parse_mode": "HTML"
                        }
                    )
                    if res.status_code == 200:
                        logger.info(f"Sent call summary & transcript to Telegram chat {self.chat_id}")
                else:
                    # If conversation was very long (>4000 chars), send summary first then transcript
                    client.post(
                        f"{self.base_url}/sendMessage",
                        json={"chat_id": self.chat_id, "text": summary_card, "parse_mode": "HTML"}
                    )
                    for i in range(0, len(transcript_formatted), 3800):
                        chunk = transcript_formatted[i:i + 3800]
                        client.post(
                            f"{self.base_url}/sendMessage",
                            json={"chat_id": self.chat_id, "text": chunk, "parse_mode": "HTML"}
                        )
                    logger.info(f"Sent multi-part call summary & transcript to Telegram chat {self.chat_id}")

                # 2. Send audio recording file if available
                if audio_path and Path(audio_path).exists() and Path(audio_path).stat().st_size > 1024:
                    with open(str(audio_path), "rb") as f:
                        client.post(
                            f"{self.base_url}/sendAudio",
                            data={"chat_id": self.chat_id, "caption": f"🎙️ Call Recording: {caller_name} ({caller_number})"},
                            files={"audio": (audio_path.name, f, "audio/wav")}
                        )
                        logger.info(f"Sent audio recording {audio_path.name} to Telegram.")

                return True

        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False

# Global singleton
telegram_notifier = TelegramNotifier()
