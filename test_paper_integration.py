"""Fail-closed integration checks for the existing paper trading entry path."""
import unittest
from unittest.mock import patch
import bot

class PaperIntegrationTests(unittest.TestCase):
    def test_unverified_model_cannot_open_paper_position(self):
        for direction in ("LONG","SHORT"):
            result=bot.research_entry_gate(direction,[[0,0,0,0,100,0,1]],
                equity=1000,bid=99.9,ask=100.1,day_start=1000,loss_count=0)
            self.assertEqual(result["decision"],"WAIT")
            self.assertEqual(result["reason"],"model_not_independently_validated")
    def test_empty_data_fails_closed(self):
        self.assertEqual(bot.research_entry_gate("LONG",[],1000,99,100,1000,0)["decision"],"WAIT")
    def test_gate_never_calls_exchange(self):
        with patch.object(bot,"api",side_effect=AssertionError("network call")):
            bot.research_entry_gate("LONG",[[0,0,0,0,100,0,1]],1000,99,100,1000,0)

if __name__=="__main__":unittest.main()
