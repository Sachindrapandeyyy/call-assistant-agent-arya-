import sqlite3, json, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect(r'C:\Users\Sachi\.gemini\antigravity\scratch\ai-call-assistant\data\calls.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute('SELECT * FROM call_sessions ORDER BY start_time DESC LIMIT 5')
rows = [dict(r) for r in c.fetchall()]
for r in rows:
    print('=' * 60)
    print(f"SESSION: {r.get('session_id')}")
    print(f"NUMBER: {r.get('caller_number')} | NAME: {r.get('caller_name')}")
    print(f"DURATION: {r.get('duration_sec')}s | START: {r.get('created_at')}")
    print(f"SUMMARY:\n{r.get('summary')}")
    print(f"TRANSCRIPT:\n{r.get('transcript')}")
