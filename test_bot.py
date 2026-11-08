"""Exercise the real paper loop against a temporary database and mocked market."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bot


class ExitGuardTests(unittest.TestCase):
    NOW = 1_800_000_000

    def cycle(self, *, direction=1, stale=False, wide=False, outage=False,
              invalid=None, position=True, stop=False):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "paper.sqlite3")
            db = sqlite3.connect(path)
            bot.init(db)
            if position:
                opened = self.NOW - (10 if stop else bot.MAX_HOLD_SECONDS + 1)
                db.execute(
                    "INSERT INTO positions(btc,entry,opened,entry_fee,entry_side) "
                    "VALUES (?,?,?,?,?)",
                    (direction, 100, opened, .8, "BUY_LONG" if direction > 0 else "SELL_SHORT"))
                db.execute("UPDATE state SET cash=? WHERE id=1",
                           (899.2 if direction > 0 else 1099.2,))
                db.commit()
            db.close()
            bid, ask = ((98, 102) if wide or stop else (100, 100.01))
            if invalid:
                bid, ask = invalid
            candles = [[self.NOW - (10000 if stale else 60) - (100-i)*60,
                        100, 101, 99, 100, 100, 1, 1] for i in range(102)]

            def market(endpoint, params):
                if endpoint == "OHLC":
                    if outage:
                        raise OSError("mock candle outage")
                    return {"XXBTZEUR": candles, "last": 1}
                return {"XXBTZEUR": {"a": [str(ask)], "b": [str(bid)]}}

            with patch.object(bot, "DB", path), patch.object(bot, "api", side_effect=market), \
                 patch.object(bot.time, "time", return_value=self.NOW), \
                 patch.object(bot.time, "sleep", side_effect=SystemExit), \
                 patch.object(bot, "signal", return_value="LONG"), \
                 patch.object(bot, "market_regime", return_value="BULL"):
                with self.assertRaises(SystemExit):
                    bot.run()
            db = sqlite3.connect(path)
            closed = db.execute("SELECT reason,net_pnl FROM closed_positions").fetchall()
            remaining = db.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
            cash = db.execute("SELECT cash FROM state").fetchone()[0]
            db.close()
            return closed, remaining, cash

    def test_time_exit_survives_stale_candles_and_outage(self):
        for direction in (1, -1):
            for problem in ({"stale": True}, {"outage": True}):
                with self.subTest(direction=direction, problem=problem):
                    closed, remaining, cash = self.cycle(direction=direction, **problem)
                    self.assertEqual(remaining, 0)
                    self.assertEqual(closed[0][0], "time_limit")
                    self.assertLess(closed[0][1], 0)
                    self.assertAlmostEqual(cash - bot.INITIAL, closed[0][1])

    def test_stop_exit_survives_wide_spread(self):
        for direction in (1, -1):
            with self.subTest(direction=direction):
                closed, remaining, cash = self.cycle(direction=direction, wide=True, stop=True)
                self.assertEqual(remaining, 0)
                self.assertEqual(closed[0][0], "stop_loss")
                self.assertAlmostEqual(cash - bot.INITIAL, closed[0][1])

    def test_entry_guards_still_block_new_positions(self):
        for problem in ({"stale": True}, {"outage": True}, {"wide": True}):
            with self.subTest(problem=problem):
                closed, remaining, cash = self.cycle(position=False, **problem)
                self.assertEqual((closed, remaining, cash), ([], 0, bot.INITIAL))

    def test_invalid_quotes_cannot_create_fills(self):
        for quote in ((101, 100), (0, 100), (100, float("nan")), (100, float("inf"))):
            with self.subTest(quote=quote):
                closed, remaining, _ = self.cycle(invalid=quote)
                self.assertEqual((closed, remaining), ([], 1))

    def test_unvalidated_research_gate_blocks_entry_even_with_healthy_quotes(self):
        # The legacy paper loop deliberately refuses new entries until
        # independent research validation. The separate isolated DEMO
        # experiment has its own entry logic and is tested separately.
        closed, remaining, cash = self.cycle(position=False)
        self.assertEqual((closed, remaining), ([], 0))
        self.assertEqual(cash, bot.INITIAL)


if __name__ == "__main__":
    unittest.main()
