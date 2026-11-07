"""Fetch public Binance BTC/EUR monthly 1m archives as a RESEARCH PROXY.
Not Kraken execution data. Fail closed on gaps or insufficient coverage.
"""
import csv
import io
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

MONTHS = ["2026-08", "2026-09", "2026-10"]
BASE = "https://data.binance.vision/data/spot/monthly/klines/BTCEUR/1m/"
OUT = Path("research/history_btceur_proxy.csv")


def main():
    bars = []
    for month in MONTHS:
        filename = f"BTCEUR-1m-{month}.zip"
        url = BASE + filename
        with urllib.request.urlopen(url, timeout=90) as response:
            archive = response.read()
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            with z.open(filename.replace(".zip", ".csv")) as f:
                for raw in csv.reader(io.TextIOWrapper(f)):
                    # Binance switched from millisecond to microsecond timestamps.
                    stamp = int(raw[0])
                    seconds = stamp / (1_000_000 if stamp > 10**14 else 1000)
                    minute = int(seconds // 60)
                    bars.append((minute, *raw[1:5], raw[5]))
        print(f"Fetched {month}: {len(bars)} cumulative bars", flush=True)
    bars.sort(key=lambda r: r[0])
    segments = []
    current = []
    for row in bars:
        if current and row[0] != current[-1][0] + 1:
            segments.append(current)
            current = []
        current.append(row)
    if current:
        segments.append(current)
    best = max(segments, key=len)
    if len(best) < 10080:
        raise RuntimeError(f"No contiguous week of data; longest run={len(best)}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for minute, o, h, l, c, volume in best:
            writer.writerow([datetime.fromtimestamp(minute * 60, timezone.utc).isoformat(), o, h, l, c, volume])
    print(f"Saved {len(best)} consecutive 1m bars, {best[0][0]}..{best[-1][0]}; source=Binance BTCEUR proxy", flush=True)


if __name__ == "__main__":
    main()
