"""Deterministic tests for the research-only directional learner."""
import datetime as dt
import unittest
from research.train_direction import examples, fit, predict, run, score

UTC = dt.timezone.utc

def candles(n=3000):
    origin = dt.datetime(2026, 1, 1, tzinfo=UTC)
    rows = []
    for i in range(n):
        o = 100 + i * .001
        c = o + (.02 if (i//5)%2 else -.02)
        rows.append((origin + dt.timedelta(minutes=i), o, max(o,c)+.03,
                     min(o,c)-.03, c, 1 + i%7))
    return rows

class DirectionLearningTests(unittest.TestCase):
    def test_features_do_not_see_future(self):
        rows = candles(500)
        before = examples(rows)
        altered = list(rows)
        last = altered[-1]
        altered[-1] = (last[0], last[1], last[2]+100, last[3], last[4], last[5])
        after = examples(altered)
        self.assertEqual(before[:-1], after[:-1])

    def test_training_only_standardization(self):
        model = fit([([0., 1.], 0), ([2., 3.], 1)], epochs=2)
        self.assertEqual(model["mean"], [1., 2.])
        self.assertTrue(0 <= predict(model, [100., 100.]) <= 1)

    def test_score_wait_when_threshold_high(self):
        model = {"weights":[0.], "bias":0., "mean":[0.], "std":[1.]}
        result = score(model, [([0.],1), ([0.],0)], .75)
        self.assertEqual(result["signals"], 0)
        self.assertIsNone(result["accuracy_pct"])

    def test_run_reports_untouched_test(self):
        result = run(candles())
        self.assertGreater(result["training_samples"], 0)
        self.assertGreater(result["test"]["samples"], 0)
        self.assertIn("majority_baseline_pct", result["test"])

if __name__ == "__main__":
    unittest.main()
