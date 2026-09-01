import sys, os, time, json
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')

from backend.stt.whisper_engine import get_stt_engine
from backend.llm.ollama_client import ollama_client
from backend.agent.dialogue_engine import dialogue_engine
from backend.llm.slot_extractor import slot_extractor
from backend.agent.state_machine import ConversationStateMachine

stt = get_stt_engine()
ollama = ollama_client

scenarios = [
    ('TEST 1: Unknown caller + Hindi', 'नमस्ते, क्या सचिन्द्र जी से बात हो सकती है?', 'Unknown'),
    ('TEST 2: Known caller + Hindi', 'नमस्ते आर्या, मैं राहुल बोल रहा हूँ।', '+919876543210'),
    ('TEST 3: Hinglish', 'Hi Arya, Sachin sir available hain kya?', 'Unknown'),
    ('TEST 4: English', 'Hello, this is David from Google calling for Sachindra.', 'Unknown'),
    ('TEST 5: All Info in 1 Sentence', 'Hello main Rahul bol raha hoon Amazon se. Kal 10 baje interview ke regarding call kiya tha, callback kar dein.', 'Unknown'),
    ('TEST 6: Normal non-urgent', 'Kal sham ko chai pe milte hain Sachin bhai.', 'Unknown'),
    ('TEST 7: Urgent call', 'Emergency hai, server down ho gaya hai turant call back karein.', 'Unknown'),
    ('TEST 8: Caller interrupts AI', 'Haan suno ek minute...', 'Unknown'),
    ('TEST 9: Poor audio / short', 'a... um...', 'Unknown'),
    ('TEST 10: Silence', '', 'Unknown'),
    ('TEST 11: Fast-speaking caller', 'Main Vikram bol raha hoon TCS se project deliver ho gaya hai', 'Unknown'),
    ('TEST 12: Multiple pieces of info', 'Main Priya bol rahi hoon HR team se, kal subah 11 baje salary discussion hai, no callback needed.', 'Unknown')
]

print('=' * 75)
print('🚀 RUNNING 12-SCENARIO PRODUCTION VALIDATION MATRIX')
print('=' * 75)

for title, utterance, caller_num in scenarios:
    t0 = time.time()
    dialogue_engine.reset(caller_num)
    sm = ConversationStateMachine()
    sm.start_call('test_sess', caller_num)
    
    # Slot extraction
    slots = slot_extractor._fast_rule_extract(utterance) if utterance else {}
    sm.apply_extracted_entities(slots)
    
    # Turn decision
    history = []
    if utterance:
        history.append({'role': 'user', 'content': utterance})
    
    ai_reply, should_hangup = dialogue_engine.process_turn(utterance, history)
    lat = time.time() - t0
    
    print(f'\n{title}')
    print(f'  Caller: \"{utterance}\"')
    print(f'  Slots Extracted: {slots}')
    print(f'  AI Reply ({lat:.3f}s): \"{ai_reply}\"')
    print(f'  Hangup Decision: {should_hangup}')

