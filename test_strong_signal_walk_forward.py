import unittest
from research.strong_signal_walk_forward import run

class StrongSignalWalkForwardTests(unittest.TestCase):
    def test_insufficient_history_fails_closed(self):
        with self.assertRaises(ValueError):
            run([])
    def test_negative_costs_rejected(self):
        with self.assertRaises(ValueError):
            run([],spread_bps=-1)
    def test_invalid_folds_rejected(self):
        with self.assertRaises(ValueError):
            run([],folds=0)

if __name__=="__main__":
    unittest.main()
