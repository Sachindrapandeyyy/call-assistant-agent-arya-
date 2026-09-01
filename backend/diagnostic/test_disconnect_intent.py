import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')

from backend.agent.dialogue_engine import dialogue_engine

test_phrases = [
    'मैं चाहता हूं की आप ये कोल कट कर दें.',
    'आप कोल दिसकनेख कर सकती हैं?',
    'call disconnect kar do',
    'ok bye bye',
    'kaat do phone'
]

print('=' * 60)
print('DISCONNECT PHRASE RECOGNITION TEST')
print('=' * 60)

for p in test_phrases:
    dialogue_engine.reset('+919876543210')
    reply, should_hangup = dialogue_engine.process_turn(p, [{'role': 'user', 'content': p}])
    print(f'Caller: \"{p}\"')
    print(f'  Hangup Decision: {should_hangup} | Reply: \"{reply}\"')
