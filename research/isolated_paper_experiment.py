"""Isolated, read-only-market BTC/EUR paper trader. NEVER sends exchange orders."""
import json, os, sqlite3, time
from datetime import datetime, timezone
from pathlib import Path
from research.kraken_shadow_observer import observe
from bot import FEE, SLIP

DB=os.getenv("PAPER_EXPERIMENT_DB","/data/experiment.sqlite3")
INITIAL=1000.0
RISK=0.005
DAILY_LIMIT=0.02
STOP_PCT=0.01
MAX_HOLD=300

def init(db):
    db.execute("""CREATE TABLE IF NOT EXISTS trades(
      id INTEGER PRIMARY KEY, candle TEXT UNIQUE, opened TEXT, closed TEXT,
      direction TEXT, entry REAL, qty REAL, stop REAL, exit REAL,
      pnl REAL, reason TEXT)""")
    db.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT)")
    db.commit()

def get(db,key,default):
    row=db.execute("SELECT value FROM state WHERE key=?",(key,)).fetchone()
    return row[0] if row else default

def put(db,key,value):
    db.execute("INSERT OR REPLACE INTO state(key,value) VALUES(?,?)",(key,str(value)))

def tick(db,report):
    if report["pair"]!="BTC/EUR" or report["orders_enabled"] or report["decision"]!="OBSERVE_ONLY":
        raise ValueError("Fail-closed: unexpected source")
    bid,ask=report["bid"],report["ask"]
    if not 0<bid<=ask: raise ValueError("Invalid quote")
    now=datetime.fromisoformat(report["timestamp_utc"])
    day=now.date().isoformat()
    equity=float(get(db,"equity",INITIAL))
    if get(db,"day","")!=day:
        put(db,"day",day)
        put(db,"day_start_equity",equity)
    day_start=float(get(db,"day_start_equity",equity))
    active=db.execute("SELECT id,opened,direction,entry,qty,stop FROM trades WHERE closed IS NULL").fetchone()
    event="WAIT"
    if active:
        tid,opened,direction,entry,qty,stop=active
        held=(now-datetime.fromisoformat(opened)).total_seconds()
        exit_quote=bid*(1-SLIP) if direction=="LONG" else ask*(1+SLIP)
        stop_hit=exit_quote<=stop if direction=="LONG" else exit_quote>=stop
        if stop_hit or held>=MAX_HOLD:
            pnl=(exit_quote-entry)*qty if direction=="LONG" else (entry-exit_quote)*qty
            pnl-=(entry+exit_quote)*qty*FEE
            equity+=pnl
            db.execute("UPDATE trades SET closed=?,exit=?,pnl=?,reason=? WHERE id=?",
                       (now.isoformat(),exit_quote,pnl,"STOP" if stop_hit else "TIME",tid))
            put(db,"equity",equity)
            event="CLOSED"
    else:
        direction=report["ema_signal"]
        eligible=(report["context_candidate"] and report["quality_filter"] and
                  report["liquidity_atr_filter"] and direction in ("LONG","SHORT"))
        halted=equity<=day_start*(1-DAILY_LIMIT)
        if eligible and not halted and equity>0:
            entry=ask*(1+SLIP) if direction=="LONG" else bid*(1-SLIP)
            stop=entry*(1-STOP_PCT) if direction=="LONG" else entry*(1+STOP_PCT)
            # Risk includes worst-case stop execution plus two taker fees.
            unit_risk=abs(entry-stop)+(entry+stop)*FEE
            qty=min(equity*RISK/unit_risk,equity/entry)
            if qty>0:
                cur=db.execute("""INSERT OR IGNORE INTO trades(candle,opened,direction,entry,qty,stop)
                                   VALUES(?,?,?,?,?,?)""",
                               (report["last_completed_candle"],now.isoformat(),direction,entry,qty,stop))
                if cur.rowcount: event="OPENED"
        elif halted: event="DAILY_LOSS_HALT"
    db.commit()
    stats=db.execute("SELECT COUNT(*),COALESCE(SUM(pnl),0),SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END) FROM trades WHERE closed IS NOT NULL").fetchone()
    open_count=db.execute("SELECT COUNT(*) FROM trades WHERE closed IS NULL").fetchone()[0]
    return {"event":event,"equity_eur":round(equity,2),"closed":stats[0],
            "net_pnl_eur":round(stats[1],2),"wins":stats[2] or 0,
            "open_positions":open_count,"daily_limit_eur":round(day_start*DAILY_LIMIT,2),
            "orders_enabled":False,"exchange_credentials_used":False,
            "warning":"Paper-only approximation; stop fills can slip beyond configured risk."}

def main():
    Path(DB).parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(DB,timeout=30) as db:
        init(db)
        while True:
            try:
                print(json.dumps(tick(db,observe())),flush=True)
            except Exception as exc:
                print(json.dumps({"error":str(exc),"orders_enabled":False}),flush=True)
            time.sleep(20)
if __name__=="__main__": main()
