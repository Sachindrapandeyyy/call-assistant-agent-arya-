import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding='utf-8')

from backend.agent.vip_manager import vip_manager
from backend.llm.slot_extractor import slot_extractor
from backend.notifications.telegram_notifier import telegram_notifier

print('=' * 60)
print('COMPREHENSIVE SUBSYSTEM VERIFICATION')
print('=' * 60)

# 1. Phone normalization test
n1 = vip_manager._normalize_phone("+91 94784 37479")
n2 = vip_manager._normalize_phone("09478437479")
n3 = vip_manager._normalize_phone("9478437479")
print(f"Phone Normalization (+91 / 0 / raw): {n1} == {n2} == {n3} -> {n1 == n2 == n3}")

# 2. Devanagari numerals & date extraction test
text1 = "कल शाम ६ बजे इंटरव्यू है"
text2 = "parso subah 10:30 am meeting hai"
s1 = slot_extractor._fast_rule_extract(text1)
s2 = slot_extractor._fast_rule_extract(text2)
print(f"Devanagari Time Extraction: {s1.get('important_dates_times')}")
print(f"Hinglish Time Extraction:   {s2.get('important_dates_times')}")

# 3. HTML Escaped Telegram Test
test_sum = {'caller_name': 'A < B & Company', 'urgency': 'Low', 'message': 'Code: <script>alert("hello")</script> & 5 > 2', 'callback_requested': False}
res = telegram_notifier.send_call_summary("+91 94784 37479", test_sum, "Transcript <safe>")
print(f"Telegram HTML Escaping Dispatch: {res}")
