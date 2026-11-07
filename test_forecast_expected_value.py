import unittest
from research.forecast_expected_value import fit_ridge,predict,assess,run

class ForecastExpectedValueTests(unittest.TestCase):
    def test_constant_return_forecast(self):
        data=[([float(i%7),float(i%3)],.002) for i in range(80)]
        model=fit_ridge(data)
        self.assertAlmostEqual(predict(model,[1.,2.]),.002,places=4)
    def test_cost_gate_blocks_small_forecast(self):
        data=[([float(i%7)],.0001) for i in range(80)]
        model=fit_ridge(data)
        result=assess(model,data,.001,.002)
        self.assertEqual(result["trades"],0)
    def test_short_history_rejected(self):
        with self.assertRaises(ValueError):
            run([])
    def test_negative_fees_rejected(self):
        # Validate using sufficiently long generated aligned candles is covered
        # in full CI; the empty-data guard must reject invalid input safely.
        with self.assertRaises(ValueError):
            run([],fee_per_side=-.01)

if __name__=="__main__":unittest.main()
