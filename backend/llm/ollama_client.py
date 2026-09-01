"""
Production Multi-Model Orchestration Engine for AI Call Assistant.
Supports:
1. Local Ollama on RTX 4050 GPU (llama3.2:3b / qwen2.5:3b) -> 0 Rate Limit, 0 Cost, 100% Privacy.
2. Cloud Groq API (llama-3.3-70b-versatile) -> 800 tokens/sec, sub-100ms TTFT.
3. Automatic Fallback: Seamlessly switches between Cloud and Local if network issues or rate limits occur.
Created and developed by Sachindra Shekhar Pandey.
"""

import time
import json
import logging
from typing import List, Dict, Optional, Any
import httpx

from backend.config import settings
from backend.llm.prompts import RECEPTIONIST_SYSTEM_PROMPT, SUMMARY_EXTRACTION_PROMPT

logger = logging.getLogger("LLMOrchestrator")

class HybridLLMClient:
    def __init__(
        self,
        ollama_host: str = settings.OLLAMA_HOST,
        local_model: str = settings.LLM_MODEL,
        groq_api_key: str = settings.GROQ_API_KEY,
        groq_model: str = settings.GROQ_MODEL,
    ):
        self.ollama_host = ollama_host.rstrip("/")
        self.local_model = local_model
        self.groq_api_key = groq_api_key.strip()
        self.groq_model = groq_model

        self.ollama_client = httpx.Client(base_url=self.ollama_host, timeout=15.0)
        self.groq_client = httpx.Client(base_url="https://api.groq.com/openai/v1", timeout=8.0)
        self._resolve_best_local_model()

    @property
    def model(self) -> str:
        return self.local_model

    def _resolve_best_local_model(self):
        """Auto-picks the fastest available model on RTX 4050."""
        try:
            r = self.ollama_client.get("/api/tags")
            if r.status_code == 200:
                models = [m.get("name") for m in r.json().get("models", [])]
                for preferred in ["llama3.2:latest", "llama3.2:3b", "qwen2.5:3b", "qwen2.5:latest"]:
                    for m in models:
                        if preferred in m:
                            self.local_model = m
                            logger.info(f"Resolved primary local model: '{self.local_model}'")
                            return
        except Exception as e:
            logger.debug(f"Local model check note: {e}")

    def is_available(self) -> bool:
        """Checks if local or cloud LLM is active."""
        if self.groq_api_key:
            return True
        try:
            r = self.ollama_client.get("/api/tags")
            return r.status_code == 200
        except Exception:
            return False

    def _generate_groq(self, system_prompt: str, messages: List[Dict[str, str]], max_tokens: int = 120, temperature: float = 0.5) -> Optional[str]:
        """Ultra-fast Cloud inference via Groq (800 tokens/sec)."""
        if not self.groq_api_key:
            return None
        try:
            full_msgs = [{"role": "system", "content": system_prompt}] + messages
            payload = {
                "model": self.groq_model,
                "messages": full_msgs,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": 0.9,
            }
            headers = {"Authorization": f"Bearer {self.groq_api_key}"}
            res = self.groq_client.post("/chat/completions", json=payload, headers=headers)
            if res.status_code == 200:
                data = res.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                logger.warning(f"Groq API returned HTTP {res.status_code}: {res.text}. Falling back to local GPU.")
                return None
        except Exception as e:
            logger.debug(f"Groq Cloud error: {e}. Falling back to local GPU.")
            return None

    def _generate_local_ollama(self, system_prompt: str, messages: List[Dict[str, str]], max_tokens: int = 120, temperature: float = 0.5) -> str:
        """Deterministic 0-rate-limit local GPU inference on RTX 4050."""
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        try:
            payload = {
                "model": self.local_model,
                "messages": full_messages,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                    "top_p": 0.9,
                    "repeat_penalty": 1.25,
                    "frequency_penalty": 0.35,
                    "presence_penalty": 0.25,
                    "stop": ["Caller:", "User:", "\n\n", "AI:"]
                }
            }
            res = self.ollama_client.post("/api/chat", json=payload)
            if res.status_code == 200:
                data = res.json()
                return data.get("message", {}).get("content", "").strip()
            else:
                logger.error(f"Local Ollama error {res.status_code}: {res.text}")
                return ""
        except Exception as e:
            logger.warning(f"Ollama request error: {e}")
            return ""

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        max_tokens: int = 120,
        temperature: float = 0.55,
    ) -> str:
        """Universal response generator with cloud-to-local zero-friction failover."""
        t0 = time.time()
        sys_prompt = system_prompt or RECEPTIONIST_SYSTEM_PROMPT
        recent_messages = messages[-6:] if len(messages) > 6 else messages

        # 1. Try Groq Cloud if configured
        reply = self._generate_groq(sys_prompt, recent_messages, max_tokens=max_tokens, temperature=temperature)

        # 2. Fallback to Local GPU Ollama (0 Rate Limit)
        if not reply:
            reply = self._generate_local_ollama(sys_prompt, recent_messages, max_tokens=max_tokens, temperature=temperature)

        # 3. Deterministic Safety Fallback if both unavailable
        if not reply or len(reply.strip()) < 3:
            reply = "Ji main sun rahi hoon. Sachindra sir ke liye aapka kya zaroori message hai?"

        latency = time.time() - t0
        logger.info(f"[LLM] Generated in {latency:.2f}s | Reply: '{reply}'")
        return reply

    def generate_summary(self, transcript_text: str) -> Dict[str, Any]:
        """Extracts structured JSON summary from transcript."""
        prompt = SUMMARY_EXTRACTION_PROMPT.replace("{transcript}", transcript_text)

        # Try Groq first
        if self.groq_api_key:
            try:
                res = self.groq_client.post(
                    "/chat/completions",
                    json={
                        "model": self.groq_model,
                        "messages": [
                            {"role": "system", "content": "You are a JSON extraction engine. Return ONLY valid JSON."},
                            {"role": "user", "content": prompt}
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.1
                    },
                    headers={"Authorization": f"Bearer {self.groq_api_key}"}
                )
                if res.status_code == 200:
                    return json.loads(res.json()["choices"][0]["message"]["content"])
            except Exception as e:
                logger.debug(f"Groq summary note: {e}")

        # Local Ollama fallback
        try:
            payload = {
                "model": self.local_model,
                "messages": [
                    {"role": "system", "content": "You are a JSON-only extraction engine. Always output valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.1, "num_predict": 350}
            }
            res = self.ollama_client.post("/api/chat", json=payload)
            if res.status_code == 200:
                return json.loads(res.json().get("message", {}).get("content", "{}"))
        except Exception as e:
            logger.error(f"Local summary generation error: {e}")

        return {
            "caller_name": "Unknown",
            "category": "General",
            "urgency": "Medium",
            "reason_for_call": "Message left on voicemail",
            "message": transcript_text[:200],
            "callback_requested": True
        }

# Global singleton
ollama_client = HybridLLMClient()
