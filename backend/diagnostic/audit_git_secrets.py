import os, re, sys, subprocess
sys.stdout.reconfigure(encoding='utf-8')

print('=' * 70)
print('🛡️ FORENSIC REPOSITORY SECRETS & PRIVACY AUDIT')
print('=' * 70)

# 1. Check all tracked files in git
tracked_files = subprocess.check_output(['git', 'ls-files'], text=True).splitlines()

disallowed_patterns = [
    (re.compile(r'\b\d{8,10}:[A-Za-z0-9_-]{35}\b'), 'Telegram Bot Token'),
    (re.compile(r'\bsk-[a-zA-Z0-9]{32,}\b'), 'OpenAI API Secret Key'),
    (re.compile(r'\bgsk_[a-zA-Z0-9]{32,}\b'), 'Groq API Secret Key'),
    (re.compile(r'TELEGRAM_CHAT_ID\s*=\s*\d{8,}'), 'Hardcoded Telegram Chat ID'),
]

issues = []
for f in tracked_files:
    if os.path.exists(f):
        try:
            with open(f, 'r', encoding='utf-8', errors='ignore') as fp:
                content = fp.read()
                for pattern, name in disallowed_patterns:
                    if pattern.search(content):
                        issues.append((f, name))
        except Exception:
            pass

# 2. Check git log diffs for any accidentally committed secrets
git_diff_log = subprocess.check_output(['git', 'log', '-p'], text=True, errors='ignore')
for pattern, name in disallowed_patterns:
    matches = pattern.findall(git_diff_log)
    if matches:
        issues.append(('GIT_HISTORY', f'{name}: {matches}'))

if issues:
    print('⚠️ SECURITY ALERT: Issues found:')
    for item in issues:
        print(f'  - {item[0]}: {item[1]}')
else:
    print('✅ AUDIT PASSED: ZERO secrets, tokens, or private IDs found in tracked files or Git history!')

print('=' * 70)
