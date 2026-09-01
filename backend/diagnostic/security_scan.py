import os, re, sys
sys.stdout.reconfigure(encoding='utf-8')

print('=' * 65)
print('PRE-COMMIT SECURITY & SECRETS SCAN')
print('=' * 65)

root = os.path.abspath('.')
disallowed_patterns = [
    (re.compile(r'\b\d{8,10}:[A-Za-z0-9_-]{35}\b'), 'Telegram Bot Token'),
    (re.compile(r'\bsk-[a-zA-Z0-9]{32,}\b'), 'OpenAI API Secret Key'),
    (re.compile(r'\bgsk_[a-zA-Z0-9]{32,}\b'), 'Groq API Secret Key'),
]

files_with_issues = []
ignored_exts = {'.wav', '.db', '.pyc', '.class', '.apk', '.jar', '.png', '.jpg', '.zip'}

for dirpath, dirnames, filenames in os.walk(root):
    if any(x in dirpath for x in ['.git', '.gradle', 'build', '__pycache__', 'recordings', '.jdk']):
        continue
    for f in filenames:
        ext = os.path.splitext(f)[1].lower()
        if ext in ignored_exts or f == '.env':
            continue
        filepath = os.path.join(dirpath, f)
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as fp:
                content = fp.read()
                for pattern, name in disallowed_patterns:
                    if pattern.search(content):
                        files_with_issues.append((filepath, name))
        except Exception:
            pass

if files_with_issues:
    print('SECURITY ALERT: Secrets detected in tracked files:')
    for fp, issue in files_with_issues:
        print(f'  - {fp}: {issue}')
else:
    print('PASSED: Zero secrets, API keys, or Bot Tokens found in source code!')
print('=' * 65)
