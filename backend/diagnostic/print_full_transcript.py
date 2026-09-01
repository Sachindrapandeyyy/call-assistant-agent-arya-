import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect(r'C:\Users\Sachi\.gemini\antigravity\scratch\ai-call-assistant\data\calls.db')
c = conn.cursor()
c.execute('SELECT transcript FROM call_sessions WHERE session_id = ?', ('call_20260901_222824_9482a1',))
row = c.fetchone()
if row and row[0]:
    print('=' * 75)
    print('FULL TRANSCRIPT (35 TURNS):')
    print('=' * 75)
    for i, line in enumerate(row[0].split('\n')):
        print(f'{i+1:02d}: {line}')
