"""Research backtest safety checks: no same-bar entry and fee sensitivity."""
import datetime as dt
import unittest
from unittest.mock import patch
from research.backtest_candles import simulate

UTC = dt.timezone.utc


def flat_rows(count=400):
    origin = dt.datetime(2026, 1, 1, tzinfo=UTC)
    return [(origin + dt.timedelta(minutes=i), 100., 100.1, 99.9, 100., 1.) for i in range(count)]


class BacktestSafetyTests(unittest.TestCase):
    def test_flat_market_does_not_trade(self):
        result = simulate(flat_rows(), 180)
        self.assertEqual(result["trades"], 0)
        self.assertEqual(result["net_pnl_eur"], 0.)

    def test_no_data_in_holdout_yields_no_trades(self):
        rows = flat_rows()
        result = simulate(rows, len(rows))
        self.assertEqual(result["trades"], 0)

    def test_fee_parameters_do_not_create_flat_market_profit(self):
        rows = flat_rows()
        for fee in (.0, .004, .008):
            for spread in (0, 5, 15):
                self.assertEqual(simulate(rows, 180, fee, spread)["net_pnl_eur"], 0.)

    def test_gap_through_stop_is_not_filled_at_favorable_stop(self):
        rows = flat_rows(400)
        # First qualifying signal at minute 184 enters at minute 185 open.
        # Gap through the long stop at minute 186 must worsen realized P&L.
        for i in range(185, 400):
            rows[i] = (rows[i][0], 100., 100.1, 99.9, 100., 1.)
        rows[186] = (rows[186][0], 90., 91., 89., 90., 1.)
        rows[187] = (rows[187][0], 90., 91., 89., 90., 1.)
        def signal(_):
            return {"signal": "LONG", "reason": "test"}
        with patch("research.backtest_candles.research_signal", side_effect=signal):
            gap = simulate(rows[:188], 180)
        # Gap must cause loss worse than a 1.2% stop plus trading costs.
        self.assertLess(gap["net_pnl_eur"], -2.5)

if __name__ == "__main__":
    unittest.main()
