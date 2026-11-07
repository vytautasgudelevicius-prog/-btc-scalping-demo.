"""Research backtest safety checks: no same-bar entry and fee sensitivity."""
import datetime as dt
import unittest
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

if __name__ == "__main__":
    unittest.main()
