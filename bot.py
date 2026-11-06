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
    minimum_range = 2 * (FEE + SLIP) + 0.015
    trend = close[-1] / close[-61] - 1
    trend_ok = trend >= 0.008 if direction == "LONG" else trend <= -0.008
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
    """Classify broad BTC trend using completed 4h and daily Kraken candles.

    Conservative by design: insufficient/stale/ambiguous data => SIDEWAYS.
    This is a risk gate, not a prediction of future price direction.
    """
    series = []
    for interval, max_age in ((240, 8 * 3600), (1440, 2 * 86400)):
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
    return series[0] if series[0] == series[1] else "SIDEWAYS"


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
    db.execute("INSERT OR IGNORE INTO state VALUES (1, ?, 0, 0, 0, '', ?, 0, 0, 0)", (INITIAL, INITIAL))
    db.commit()

def trade(db, side, amount, price, fee, reason, equity):
    db.execute("INSERT INTO trades VALUES (?,?,?,?,?,?,?)", (dt.datetime.now(dt.timezone.utc).isoformat(), side, amount, price, fee, reason, equity))

def run():
    import pathlib
    pathlib.Path(DB).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB, timeout=30)
    init(db)
    log.info("PAPER ONLY started, database=%s, initial balance=EUR %.2f", DB, INITIAL)
    while True:
        try:
            now = int(time.time())
            result = api("OHLC", {"pair": PAIR, "interval": 1})
            key = next(k for k in result if k != "last")
            candles = result[key][:-1]  # exclude still-forming minute
            if len(candles) < 30 or now - int(candles[-1][0]) > 180:
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
            cash, btc, entry, opened, day, day_start, buys, last_buy, last_candle = db.execute("SELECT cash,btc,entry,opened,day,day_start,buys,last_buy,last_candle FROM state WHERE id=1").fetchone()
            today = dt.datetime.now(dt.timezone.utc).date().isoformat()
            equity = marked_equity(cash, btc, bid, ask)
            if today != day:
                day, day_start, buys = today, equity, 0
            exit_reason = None
            if btc > 0:
                if bid <= entry * (1 - 0.012): exit_reason = "stop_loss"
                elif bid >= entry * (1 + 0.03): exit_reason = "take_profit"
                elif now - opened >= 45 * 60: exit_reason = "time_limit"
                if exit_reason:
                    price = bid * (1 - SLIP)
                    proceeds = btc * price
                    fee = proceeds * FEE
                    cash += proceeds - fee
                    trade(db, "SELL_LONG", btc, price, fee, exit_reason, cash)
                    log.info("PAPER CLOSE LONG reason=%s equity=%.2f", exit_reason, cash)
                    btc, entry, opened = 0, 0, 0
            elif btc < 0:
                if ask >= entry * (1 + 0.012): exit_reason = "stop_loss"
                elif ask <= entry * (1 - 0.03): exit_reason = "take_profit"
                elif now - opened >= 45 * 60: exit_reason = "time_limit"
                if exit_reason:
                    price = ask * (1 + SLIP)
                    cost = -btc * price
                    fee = cost * FEE
                    cash -= cost + fee
                    trade(db, "BUY_TO_COVER", -btc, price, fee, exit_reason, cash)
                    log.info("PAPER CLOSE SHORT reason=%s equity=%.2f", exit_reason, cash)
                    btc, entry, opened = 0, 0, 0
            candle_time = int(candles[-1][0])
            # A position cannot be reversed in the same polling cycle.
            daily_ok = marked_equity(cash, btc, bid, ask) >= day_start * 0.97
            if btc == 0 and exit_reason is None and daily_ok and buys < 4 and now - last_buy >= 3600 and candle_time != last_candle:
                direction = signal(candles)
                regime = market_regime() if direction != "WAIT" else "SIDEWAYS"
                if (direction == "LONG" and regime != "BULL") or (direction == "SHORT" and regime != "BEAR"):
                    log.info("PAPER entry blocked by market regime=%s signal=%s", regime, direction)
                    direction = "WAIT"
                # Max 10% of current equity, no leverage; simulated short collateral
                # is covered by the other 90% of available cash.
                budget = min(max(0, marked_equity(cash, btc, bid, ask)) * 0.10, cash * 0.10)
                if direction == "LONG" and entry_quality(candles, direction) and liquidity_and_atr_ok(candles) and budget > 5:
                    price = ask * (1 + SLIP)
                    amount = budget / (price * (1 + FEE))
                    fee = amount * price * FEE
                    cash -= amount * price + fee
                    btc, entry, opened = amount, price, now
                    buys += 1
                    last_buy = now
                    trade(db, "BUY_LONG", amount, price, fee, "ema9_21", marked_equity(cash, btc, bid, ask))
                    log.info("PAPER OPEN LONG %.8f BTC @ %.2f", btc, price)
                elif direction == "SHORT" and entry_quality(candles, direction) and budget > 5:
                    price = bid * (1 - SLIP)
                    amount = budget / price
                    fee = amount * price * FEE
                    cash += amount * price - fee
                    btc, entry, opened = -amount, price, now
                    buys += 1
                    last_buy = now
                    trade(db, "SELL_SHORT", amount, price, fee, "ema9_21", marked_equity(cash, btc, bid, ask))
                    log.info("PAPER OPEN SHORT %.8f BTC @ %.2f", amount, price)
            last_candle = candle_time
            db.execute("UPDATE state SET cash=?,btc=?,entry=?,opened=?,day=?,day_start=?,buys=?,last_buy=?,last_candle=? WHERE id=1", (cash,btc,entry,opened,day,day_start,buys,last_buy,last_candle))
            db.commit()
            log.info("PAPER status equity=%.2f cash=%.2f btc=%.8f direction=%s entries_today=%d", marked_equity(cash, btc, bid, ask), cash, btc, "LONG" if btc > 0 else "SHORT" if btc < 0 else "WAIT", buys)
        except Exception:
            log.exception("Cycle failed; retrying; NO live orders")
            db.rollback()
        time.sleep(15)

if __name__ == "__main__":
    run()
