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
    if len(candles) < 30:
        return False
    close = [float(c[4]) for c in candles]
    fast, slow = ema(close, 9), ema(close, 21)
    return fast[-2] <= slow[-2] and fast[-1] > slow[-1]

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
            equity = cash + btc * bid * (1 - FEE - SLIP)
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
                    trade(db, "SELL", btc, price, fee, exit_reason, cash)
                    log.info("PAPER SELL reason=%s equity=%.2f", exit_reason, cash)
                    btc, entry, opened = 0, 0, 0
            candle_time = int(candles[-1][0])
            daily_ok = equity >= day_start * 0.97
            if btc == 0 and daily_ok and buys < 12 and now - last_buy >= 600 and candle_time != last_candle:
                if signal(candles):
                    budget = min(cash * 0.10, cash / (1 + FEE))
                    price = ask * (1 + SLIP)
                    amount = budget / (price * (1 + FEE))
                    fee = amount * price * FEE
                    if amount > 0 and budget > 5:
                        cash -= amount * price + fee
                        btc, entry, opened = amount, price, now
                        buys += 1
                        last_buy = now
                        trade(db, "BUY", amount, price, fee, "ema9_21", cash + btc * bid)
                        log.info("PAPER BUY %.8f BTC @ %.2f; remaining EUR %.2f", btc, price, cash)
            last_candle = candle_time
            db.execute("UPDATE state SET cash=?,btc=?,entry=?,opened=?,day=?,day_start=?,buys=?,last_buy=?,last_candle=? WHERE id=1", (cash,btc,entry,opened,day,day_start,buys,last_buy,last_candle))
            db.commit()
            log.info("PAPER status equity=%.2f cash=%.2f btc=%.8f buys_today=%d", cash + btc * bid * (1-FEE-SLIP), cash, btc, buys)
        except Exception:
            log.exception("Cycle failed; retrying; NO live orders")
            db.rollback()
        time.sleep(15)

if __name__ == "__main__":
    run()
