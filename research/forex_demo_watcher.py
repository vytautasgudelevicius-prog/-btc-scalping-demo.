"""24/5 EUR/USD DEMO signal watcher (NO orders, NO live feed included).

Supply fresh, chronologically ordered broker 1-minute CSV snapshots via
FOREX_CSV_PATH. Re-read on every polling interval. No simulated prices.
"""
import json
import os
import time
from datetime import datetime, timezone
from research.forex_eurusd_backtest import load_bars
from research.forex_signal_forecast import forecast_signal

def market_session(now):
    # Indicative FX session; broker-specific Sunday open and Friday close vary.
    return now.weekday() < 5

def check_once(path, now=None):
    now=now or datetime.now(timezone.utc)
    if not market_session(now):
        return {"status":"WAIT","reason":"weekend_market_closed","order_allowed":False}
    if not path or not os.path.isfile(path):
        return {"status":"ERROR","reason":"broker_data_feed_not_configured","order_allowed":False}
    try:
        bars=load_bars(path)
    except (ValueError,KeyError,OSError) as exc:
        return {"status":"ERROR","reason":"invalid_market_data","detail":str(exc),"order_allowed":False}
    if not bars or (now-bars[-1][0]).total_seconds()>120 or (now-bars[-1][0]).total_seconds() < -30:
        return {"status":"WAIT","reason":"stale_market_data","order_allowed":False}
    result=forecast_signal(bars)
    result["order_allowed"]=False
    result["last_candle_utc"]=bars[-1][0].isoformat()
    return result

def run():
    path=os.getenv("FOREX_CSV_PATH","")
    interval=max(10,int(os.getenv("FOREX_POLL_SECONDS","60")))
    previous=None
    while True:
        result=check_once(path)
        # Emit changes and errors only; avoid per-minute alert spam.
        key=(result["status"],result.get("reason"),result.get("direction"))
        if key != previous:
            print(json.dumps({"at_utc":datetime.now(timezone.utc).isoformat(),**result}),flush=True)
            previous=key
        time.sleep(interval)

if __name__=="__main__":
    run()
