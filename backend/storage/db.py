"""
Production SQLite Database Engine for AI Call Assistant.
Features transactional updates, foreign keys, schema migrations, and processing status state tracking.
"""

import json
import sqlite3
import datetime
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from backend.config import settings

logger = logging.getLogger("Database")

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(settings.DB_PATH), timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Initializes tables, indexes, and migrates missing columns."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Call Sessions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS call_sessions (
        session_id TEXT PRIMARY KEY,
        caller_number TEXT NOT NULL,
        caller_name TEXT,
        state TEXT NOT NULL,
        processing_status TEXT DEFAULT 'RECEIVED',
        start_time REAL NOT NULL,
        answered_time REAL,
        end_time REAL,
        duration_sec REAL DEFAULT 0.0,
        recording_path TEXT,
        summary TEXT,
        transcript TEXT,
        error_message TEXT,
        retries_count INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """)

    # Check and add columns for existing databases
    cursor.execute("PRAGMA table_info(call_sessions)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    for col, col_type in [
        ("summary", "TEXT"),
        ("transcript", "TEXT"),
        ("processing_status", "TEXT DEFAULT 'RECEIVED'"),
        ("error_message", "TEXT"),
        ("retries_count", "INTEGER DEFAULT 0")
    ]:
        if col not in existing_cols:
            try:
                cursor.execute(f"ALTER TABLE call_sessions ADD COLUMN {col} {col_type}")
            except Exception as e:
                logger.debug(f"Migration note for column {col}: {e}")

    # 2. Telephony Events Log Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS telephony_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        event_type TEXT NOT NULL,
        event_data TEXT,
        timestamp REAL NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(session_id) REFERENCES call_sessions(session_id) ON DELETE CASCADE
    )
    """)

    # 3. Speech Segments Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS speech_segments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        segment_index INTEGER NOT NULL,
        start_offset_sec REAL NOT NULL,
        end_offset_sec REAL NOT NULL,
        duration_sec REAL NOT NULL,
        audio_file_path TEXT NOT NULL,
        transcript TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(session_id) REFERENCES call_sessions(session_id) ON DELETE CASCADE
    )
    """)

    # 4. Performance Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON call_sessions(start_time DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_session_id ON telephony_events(session_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_segments_session_id ON speech_segments(session_id)")

    conn.commit()
    conn.close()

def create_call_session(session_id: str, caller_number: str, caller_name: Optional[str] = None) -> Dict[str, Any]:
    """Atomically creates a new call session record in RECEIVED state."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    now_ts = datetime.datetime.now().timestamp()

    try:
        cursor.execute("""
        INSERT INTO call_sessions (session_id, caller_number, caller_name, state, processing_status, start_time, created_at)
        VALUES (?, ?, ?, 'RINGING', 'RECEIVED', ?, ?)
        """, (session_id, caller_number, caller_name, now_ts, now_iso))
        conn.commit()
        return {"session_id": session_id, "caller_number": caller_number, "state": "RINGING"}
    except Exception as e:
        conn.rollback()
        logger.error(f"Error creating call session: {e}")
        raise e
    finally:
        conn.close()

def update_session_state(session_id: str, state: str, **kwargs):
    """Atomically updates call session state, summary, and processing status."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now_ts = datetime.datetime.now().timestamp()

    if state == "ACTIVE" and "answered_time" not in kwargs:
        kwargs["answered_time"] = now_ts
        kwargs["processing_status"] = "PROCESSING"
    elif state in ("ENDED", "DISCONNECTED") and "end_time" not in kwargs:
        kwargs["end_time"] = now_ts
        if "processing_status" not in kwargs:
            kwargs["processing_status"] = "COMPLETED"

    set_clauses = ["state = ?"]
    values = [state]

    for k, v in kwargs.items():
        set_clauses.append(f"{k} = ?")
        values.append(v)

    values.append(session_id)
    query = f"UPDATE call_sessions SET {', '.join(set_clauses)} WHERE session_id = ?"

    try:
        cursor.execute(query, values)
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating session state for {session_id}: {e}")
    finally:
        conn.close()

def log_telephony_event(session_id: Optional[str], event_type: str, event_data: str):
    """Atomically logs telephony event."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    now_ts = datetime.datetime.now().timestamp()

    try:
        cursor.execute("""
        INSERT INTO telephony_events (session_id, event_type, event_data, timestamp, created_at)
        VALUES (?, ?, ?, ?, ?)
        """, (session_id, event_type, event_data, now_ts, now_iso))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error logging telephony event: {e}")
    finally:
        conn.close()

def record_speech_segment(session_id: str, index: int, start_offset: float, end_offset: float, audio_path: str):
    """Atomically records a VAD speech segment."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    duration = end_offset - start_offset

    try:
        cursor.execute("""
        INSERT INTO speech_segments (session_id, segment_index, start_offset_sec, end_offset_sec, duration_sec, audio_file_path, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (session_id, index, start_offset, end_offset, duration, str(audio_path), now_iso))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error recording speech segment: {e}")
    finally:
        conn.close()

# Auto-initialize database
init_db()
