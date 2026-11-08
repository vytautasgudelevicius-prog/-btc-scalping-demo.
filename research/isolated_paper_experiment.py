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
# No time-based exit; hard stop and structural invalidation only.
# Experimental paper-only trend entry; production signal remains unchanged.
MIN_HOURLY_TREND_PCT=0.15
MIN_HOURLY_RANGE_PCT=0.25
MAX_SPREAD_PCT=0.05

def init(db):
    db.execute("""CREATE TABLE IF NOT EXISTS trades(
      id INTEGER PRIMARY KEY, candle TEXT UNIQUE, opened TEXT, closed TEXT,
      direction TEXT, entry REAL, qty REAL, stop REAL, exit REAL,
      pnl REAL, reason TEXT)""")
    db.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS decisions (candle TEXT PRIMARY KEY, timestamp TEXT, direction TEXT, eligible INTEGER, reason TEXT, spread_pct REAL, estimated_cost_pct REAL)")
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
    s=report.get("structure",{})
    m5,m15=s.get("5",{}),s.get("15",{})
    if not m5 or not m15: raise ValueError("Missing completed 5m/15m structure")
    event="WAIT"
    if active:
        tid,opened,direction,entry,qty,stop=active
        exit_quote=bid*(1-SLIP) if direction=="LONG" else ask*(1+SLIP)
        # Do not interpret one adverse candle as a reversal.
        reversal=(m5["ema9"]<m5["ema21"] and m15["ema9"]<m15["ema21"]
                  and m5["close"]<m5["support"] and m15["close"]<m15["support"]) if direction=="LONG" else (
                  m5["ema9"]>m5["ema21"] and m15["ema9"]>m15["ema21"]
                  and m5["close"]>m5["resistance"] and m15["close"]>m15["resistance"])
        # Tighten only; never loosen a protective stop.
        if direction=="LONG":
            candidate=m5["support"]*(1-0.001)
            if candidate>stop and candidate<bid: stop=candidate
        else:
            candidate=m5["resistance"]*(1+0.001)
            if candidate<stop and candidate>ask: stop=candidate
        db.execute("UPDATE trades SET stop=? WHERE id=?",(stop,tid))
        stop_hit=exit_quote<=stop if direction=="LONG" else exit_quote>=stop
        if stop_hit or reversal:
            pnl=(exit_quote-entry)*qty if direction=="LONG" else (entry-exit_quote)*qty
            pnl-=(entry+exit_quote)*qty*FEE
            equity+=pnl
            db.execute("UPDATE trades SET closed=?,exit=?,pnl=?,reason=? WHERE id=?",
                       (now.isoformat(),exit_quote,pnl,"STOP" if stop_hit else "STRUCTURE_REVERSAL",tid))
            put(db,"equity",equity)
            event="CLOSED"
    else:
        # Multi-timeframe trend alignment on completed 5m/15m bars.
        long_ok=(m5["ema9"]>m5["ema21"] and m15["ema9"]>m15["ema21"]
                 and m5["close"]>m5["support"] and m15["close"]>m15["support"])
        short_ok=(m5["ema9"]<m5["ema21"] and m15["ema9"]<m15["ema21"]
                  and m5["close"]<m5["resistance"] and m15["close"]<m15["resistance"])
        direction="LONG" if long_ok else ("SHORT" if short_ok else "WAIT")
        # Volume confirmation and candle rejection: avoid thin, exhausted moves.
        volume_ok=m5.get("volume_ratio",0)>=0.8
        structure_ok=(m5.get("higher_lows",False) if direction=="LONG" else
                      m5.get("lower_highs",False) if direction=="SHORT" else False)
        rejection=(m5.get("upper_wick_ratio",0)>0.6 if direction=="LONG" else
                   m5.get("lower_wick_ratio",0)>0.6 if direction=="SHORT" else True)
        cost_ok=report["hourly_range_pct"]>=report["estimated_roundtrip_cost_pct"]
        eligible=(direction!="WAIT" and report["spread_pct"]<=MAX_SPREAD_PCT
                  and cost_ok and volume_ok and structure_ok and not rejection)
        reasons=[]
        if direction=="WAIT": reasons.append("NO_ALIGNED_TREND")
        if not cost_ok: reasons.append("COST_EXCEEDS_RECENT_RANGE")
        if not volume_ok: reasons.append("LOW_VOLUME")
        if not structure_ok: reasons.append("WEAK_MARKET_STRUCTURE")
        if rejection: reasons.append("REJECTION_WICK")
        if report["spread_pct"]>MAX_SPREAD_PCT: reasons.append("SPREAD")
        db.execute("INSERT OR IGNORE INTO decisions VALUES(?,?,?,?,?,?,?)",
                   (report["last_completed_candle"],now.isoformat(),direction,int(eligible),
                    ",".join(reasons) or "ELIGIBLE",report["spread_pct"],
                    report["estimated_roundtrip_cost_pct"]))
        halted=equity<=day_start*(1-DAILY_LIMIT)
        if eligible and not halted and equity>0:
            entry=ask*(1+SLIP) if direction=="LONG" else bid*(1-SLIP)
            structural=m5["support"]*(1-0.001) if direction=="LONG" else m5["resistance"]*(1+0.001)
            stop=min(entry*(1-STOP_PCT),structural) if direction=="LONG" else max(entry*(1+STOP_PCT),structural)
            # Risk includes worst-case stop execution plus two taker fees.
            unit_risk=abs(entry-stop)+(entry+stop)*FEE
            # Require a plausible 2:1 gross reward/risk against structural target.
            target=m15["resistance"] if direction=="LONG" else m15["support"]
            reward=(target-entry if direction=="LONG" else entry-target)
            qty=min(equity*RISK/unit_risk,equity/entry) if reward>=2*unit_risk else 0
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
