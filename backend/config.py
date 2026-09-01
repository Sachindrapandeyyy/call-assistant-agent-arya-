"""
Production Configuration Settings for AI Personal Call Assistant ("Aura AI").
All timing, models, devices, safety thresholds, and retention policies are managed here.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    # --- Server Settings ---
    HOST: str = "127.0.0.1"  # Localhost binding for privacy/security
    PORT: int = 8000
    
    # --- Telephony & Timing ---
    ANSWER_DELAY_SECONDS: float = 4.0
    MAX_CALL_DURATION_SECONDS: float = 300.0  # 5 minutes safety timeout
    MAX_CLARIFICATION_ATTEMPTS: int = 2
    MAX_SILENCE_ATTEMPTS: int = 2
    
    # --- Audio Engine ---
    AUDIO_SAMPLE_RATE: int = 16000
    PLAYBACK_SAMPLE_RATE: int = 48000
    VAD_THRESHOLD: float = 0.035  # Tuned to filter room ambient noise on Realtek speakers
    SILENCE_TIMEOUT: float = 0.85  # Seconds of silence to trigger end-of-turn
    MIN_SPEECH_DURATION: float = 0.45  # Minimum speech duration to accept
    BARGE_IN_THRESHOLD: float = 0.015
    UPLINK_MODE: str = "dual"  # 'dual', 'vb_cable', or 'direct_bluetooth'
    
    # --- Storage & Retention ---
    RECORDING_ENABLED: bool = True
    RECORDING_RETENTION_DAYS: int = 30
    TRANSCRIPT_RETENTION_DAYS: int = 60
    RECORDINGS_DIR: Path = BASE_DIR / "recordings"
    DATA_DIR: Path = BASE_DIR / "data"
    DB_PATH: Path = BASE_DIR / "data" / "calls.db"
    
    # --- Local AI Models ---
    # faster-whisper STT
    STT_MODEL_SIZE: str = "small"   # 'small', 'base', or 'large-v3-turbo'
    STT_DEVICE: str = "cuda"        # 'cuda' (RTX 4050 GPU) with automatic CPU fallback
    STT_COMPUTE_TYPE: str = "int8"   # 'int8' or 'float16'
    
    # Ollama LLM
    OLLAMA_HOST: str = "http://127.0.0.1:11434"
    LLM_MODEL: str = "llama3.2:latest"
    
    # Cloud Hybrid LLM (Zero Latency Groq Option)
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    
    # TTS Engine
    TTS_ENGINE: str = "local"        # 'local' (100% offline SAPI) or 'edge' (online SwaraNeural)
    EDGE_VOICE: str = "hi-IN-SwaraNeural"  # Natural female Indian voice
    
    # --- Assistant Persona ---
    USER_NAME: str = "Sachindra Shekhar Pandey"
    USER_TITLE: str = "Sachindra sir"
    ASSISTANT_NAME: str = "Arya"
    
    # --- Notifications ---
    NOTIFICATION_ENABLED: bool = True
    TELEGRAM_ENABLED: bool = True
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    WHATSAPP_ENABLED: bool = False  # Explicitly marked Pending

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

# Ensure critical directories exist
settings.RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
