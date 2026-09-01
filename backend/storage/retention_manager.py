"""
Local Data Retention and Privacy Manager for AI Call Assistant.
Manages scheduled cleanup of old recordings and transcripts according to user-configured retention policies.
"""

import time
import os
import shutil
import logging
from pathlib import Path
from backend.config import settings
from backend.storage import db

logger = logging.getLogger("RetentionManager")

class RetentionManager:
    def __init__(self, recording_days: int = settings.RECORDING_RETENTION_DAYS, transcript_days: int = settings.TRANSCRIPT_RETENTION_DAYS):
        self.recording_days = recording_days
        self.transcript_days = transcript_days

    def purge_expired_recordings(self, dry_run: bool = False) -> int:
        """Purges WAV audio files older than recording_days."""
        if not settings.RECORDINGS_DIR.exists():
            return 0

        cutoff_ts = time.time() - (self.recording_days * 86400)
        deleted_count = 0

        for session_dir in settings.RECORDINGS_DIR.iterdir():
            if session_dir.is_dir():
                try:
                    mtime = session_dir.stat().st_mtime
                    if mtime < cutoff_ts:
                        if not dry_run:
                            shutil.rmtree(str(session_dir), ignore_errors=True)
                        deleted_count += 1
                        logger.info(f"Purged expired recording directory: {session_dir.name}")
                except Exception as e:
                    logger.error(f"Error purging {session_dir}: {e}")

        return deleted_count

    def purge_expired_transcripts_from_db(self, dry_run: bool = False) -> int:
        """Nullifies transcripts in SQLite older than transcript_days."""
        cutoff_ts = time.time() - (self.transcript_days * 86400)
        conn = db.get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT count(*) FROM call_sessions WHERE start_time < ? AND transcript IS NOT NULL", (cutoff_ts,))
            count = cursor.fetchone()[0]

            if not dry_run and count > 0:
                cursor.execute("UPDATE call_sessions SET transcript = '[PURGED BY RETENTION POLICY]' WHERE start_time < ?", (cutoff_ts,))
                conn.commit()
                logger.info(f"Purged {count} expired transcripts from database.")
            return count
        except Exception as e:
            logger.error(f"Error purging transcripts: {e}")
            return 0
        finally:
            conn.close()

# Global singleton
retention_manager = RetentionManager()
