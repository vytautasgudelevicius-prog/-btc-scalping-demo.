import unittest
import pandas as pd
from research.filter_diagnostics import funnel


class FunnelTests(unittest.TestCase):
    def test_close_boundary_and_missing_execution_bar(self):
        d = pd.DataFrame(dict(timestamp=[0, 60, 180, 240], signal=[1]*4,
            regime=[1]*4, continuous=[True]*4, range=[.03]*4,
            trend=[.01]*4, atr=[.001]*4, volume_ratio=[1.]*4))
        result = funnel(d, 60, 240)
        self.assertEqual(result['crossovers'], 2)
        self.assertEqual(result['continuous_data'], 1)
        self.assertEqual(result['volume'], 1)


if __name__ == '__main__':
    unittest.main()
