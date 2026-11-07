"""Download public Kraken BTC/EUR 1m candles for offline paper-only backtest.
Kraken OHLC exposes at most ~720 recent candles; last unfinished bar is excluded.
Usage: python fetch_kraken_history.py history.csv
"""
import csv
import json
import sys
from urllib.request import Request, urlopen

def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python fetch_kraken_history.py history.csv")
    req = Request("https://api.kraken.com/0/public/OHLC?pair=XBTEUR&interval=1",
                  headers={"User-Agent": "BTC-Paper-Research/1.0"})
    with urlopen(req, timeout=30) as response:
        payload = json.load(response)
    if payload.get("error"):
        raise RuntimeError(str(payload["error"]))
    result = payload["result"]
    key = next(k for k in result if k != "last")
    rows = result[key][:-1]
    if len(rows) < 625:
        raise RuntimeError(f"Insufficient completed 1m candles: {len(rows)}")
    with open(sys.argv[1], "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp","open","high","low","close","volume"])
        for r in rows:
            writer.writerow([r[0],r[1],r[2],r[3],r[4],r[6]])
    print(f"Saved {len(rows)} completed Kraken BTC/EUR candles to {sys.argv[1]}")
    print("Run: python backtest.py " + sys.argv[1])
if __name__ == "__main__":
    main()
