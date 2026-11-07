"""Persistent forward-only Kraken BTC/EUR shadow observations; NEVER sends orders.

Separate SQLite database; sample once per completed 1m candle and settle after 5m.
Entry and exit use observed bid/ask, simulated taker fees and slippage.
WAIT observations are logged but never treated as hypothetical trades.
"""
import json
import os
import sqlite3
import time
from datetime import datetime,timezone
from pathlib import Path
from research.kraken_shadow_observer import observe
from bot import FEE, SLIP

DB_PATH=os.getenv("SHADOW_DB_PATH","/data/kraken_shadow.sqlite3")
HORIZON_SECONDS=300

def initialize(db):
    db.execute("""CREATE TABLE IF NOT EXISTS observations (
        candle TEXT PRIMARY KEY, timestamp TEXT NOT NULL, direction TEXT NOT NULL,
        bid REAL NOT NULL, ask REAL NOT NULL, spread_pct REAL NOT NULL,
        cost_pct REAL NOT NULL, quality INTEGER NOT NULL, liquidity INTEGER NOT NULL,
        candidate INTEGER NOT NULL, settled_timestamp TEXT, exit_bid REAL, exit_ask REAL,
        gross_pct REAL, net_pct REAL)""")
    db.commit()

def record(db, report):
    direction=report["ema_signal"]
    if direction not in ("LONG","SHORT","WAIT"):
        raise ValueError("Invalid signal")
    values=(report["last_completed_candle"],report["timestamp_utc"],direction,
            report["bid"],report["ask"],report["spread_pct"],
            report["estimated_roundtrip_cost_pct"],int(report["quality_filter"]),
            int(report["liquidity_atr_filter"]),int(report["context_candidate"]))
    cur=db.execute("""INSERT OR IGNORE INTO observations
        (candle,timestamp,direction,bid,ask,spread_pct,cost_pct,quality,liquidity,candidate)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",values)
    db.commit()
    return cur.rowcount

def net_return(direction,entry_bid,entry_ask,exit_bid,exit_ask):
    if min(entry_bid,entry_ask,exit_bid,exit_ask)<=0:
        raise ValueError("Invalid quote")
    if direction=="LONG":
        entry=entry_ask*(1+SLIP)
        exit=exit_bid*(1-SLIP)
        gross=exit/entry-1
        net=(exit*(1-FEE))/(entry*(1+FEE))-1
    elif direction=="SHORT":
        # Hypothetical fully collateralized short; not executable spot orders.
        entry=entry_bid*(1-SLIP)
        exit=exit_ask*(1+SLIP)
        gross=1-exit/entry
        net=((entry*(1-FEE)-exit*(1+FEE))/entry)
    else:
        raise ValueError("Only LONG/SHORT can settle")
    return round(gross*100,6),round(net*100,6)

def settle(db, report):
    now=datetime.fromisoformat(report["timestamp_utc"]).timestamp()
    rows=db.execute("""SELECT candle,timestamp,direction,bid,ask FROM observations
        WHERE candidate=1 AND settled_timestamp IS NULL""").fetchall()
    settled=0
    for candle,timestamp,direction,bid,ask in rows:
        if now-datetime.fromisoformat(timestamp).timestamp()<HORIZON_SECONDS:
            continue
        # Never pretend an hours-late quote is a five-minute fill.
        if now-datetime.fromisoformat(timestamp).timestamp()>420:
            db.execute("UPDATE observations SET settled_timestamp=? WHERE candle=? AND settled_timestamp IS NULL",
                       (report["timestamp_utc"],candle))
            continue
        gross,net=net_return(direction,bid,ask,report["bid"],report["ask"])
        db.execute("""UPDATE observations SET settled_timestamp=?,exit_bid=?,exit_ask=?,
            gross_pct=?,net_pct=? WHERE candle=? AND settled_timestamp IS NULL""",
            (report["timestamp_utc"],report["bid"],report["ask"],gross,net,candle))
        settled+=1
    db.commit()
    return settled

def summary(db):
    rows=db.execute("""SELECT net_pct FROM observations
        WHERE candidate=1 AND net_pct IS NOT NULL""").fetchall()
    values=[x[0] for x in rows]
    pending=db.execute("""SELECT COUNT(*) FROM observations
        WHERE candidate=1 AND settled_timestamp IS NULL""").fetchone()[0]
    total=db.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    return {"observations":total,"settled_candidates":len(values),"pending_candidates":pending,
            "winning_candidates":sum(x>0 for x in values),
            "avg_net_pct":round(sum(values)/len(values),6) if values else None,
            "positive_net_after_costs":bool(len(values)>=100 and sum(values)>0),
            "deployment_authorized":False,
            "warning":"Forward observations only; overlapping signals and five-minute exit assumption. No live orders."}

def tick(db,fetch=None):
    report=observe() if fetch is None else observe(fetch)
    # First settle older signals using the current fresh quote, then record.
    settled=settle(db,report)
    inserted=record(db,report)
    return {"inserted":inserted,"settled":settled,"latest":report,"summary":summary(db)}

def main():
    Path(DB_PATH).parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(DB_PATH,timeout=30) as db:
        initialize(db)
        while True:
            try:
                print(json.dumps(tick(db)),flush=True)
            except Exception as exc:
                print(json.dumps({"error":str(exc),"orders_enabled":False}),flush=True)
            time.sleep(20)

if __name__=="__main__":
    main()
