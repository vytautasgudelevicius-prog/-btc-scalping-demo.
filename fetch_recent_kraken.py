"""Fetch the *recent* Kraken BTC/EUR 1-minute OHLC snapshot for research.

Kraken OHLC returns only ~720 most recent candles, NOT historical months.
This utility does not write the production trading database or place orders.
Usage: python fetch_recent_kraken.py recent_btc_eur_1m.csv
"""
import csv
import json
import sys
from urllib.request import Request, urlopen
from datetime import datetime, timezone

URL = "https://api.kraken.com/0/public/OHLC?pair=XBTEUR&interval=1"

def main():
    if len(sys.argv)!=2:
        raise SystemExit("Usage: python fetch_recent_kraken.py output.csv")
    req=Request(URL,headers={"User-Agent":"BTC-DEMO-Research/1.0"})
    with urlopen(req,timeout=30) as response:
        data=json.load(response)
    if data.get("error"):
        raise RuntimeError(str(data["error"]))
    key=next(k for k in data["result"] if k!="last")
    # Last candle is unfinished and must never be used for backtesting.
    candles=data["result"][key][:-1]
    if len(candles)<250:
        raise RuntimeError("Insufficient completed candles")
    with open(sys.argv[1],"w",newline="",encoding="utf-8") as f:
        writer=csv.writer(f)
        writer.writerow(("timestamp","open","high","low","close","volume"))
        for c in candles:
            writer.writerow((datetime.fromtimestamp(int(c[0]),timezone.utc).isoformat(),
                             c[1],c[2],c[3],c[4],c[6]))
    print(f"Saved {len(candles)} recent completed BTC/EUR 1m candles.")
    print("WARNING: Kraken OHLC cannot supply months of backtest history.")
    print("WARNING: Research-only data. Backtest is not production-strategy parity.")

if __name__=="__main__":
    main()
