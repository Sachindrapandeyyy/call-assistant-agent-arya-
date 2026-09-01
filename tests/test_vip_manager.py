"""
VIP Contacts and Custom Greetings Test Suite.
"""

import sys
import unittest
from pathlib import Path

# Force UTF-8 encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agent.vip_manager import vip_manager
from backend.agent.state_machine import ConversationStateMachine

class TestVIPManager(unittest.TestCase):

    def test_vip_recognition_and_greeting(self):
        """Verify VIP contact phone number normalization and custom greeting."""
        # Test Papa number (+919876543210 or 9876543210 or +91 98765 43210)
        info = vip_manager.get_vip_info("+91 98765 43210")
        self.assertIsNotNone(info)
        self.assertEqual(info["name"], "Papa")
        self.assertEqual(info["category"], "family")
        
        # Test State Machine with Papa's incoming call
        sm = ConversationStateMachine()
        sm.start_call("vip_session_test", "+91 98765 43210")
        
        self.assertEqual(sm.slots.caller_name, "Papa")
        self.assertEqual(sm.slots.relationship, "family")
        self.assertEqual(sm.slots.urgency, "High")
        
        greeting = sm.get_initial_greeting()
        self.assertIn("Pranam Papa ji", greeting)
        print(f"\n[VIP TEST] Personalized Greeting for Papa: \"{greeting}\" -> PASS")

    def test_unknown_caller_fallback(self):
        """Verify non-VIP caller gets standard formal greeting."""
        sm = ConversationStateMachine()
        sm.start_call("standard_session_test", "+91 11111 22222")
        
        greeting = sm.get_initial_greeting()
        self.assertIn("Sachindra ki personal assistant", greeting)
        print(f"\n[VIP TEST] Standard Greeting for Unknown: \"{greeting}\" -> PASS")

if __name__ == "__main__":
    unittest.main()
