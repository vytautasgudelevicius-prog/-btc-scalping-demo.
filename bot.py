"""BTC/EUR paper-trading experiment. Public Kraken data only. NEVER sends orders."""
import datetime as dt
import json
import logging
import math
import os
import sqlite3
import time
from urllib.request import Request, urlopen

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("paper")
API = "https://api.kraken.com/0/public/"
DB = os.getenv("DB_PATH", "/data/paper.sqlite3")
PAIR = "XBTEUR"
INITIAL = 1000.0
FEE = 0.008
SLIP = 0.0002
MAX_OPEN = 3
MAX_DAILY_ENTRIES = 16  # experimental paper scalping ceiling, not a target
ENTRY_COOLDOWN_SECONDS = 300
MAX_HOLD_SECONDS = 15 * 60
MAX_GROSS_EXPOSURE = 0.30
MAX_DAILY_LOSS_FRACTION = 0.02  # match research risk curriculum; never auto-reset loss streak
# Kraken Pro base-tier taker fee (0.80% per side); marketable paper fills.
# The spread is represented by ask on entry/bid on exit (reverse for shorts).
# Simulated SHORT is hypothetical: spot Kraken trading does not offer uncollateralized shorts.


def api(endpoint, params):
    from urllib.parse import urlencode
    req = Request(API + endpoint + "?" + urlencode(params), headers={"User-Agent": "BTC-Paper-Demo/1.0"})
    with urlopen(req, timeout=20) as response:
        result = json.load(response)
    if result.get("error"):
        raise RuntimeError(str(result["error"]))
    return result["result"]

def ema(values, period):
    k = 2.0 / (period + 1)
    out = values[0]
    result = []
    for value in values:
        out = value * k + out * (1 - k)
        result.append(out)
    return result

def signal(candles):
    """Return LONG, SHORT or WAIT from completed-candle EMA crossover."""
    if len(candles) < 30:
        return "WAIT"
    close = [float(c[4]) for c in candles]
    fast, slow = ema(close, 9), ema(close, 21)
    if fast[-2] <= slow[-2] and fast[-1] > slow[-1]:
        return "LONG"
    if fast[-2] >= slow[-2] and fast[-1] < slow[-1]:
        return "SHORT"
    return "WAIT"

def entry_quality(candles, direction):
    """Conservative volatility/trend filter, NOT a profit prediction."""
    if direction == "WAIT" or len(candles) < 90:
        return False
    close = [float(x[4]) for x in candles]
    high = max(float(x[2]) for x in candles[-60:])
    low = min(float(x[3]) for x in candles[-60:])
    if low <= 0:
        return False
    hourly_range = high / low - 1
    # Round-trip fee+slippage alone costs ~1.64% before spread.
    # Require substantially more observed movement before risking a new entry.
    minimum_range = 2 * (FEE + SLIP) + 0.002
    trend = close[-1] / close[-61] - 1
    trend_ok = trend >= 0.002 if direction == "LONG" else trend <= -0.002
    return hourly_range >= minimum_range and trend_ok

def liquidity_and_atr_ok(candles):
    """Require meaningful activity and bounded volatility on completed 1m bars."""
    if len(candles) < 65:
        return False
    recent = candles[-60:]
    highs = [float(x[2]) for x in recent]
    lows = [float(x[3]) for x in recent]
    closes = [float(x[4]) for x in recent]
    volumes = [float(x[6]) for x in recent]
    if min(lows) <= 0 or closes[-1] <= 0:
        return False
    true_ranges = [max(highs[i] - lows[i],
                       abs(highs[i] - closes[i-1]),
                       abs(lows[i] - closes[i-1])) for i in range(1, len(recent))]
    atr_pct = (sum(true_ranges[-14:]) / 14) / closes[-1]
    avg_volume = sum(volumes[-31:-1]) / 30
    # Avoid dead markets and extreme one-minute volatility.
    return (0.0002 <= atr_pct <= 0.015
            and avg_volume > 0
            and volumes[-1] >= 0.5 * avg_volume)


def market_regime():
    """Classify broad BTC trend using completed 4h Kraken candles.

    Conservative by design: insufficient/stale/ambiguous data => SIDEWAYS.
    This is a risk gate, not a prediction of future price direction.
    """
    series = []
    for interval, max_age in ((240, 8 * 3600),):
        data = api("OHLC", {"pair": PAIR, "interval": interval})
        key = next(k for k in data if k != "last")
        candles = data[key][:-1]
        if len(candles) < 210 or int(time.time()) - int(candles[-1][0]) > max_age:
            return "SIDEWAYS"
        closes = [float(x[4]) for x in candles]
        e50 = ema(closes, 50)[-1]
        e200 = ema(closes, 200)[-1]
        last = closes[-1]
        if e50 <= 0 or e200 <= 0:
            return "SIDEWAYS"
        series.append("BULL" if last > e50 > e200 * 1.005
                      else "BEAR" if last < e50 < e200 * 0.995
                      else "SIDEWAYS")
    return series[0] if series else "SIDEWAYS"


def marked_equity(cash, btc, bid, ask):
    """Conservative close-out valuation including simulated taker fee/slippage."""
    if btc > 0:
        return cash + btc * bid * (1 - FEE - SLIP)
    if btc < 0:
        return cash + btc * ask * (1 + FEE + SLIP)
    return cash

def init(db):
    db.execute("CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), cash REAL, btc REAL, entry REAL, opened INTEGER, day TEXT, day_start REAL, buys INTEGER, last_buy INTEGER, last_candle INTEGER)")
    db.execute("CREATE TABLE IF NOT EXISTS trades (timestamp TEXT, side TEXT, btc REAL, price REAL, fee REAL, reason TEXT, equity REAL)")
    db.execute("CREATE TABLE IF NOT EXISTS positions (id INTEGER PRIMARY KEY AUTOINCREMENT, btc REAL NOT NULL, entry REAL NOT NULL, opened INTEGER NOT NULL)")
    # Existing positions from older releases are preserved; historical entry fees
    # cannot be inferred reliably, so they remain NULL and are not fabricated.
    columns = {row[1] for row in db.execute("PRAGMA table_info(positions)")}
    if "entry_fee" not in columns:
        db.execute("ALTER TABLE positions ADD COLUMN entry_fee REAL")
    if "entry_side" not in columns:
        db.execute("ALTER TABLE positions ADD COLUMN entry_side TEXT")
    db.execute("""CREATE TABLE IF NOT EXISTS closed_positions (
        position_id INTEGER PRIMARY KEY, opened INTEGER NOT NULL,
        closed TEXT NOT NULL, direction TEXT NOT NULL, btc REAL NOT NULL,
        entry_price REAL NOT NULL, exit_price REAL NOT NULL,
        entry_fee REAL, exit_fee REAL NOT NULL,
        net_pnl REAL, reason TEXT NOT NULL, equity REAL NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS equity_history (
        timestamp TEXT PRIMARY KEY, equity REAL NOT NULL)""")
    db.execute("INSERT OR IGNORE INTO state VALUES (1, ?, 0, 0, 0, '', ?, 0, 0, 0)", (INITIAL, INITIAL))
    # One-time migration of a legacy open position; retain cash and trade history.
    legacy = db.execute("SELECT btc,entry,opened FROM state WHERE id=1").fetchone()
    if legacy[0] != 0:
        db.execute("INSERT INTO positions(btc,entry,opened) VALUES (?,?,?)", legacy)
        db.execute("UPDATE state SET btc=0,entry=0,opened=0 WHERE id=1")
    db.commit()

def positions(db):
    return db.execute("SELECT id,btc,entry,opened,entry_fee,entry_side FROM positions ORDER BY id").fetchall()

def portfolio_equity(cash, items, bid, ask):
    return marked_equity(cash, sum(p[1] for p in items), bid, ask)

def trade_statistics(db, current_equity):
    """Realized PnL only when both entry and exit costs are known."""
    rows = db.execute("SELECT net_pnl FROM closed_positions WHERE net_pnl IS NOT NULL").fetchall()
    wins = [r[0] for r in rows if r[0] > 0]
    losses = [r[0] for r in rows if r[0] < 0]
    # Drawdown includes conservative marked-to-close equity observations.
    samples = [INITIAL] + [r[0] for r in db.execute(
        "SELECT equity FROM equity_history ORDER BY timestamp")] + [current_equity]
    peak = samples[0]
    max_dd = 0.0
    for value in samples:
        peak = max(peak, value)
        if peak > 0:
            max_dd = max(max_dd, (peak - value) / peak * 100)
    return {"closed": len(rows), "wins": len(wins), "losses": len(losses),
            "win_rate": 100 * len(wins) / len(rows) if rows else 0.0,
            "avg_win": sum(wins) / len(wins) if wins else 0.0,
            "avg_loss": sum(losses) / len(losses) if losses else 0.0,
            "net_pnl": sum(r[0] for r in rows), "max_dd": max_dd,
            "unknown": db.execute("SELECT COUNT(*) FROM closed_positions WHERE net_pnl IS NULL").fetchone()[0]}


def trade(db, side, amount, price, fee, reason, equity):
    db.execute("INSERT INTO trades VALUES (?,?,?,?,?,?,?)", (dt.datetime.now(dt.timezone.utc).isoformat(), side, amount, price, fee, reason, equity))

def research_entry_gate(direction, candles, equity, bid, ask, day_start, loss_count):
    """Research model is not validated for deployment: reject new entries.

    Preserves legacy position exit processing. Never infer authorization from a
    green CI check or a profitable-looking historical result.
    """
    from research.paper_promotion_gate import paper_candidate
    if direction not in ("LONG", "SHORT") or not candles:
        return {"decision": "WAIT", "reason": "no_direction_or_candles"}
    entry = ask * (1 + SLIP) if direction == "LONG" else bid * (1 - SLIP)
    stop = entry * (0.988 if direction == "LONG" else 1.012)
    target = entry * (1.03 if direction == "LONG" else .97)
    # No independently verified live forecast or walk-forward promotion yet.
    return paper_candidate(
        forecast_return=0.0, expected_price=entry, entry=entry,
        equity=equity, stop=stop, target=target,
        validated=False, walk_forward_passed=False,
        day_start_equity=day_start, consecutive_losses=loss_count,
        fee_per_side=FEE, spread_bps=max(0.0, (ask-bid)/ask*10000),
        slippage_bps=SLIP*10000)


def run():
    import pathlib
    pathlib.Path(DB).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB, timeout=30)
    init(db)
    log.info("PAPER ONLY started, database=%s, max_positions=%d", DB, MAX_OPEN)
    while True:
        try:
            now = int(time.time())
            candles = []
            try:
                result = api("OHLC", {"pair": PAIR, "interval": 1})
                key = next(k for k in result if k != "last")
                candles = result[key][:-1]
                candles_ok = (len(candles) >= 90
                              and 0 <= now - int(candles[-1][0]) <= 180)
            except Exception:
                candles_ok = False
                log.warning("Candle data unavailable; entries disabled", exc_info=True)
            if not candles_ok:
                log.warning("Stale/insufficient candles; entries disabled, exits still checked")
            tick = api("Ticker", {"pair": PAIR})
            ticker = next(iter(tick.values()))
            ask, bid = float(ticker["a"][0]), float(ticker["b"][0])
            if not (math.isfinite(ask) and math.isfinite(bid) and ask >= bid > 0):
                log.warning("Invalid quote; cannot price paper fills")
                time.sleep(15)
                continue
            spread_ok = (ask - bid) / ask <= 0.0015
            if not spread_ok:
                log.warning("Spread too wide; entries disabled, exits still checked")
            cash, day, day_start, buys, last_buy, last_candle = db.execute(
                "SELECT cash,day,day_start,buys,last_buy,last_candle FROM state WHERE id=1"
            ).fetchone()
            items = positions(db)
            today = dt.datetime.now(dt.timezone.utc).date().isoformat()
            if today != day:
                day, day_start, buys = today, portfolio_equity(cash, items, bid, ask), 0
            closed_any = False
            for pos_id, amount, entry, opened, entry_fee, entry_side in items:
                reason = None
                if amount > 0:
                    if bid <= entry * (1 - 0.012): reason = "stop_loss"
                    elif bid >= entry * (1 + 0.03): reason = "take_profit"
                    elif now - opened >= MAX_HOLD_SECONDS: reason = "time_limit"
                    if reason:
                        price = bid * (1 - SLIP)
                        proceeds = amount * price
                        fee = proceeds * FEE
                        cash += proceeds - fee
                        side, quantity = "SELL_LONG", amount
                else:
                    if ask >= entry * (1 + 0.012): reason = "stop_loss"
                    elif ask <= entry * (1 - 0.03): reason = "take_profit"
                    elif now - opened >= MAX_HOLD_SECONDS: reason = "time_limit"
                    if reason:
                        price = ask * (1 + SLIP)
                        quantity = -amount
                        fee = quantity * price * FEE
                        cash -= quantity * price + fee
                        side = "BUY_TO_COVER"
                if reason:
                    db.execute("DELETE FROM positions WHERE id=?", (pos_id,))
                    remaining = positions(db)
                    equity = portfolio_equity(cash, remaining, bid, ask)
                    trade(db, side, quantity, price, fee, reason, equity)
                    # Entry and exit execution prices already include slippage.
                    # Entry/exit bid/ask already account for the observed spread.
                    pnl = ((price - entry) * quantity if amount > 0 else
                           (entry - price) * quantity)
                    net_pnl = pnl - entry_fee - fee if entry_fee is not None else None
                    closed_at = dt.datetime.now(dt.timezone.utc).isoformat()
                    db.execute("""INSERT INTO closed_positions
                        (position_id,opened,closed,direction,btc,entry_price,exit_price,
                         entry_fee,exit_fee,net_pnl,reason,equity)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (pos_id,opened,closed_at,"LONG" if amount > 0 else "SHORT",
                         quantity,entry,price,entry_fee,fee,net_pnl,reason,equity))
                    log.info("PAPER CLOSE position=%d side=%s reason=%s net_pnl=%s equity=%.2f",
                             pos_id, side, reason,
                             ("%.4f EUR" % net_pnl) if net_pnl is not None else "UNKNOWN_LEGACY", equity)
                    closed_any = True
            items = positions(db)
            candle_time = int(candles[-1][0]) if candles_ok else last_candle
            equity = portfolio_equity(cash, items, bid, ask)
            # Halt new entries after five consecutive losing closes, even across UTC days.
            recent_results = [r[0] for r in db.execute(
                "SELECT net_pnl FROM closed_positions WHERE net_pnl IS NOT NULL ORDER BY closed DESC LIMIT 5")]
            loss_streak_block = (len(recent_results) == 5 and all(pnl < 0 for pnl in recent_results))
            daily_ok = day_start > 0 and equity > day_start * (1 - MAX_DAILY_LOSS_FRACTION) and not loss_streak_block
            if loss_streak_block:
                log.info("PAPER SIGNAL REJECT reason=five_consecutive_losses")
                log.warning("PAPER ENTRY HALTED: five consecutive losses; exits remain active")
            elif day_start <= 0 or equity <= day_start * (1 - MAX_DAILY_LOSS_FRACTION):
                log.info("PAPER SIGNAL REJECT reason=daily_loss_limit_or_invalid_start")
                log.warning("PAPER ENTRY HALTED: UTC-day loss limit; exits remain active")
            gross = sum(abs(p[1]) * (ask if p[1] < 0 else bid) for p in items)
            if (candles_ok and spread_ok and not closed_any and daily_ok
                    and len(items) < MAX_OPEN and buys < MAX_DAILY_ENTRIES
                    and now - last_buy >= ENTRY_COOLDOWN_SECONDS and candle_time != last_candle):
                direction = signal(candles)
                if direction == "WAIT":
                    log.info("PAPER SIGNAL REJECT reason=no_ema_crossover candle=%s", candle_time)
                if direction != "WAIT":
                    try:
                        regime = market_regime()
                    except Exception:
                        # An entry-only data failure must not roll back this cycle's
                        # accounting, including any earlier position exits.
                        log.warning("Regime unavailable; entry disabled", exc_info=True)
                        regime, direction = "UNAVAILABLE", "WAIT"
                    if (direction == "LONG" and regime == "BEAR") or (direction == "SHORT" and regime == "BULL"):
                        log.info("PAPER entry blocked by market regime=%s signal=%s", regime, direction)
                        log.info("PAPER SIGNAL REJECT reason=market_regime_unavailable")
                        direction = "WAIT"
                # Do not hold opposing long and short positions simultaneously.
                if items and ((direction == "LONG" and items[0][1] < 0)
                              or (direction == "SHORT" and items[0][1] > 0)):
                    log.info("PAPER SIGNAL REJECT reason=opposing_open_position")
                    direction = "WAIT"
                budget = min(max(0, equity) * 0.10,
                             max(0, equity * MAX_GROSS_EXPOSURE - gross),
                             max(0, cash) * 0.10)
                if direction in ("LONG", "SHORT"):
                    # Research promotion is fail-closed until forward results and
                    # costs are independently verified. Do not bypass filters.
                    gate = research_entry_gate(direction, candles, equity, bid, ask,
                                               day_start, sum(pnl < 0 for pnl in recent_results))
                    if gate["decision"] != "PAPER_RESEARCH_CANDIDATE":
                        log.info("PAPER entry blocked by research gate: %s", gate["reason"])
                        log.info("PAPER SIGNAL REJECT reason=research_gate_%s", gate["reason"])
                        direction = "WAIT"
                    elif not entry_quality(candles, direction) or not liquidity_and_atr_ok(candles):
                        log.info("PAPER SIGNAL REJECT reason=quality_or_liquidity_gate")
                        direction = "WAIT"
                    if budget <= 5:
                        log.info("PAPER SIGNAL REJECT reason=insufficient_budget budget=%.2f", budget)
                if direction in ("LONG", "SHORT") and budget > 5:
                    if direction == "LONG":
                        price = ask * (1 + SLIP)
                        amount = budget / (price * (1 + FEE))
                        fee = amount * price * FEE
                        cash -= amount * price + fee
                        side = "BUY_LONG"
                    else:
                        price = bid * (1 - SLIP)
                        amount = -budget / price
                        fee = -amount * price * FEE
                        cash += -amount * price - fee
                        side = "SELL_SHORT"
                    db.execute("INSERT INTO positions(btc,entry,opened,entry_fee,entry_side) VALUES (?,?,?,?,?)", (amount, price, now, fee, side))
                    buys += 1
                    last_buy = now
                    items = positions(db)
                    trade(db, side, abs(amount), price, fee, "ema9_21", portfolio_equity(cash, items, bid, ask))
                    log.info("PAPER OPEN %s %.8f BTC @ %.2f positions=%d", direction, abs(amount), price, len(items))
            last_candle = candle_time
            db.execute("UPDATE state SET cash=?,day=?,day_start=?,buys=?,last_buy=?,last_candle=? WHERE id=1",
                       (cash, day, day_start, buys, last_buy, last_candle))
            # Store a timestamped equity sample for realized+unrealized drawdown.
            items = positions(db)
            equity_now = portfolio_equity(cash, items, bid, ask)
            stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:00Z")
            db.execute("INSERT OR REPLACE INTO equity_history(timestamp,equity) VALUES (?,?)",
                       (stamp, equity_now))
            db.commit()
            stats = trade_statistics(db, equity_now)
            log.info("PAPER STATS closed=%d wins=%d losses=%d win_rate=%.1f%% avg_win=%.4f avg_loss=%.4f net_pnl=%.4f max_drawdown=%.2f%% unknown_legacy=%d",
                     stats["closed"],stats["wins"],stats["losses"],stats["win_rate"],
                     stats["avg_win"],stats["avg_loss"],stats["net_pnl"],stats["max_dd"],stats["unknown"])
            log.info("PAPER status equity=%.2f cash=%.2f positions=%d btc=%.8f entries_today=%d",
                     portfolio_equity(cash, items, bid, ask), cash, len(items), sum(p[1] for p in items), buys)
        except Exception:
            log.exception("Cycle failed; retrying; NO live orders")
            db.rollback()
        time.sleep(15)

if __name__ == "__main__":
    run()
