"""BTC/EUR paper-trading experiment. Public Kraken data only. NEVER sends orders."""
import datetime as dt
import json
import logging
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
MAX_GROSS_EXPOSURE = 0.30

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
    minimum_range = 2 * (FEE + SLIP) + 0.005
    trend = close[-1] / close[-61] - 1
    trend_ok = trend >= 0.004 if direction == "LONG" else trend <= -0.004
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
    db.execute("INSERT OR IGNORE INTO state VALUES (1, ?, 0, 0, 0, '', ?, 0, 0, 0)", (INITIAL, INITIAL))
    # One-time migration of a legacy open position; retain cash and trade history.
    legacy = db.execute("SELECT btc,entry,opened FROM state WHERE id=1").fetchone()
    if legacy[0] != 0:
        db.execute("INSERT INTO positions(btc,entry,opened) VALUES (?,?,?)", legacy)
        db.execute("UPDATE state SET btc=0,entry=0,opened=0 WHERE id=1")
    db.commit()

def positions(db):
    return db.execute("SELECT id,btc,entry,opened FROM positions ORDER BY id").fetchall()

def portfolio_equity(cash, items, bid, ask):
    return marked_equity(cash, sum(p[1] for p in items), bid, ask)

def trade(db, side, amount, price, fee, reason, equity):
    db.execute("INSERT INTO trades VALUES (?,?,?,?,?,?,?)", (dt.datetime.now(dt.timezone.utc).isoformat(), side, amount, price, fee, reason, equity))

def run():
    import pathlib
    pathlib.Path(DB).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB, timeout=30)
    init(db)
    log.info("PAPER ONLY started, database=%s, max_positions=%d", DB, MAX_OPEN)
    while True:
        try:
            now = int(time.time())
            result = api("OHLC", {"pair": PAIR, "interval": 1})
            key = next(k for k in result if k != "last")
            candles = result[key][:-1]
            if len(candles) < 90 or now - int(candles[-1][0]) > 180:
                log.warning("Stale/insufficient candles; no trading")
                time.sleep(15)
                continue
            tick = api("Ticker", {"pair": PAIR})
            ticker = next(iter(tick.values()))
            ask, bid = float(ticker["a"][0]), float(ticker["b"][0])
            if ask <= 0 or bid <= 0 or (ask - bid) / ask > 0.0015:
                log.warning("Spread too wide; skip")
                time.sleep(15)
                continue
            cash, day, day_start, buys, last_buy, last_candle = db.execute(
                "SELECT cash,day,day_start,buys,last_buy,last_candle FROM state WHERE id=1"
            ).fetchone()
            items = positions(db)
            today = dt.datetime.now(dt.timezone.utc).date().isoformat()
            if today != day:
                day, day_start, buys = today, portfolio_equity(cash, items, bid, ask), 0
            closed_any = False
            for pos_id, amount, entry, opened in items:
                reason = None
                if amount > 0:
                    if bid <= entry * (1 - 0.012): reason = "stop_loss"
                    elif bid >= entry * (1 + 0.03): reason = "take_profit"
                    elif now - opened >= 45 * 60: reason = "time_limit"
                    if reason:
                        price = bid * (1 - SLIP)
                        proceeds = amount * price
                        fee = proceeds * FEE
                        cash += proceeds - fee
                        side, quantity = "SELL_LONG", amount
                else:
                    if ask >= entry * (1 + 0.012): reason = "stop_loss"
                    elif ask <= entry * (1 - 0.03): reason = "take_profit"
                    elif now - opened >= 45 * 60: reason = "time_limit"
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
                    log.info("PAPER CLOSE position=%d side=%s reason=%s equity=%.2f", pos_id, side, reason, equity)
                    closed_any = True
            items = positions(db)
            candle_time = int(candles[-1][0])
            equity = portfolio_equity(cash, items, bid, ask)
            daily_ok = equity >= day_start * 0.97
            gross = sum(abs(p[1]) * (ask if p[1] < 0 else bid) for p in items)
            if (not closed_any and daily_ok and len(items) < MAX_OPEN and buys < 8
                    and now - last_buy >= 900 and candle_time != last_candle):
                direction = signal(candles)
                if direction != "WAIT":
                    regime = market_regime()
                    if (direction == "LONG" and regime != "BULL") or (direction == "SHORT" and regime != "BEAR"):
                        log.info("PAPER entry blocked by market regime=%s signal=%s", regime, direction)
                        direction = "WAIT"
                # Do not hold opposing long and short positions simultaneously.
                if items and ((direction == "LONG" and items[0][1] < 0)
                              or (direction == "SHORT" and items[0][1] > 0)):
                    direction = "WAIT"
                budget = min(max(0, equity) * 0.10,
                             max(0, equity * MAX_GROSS_EXPOSURE - gross),
                             max(0, cash) * 0.10)
                if (direction in ("LONG", "SHORT") and budget > 5
                        and entry_quality(candles, direction)
                        and liquidity_and_atr_ok(candles)):
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
                    db.execute("INSERT INTO positions(btc,entry,opened) VALUES (?,?,?)", (amount, price, now))
                    buys += 1
                    last_buy = now
                    items = positions(db)
                    trade(db, side, abs(amount), price, fee, "ema9_21", portfolio_equity(cash, items, bid, ask))
                    log.info("PAPER OPEN %s %.8f BTC @ %.2f positions=%d", direction, abs(amount), price, len(items))
            last_candle = candle_time
            db.execute("UPDATE state SET cash=?,day=?,day_start=?,buys=?,last_buy=?,last_candle=? WHERE id=1",
                       (cash, day, day_start, buys, last_buy, last_candle))
            db.commit()
            items = positions(db)
            log.info("PAPER status equity=%.2f cash=%.2f positions=%d btc=%.8f entries_today=%d",
                     portfolio_equity(cash, items, bid, ask), cash, len(items), sum(p[1] for p in items), buys)
        except Exception:
            log.exception("Cycle failed; retrying; NO live orders")
            db.rollback()
        time.sleep(15)

if __name__ == "__main__":
    run()
