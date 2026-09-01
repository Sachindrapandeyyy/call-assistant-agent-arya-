import sys, os, json
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')

from backend.agent.dialogue_engine import dialogue_engine
from backend.llm.slot_extractor import slot_extractor
from backend.llm.ollama_client import ollama_client
from backend.agent.state_machine import ConversationStateMachine

dialogue_engine.reset('+919478437479')
sm = ConversationStateMachine()
sm.start_call('test_audit_sess', '+919478437479')

turns = [
    'Kal shaam 6 baje meeting ke liye milna hai',
    'Yes callback chahiye',
    'Aur koi baat nahi hai call disconnect kar do'
]

history = []
for t in turns:
    print('=' * 60)
    print('CALLER:', t)
    slots = slot_extractor._fast_rule_extract(t)
    sm.apply_extracted_entities(slots)
    history.append({'role': 'user', 'content': t})
    reply, should_hangup = dialogue_engine.process_turn(t, history)
    history.append({'role': 'assistant', 'content': reply})
    print(f'AI: \"{reply}\" | Hangup: {should_hangup}')

print('=' * 60)
print('FINAL STATE MACHINE SLOTS:', json.dumps(sm.slots.__dict__, indent=2, default=str))

# Summary test
transcript_str = '\n'.join([f"{h['role']}: {h['content']}" for h in history])
summary = ollama_client.generate_summary(transcript_str)
print('GENERATED SUMMARY JSON:\n', json.dumps(summary, indent=2))
