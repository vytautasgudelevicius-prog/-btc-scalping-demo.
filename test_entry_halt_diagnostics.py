"""Safety regression tests for research-only entry halts."""
import unittest
import bot

class EntryHaltTests(unittest.TestCase):
    def test_five_losses_halt_even_after_day_rollover(self):
        self.assertEqual(bot.entry_halt_reason(1000, 1000, [-1] * 5), "five_consecutive_losses")
        self.assertEqual(bot.entry_halt_reason(990, 990, [-1] * 5), "five_consecutive_losses")

    def test_four_losses_do_not_halt(self):
        self.assertIsNone(bot.entry_halt_reason(1000, 1000, [-1] * 4))

    def test_win_breaks_streak(self):
        self.assertIsNone(bot.entry_halt_reason(1000, 1000, [-1, -1, 1, -1, -1]))

    def test_two_percent_daily_loss_halts(self):
        self.assertEqual(bot.entry_halt_reason(980, 1000, []), "daily_loss_limit")
        self.assertIsNone(bot.entry_halt_reason(980.01, 1000, []))

    def test_invalid_daily_equity_fails_closed(self):
        self.assertEqual(bot.entry_halt_reason(1000, 0, []), "invalid_daily_equity")
        self.assertEqual(bot.entry_halt_reason(float("nan"), 1000, []), "invalid_daily_equity")

if __name__ == "__main__":
    unittest.main()
