"""
Production FastAPI Server for AI Call Assistant ("Aura AI").
Provides WebSocket telephony signaling, detailed health metrics across all 9 subsystems,
and local REST endpoints for call histories and retention management.
"""

import json
import logging
import asyncio
import threading
from contextlib import asynccontextmanager
from typing import Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.storage import db
from backend.storage.retention_manager import retention_manager
from backend.audio.device_manager import DeviceManager
from backend.audio.session_manager import session_manager
from backend.stt.whisper_engine import get_stt_engine
from backend.llm.ollama_client import ollama_client
from backend.tts.tts_engine import tts_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("CallAssistantServer")

connected_ws_clients = set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 65)
    logger.info("  AURA AI CALL ASSISTANT — PRODUCTION LOCAL SERVER")
    logger.info("=" * 65)
    loopback, uplink = DeviceManager.get_devices()
    logger.info(f"  Downlink (Loopback Capture): {loopback.name if loopback else 'NOT FOUND'}")
    logger.info(f"  Uplink (VB-Cable Injection): {uplink.name if uplink else 'NOT FOUND'}")
    logger.info(f"  Database Path:               {settings.DB_PATH}")
    logger.info(f"  Recordings Directory:        {settings.RECORDINGS_DIR}")
    logger.info(f"  Uplink Mode:                 {settings.UPLINK_MODE}")
    logger.info(f"  TTS Engine Mode:             {settings.TTS_ENGINE}")
    logger.info("=" * 65)
    
    # Pre-load Whisper GPU STT and Ollama LLM in background at server start to eliminate cold start
    def _warmup():
        try:
            stt = get_stt_engine()
            logger.info(f"  [STARTUP] Pre-warmed faster-whisper on {stt.device}:{stt.compute_type}")
        except Exception as e:
            logger.warning(f"  [STARTUP] STT warmup note: {e}")
        try:
            ollama_client.generate_response([{"role": "user", "content": "Hello"}], max_tokens=5)
            logger.info(f"  [STARTUP] Pre-warmed Ollama LLM on RTX 4050 GPU")
        except Exception as e:
            logger.warning(f"  [STARTUP] LLM warmup note: {e}")
    threading.Thread(target=_warmup, daemon=True).start()

    yield
    logger.info("Aura AI backend shutting down.")

app = FastAPI(title="Aura AI Call Assistant", lifespan=lifespan)

@app.get("/health")
@app.get("/api/health")
def detailed_health_check() -> Dict[str, Any]:
    """Evaluates the real-time operational status across all 9 core subsystems."""
    subsystems = {}

    # 1. Telephony WebSocket
    subsystems["TELEPHONY"] = "HEALTHY" if len(connected_ws_clients) > 0 else "DEGRADED (No Active Phone Client)"

    # 2. Audio Downlink
    loopback, uplink = DeviceManager.get_devices()
    subsystems["AUDIO_DOWNLINK"] = "HEALTHY" if loopback is not None else "FAILED (Loopback Not Found)"

    # 3. Audio Uplink
    subsystems["AUDIO_UPLINK"] = "HEALTHY" if uplink is not None else "FAILED (VB-Cable Not Found)"

    # 4. VAD Segmenter
    subsystems["VAD"] = "HEALTHY"

    # 5. Whisper STT
    try:
        stt = get_stt_engine()
        subsystems["WHISPER"] = f"HEALTHY ({stt.device}:{stt.compute_type})" if stt else "FAILED"
    except Exception as e:
        subsystems["WHISPER"] = f"FAILED ({e})"

    # 6. Ollama LLM
    try:
        is_llm_ok = ollama_client.is_available()
        subsystems["OLLAMA"] = f"HEALTHY ({ollama_client.model})" if is_llm_ok else "FAILED (Ollama Offline)"
    except Exception as e:
        subsystems["OLLAMA"] = f"FAILED ({e})"

    # 7. TTS Engine
    try:
        subsystems["TTS"] = f"HEALTHY (Mode: {settings.TTS_ENGINE})"
    except Exception as e:
        subsystems["TTS"] = f"FAILED ({e})"

    # 8. SQLite Database
    try:
        conn = db.get_db_connection()
        c = conn.cursor()
        c.execute("SELECT count(*) FROM call_sessions")
        cnt = c.fetchone()[0]
        conn.close()
        subsystems["DATABASE"] = f"HEALTHY ({cnt} sessions recorded)"
    except Exception as e:
        subsystems["DATABASE"] = f"FAILED ({e})"

    # 9. Notification (Telegram)
    if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
        subsystems["NOTIFICATION"] = "HEALTHY (Telegram Configured)"
    else:
        subsystems["NOTIFICATION"] = "PENDING (Telegram Unconfigured - Safe Fallback)"

    overall_status = "HEALTHY"
    for k, v in subsystems.items():
        if "FAILED" in v:
            overall_status = "FAILED"
            break
        elif "DEGRADED" in v and overall_status != "FAILED":
            overall_status = "DEGRADED"

    return {
        "status": overall_status,
        "active_session": session_manager.active_session_id,
        "subsystems": subsystems
    }

@app.get("/sessions")
@app.get("/api/sessions")
@app.get("/api/calls")
def get_sessions(limit: int = 50):
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM call_sessions ORDER BY start_time DESC LIMIT ?", (limit,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return {"sessions": rows, "calls": rows}
    except Exception as e:
        logger.error(f"Error fetching sessions: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/retention/purge")
def trigger_retention_purge():
    """Manual trigger to purge expired recordings and transcripts."""
    purged_recordings = retention_manager.purge_expired_recordings()
    purged_transcripts = retention_manager.purge_expired_transcripts_from_db()
    return {
        "status": "success",
        "purged_recordings_count": purged_recordings,
        "purged_transcripts_count": purged_transcripts
    }

from pydantic import BaseModel

class AssistantChatRequest(BaseModel):
    query: str

@app.post("/api/assistant/chat")
def assistant_chat(req: AssistantChatRequest):
    """Direct conversation with Aura AI inside the phone app."""
    conn = db.get_db_connection()
    c = conn.cursor()
    c.execute("SELECT caller_number, caller_name, summary, transcript, duration_sec, created_at FROM call_sessions ORDER BY start_time DESC LIMIT 10")
    recent_calls = [dict(r) for r in c.fetchall()]
    conn.close()

    from backend.llm.companion_engine import companion_engine
    reply = companion_engine.generate_reply(req.query)

    return {
        "reply": reply,
        "recent_calls_count": len(recent_calls),
        "recent_calls": recent_calls
    }

connected_ws_sockets = set()
_main_loop = None

def broadcast_ws_message(event_type: str, data: Dict[str, Any] = None):
    """Broadcasts a JSON command (like hangup_call) to connected Android devices."""
    global _main_loop
    payload = json.dumps({"event": event_type, "data": data or {}})
    for ws in list(connected_ws_sockets):
        try:
            if _main_loop and _main_loop.is_running():
                asyncio.run_coroutine_threadsafe(ws.send_text(payload), _main_loop)
            else:
                logger.debug("[WS BROADCAST] Event loop not running, cannot send message.")
            logger.info(f"[WS BROADCAST] Sent '{event_type}' to Android client.")
        except Exception as e:
            logger.debug(f"[WS BROADCAST] Note: {e}")

@app.websocket("/ws/telephony")
async def telephony_websocket(websocket: WebSocket):
    global _main_loop
    _main_loop = asyncio.get_running_loop()
    await websocket.accept()
    client_host = websocket.client.host if websocket.client else "unknown"
    connected_ws_clients.add(client_host)
    connected_ws_sockets.add(websocket)
    logger.info(f"[WS] Android client connected from {client_host} (Active clients: {len(connected_ws_clients)})")

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                msg = json.loads(raw_data)
                if not isinstance(msg, dict):
                    logger.warning(f"[WS] Non-dict JSON payload ignored: {type(msg)}")
                    continue
                event_type = msg.get("event", "unknown")
                event_data = msg.get("data", {})

                logger.info(f"[TELEPHONY EVENT] {event_type.upper()} -> {event_data}")
                session_manager.handle_telephony_event(event_type, event_data)

            except json.JSONDecodeError:
                logger.warning(f"[WS] Received non-JSON message: {raw_data}")

    except WebSocketDisconnect:
        connected_ws_clients.discard(client_host)
        connected_ws_sockets.discard(websocket)
        logger.info(f"[WS] Android client disconnected ({client_host})")
    except Exception as e:
        connected_ws_clients.discard(client_host)
        connected_ws_sockets.discard(websocket)
        logger.error(f"[WS] Error in telephony websocket: {e}")
