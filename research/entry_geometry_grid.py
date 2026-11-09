"""Offline target/stop feasibility grid for BTC/EUR paper signals.

This is a diagnostic of entry geometry, NOT evidence of profitability:
it does not assume targets were filled, or inspect future price movement.
"""
import argparse,json
from collections import Counter
from research import isolated_paper_experiment as p

def grid(path,fees=(.008,.002,.001,.0005),stop_pcts=(.0025,.005,.0075,.01),rr_values=(1.0,1.5,2.0)):
    reports=[json.loads(line) for line in open(path,encoding="utf-8") if line.strip()]
    rows=[]
    for fee in fees:
        for stop_pct in stop_pcts:
            counts=Counter()
            for r in reports:
                m5,m15=r["structure"]["5"],r["structure"]["15"]
                long_ok=m5["ema9"]>m5["ema21"] and m15["ema9"]>m15["ema21"] and m5["close"]>m5["support"] and m15["close"]>m15["support"]
                short_ok=m5["ema9"]<m5["ema21"] and m15["ema9"]<m15["ema21"] and m5["close"]<m5["resistance"] and m15["close"]<m15["resistance"]
                d="LONG" if long_ok else "SHORT" if short_ok else None
                if not d: continue
                vol=m5.get("volume_ratio",0)>=.8
                struct=m5.get("higher_lows",False) if d=="LONG" else m5.get("lower_highs",False)
                wick=m5.get("upper_wick_ratio",0)>.6 if d=="LONG" else m5.get("lower_wick_ratio",0)>.6
                false=(m5.get("false_break_up",False) or m15.get("false_break_up",False)) if d=="LONG" else (m5.get("false_break_down",False) or m15.get("false_break_down",False))
                if not (vol and struct and not wick and not false and r["spread_pct"]<=p.MAX_SPREAD_PCT and r["hourly_range_pct"]>=1.25*(200*(fee+p.SLIP)+r["spread_pct"])):continue
                counts["eligible"]+=1
                entry=r["ask"]*(1+p.SLIP) if d=="LONG" else r["bid"]*(1-p.SLIP)
                structural=m5["support"]*(1-.001) if d=="LONG" else m5["resistance"]*(1+.001)
                stop=min(entry*(1-stop_pct),structural) if d=="LONG" else max(entry*(1+stop_pct),structural)
                stop_fill=stop*(1-p.SLIP) if d=="LONG" else stop*(1+p.SLIP)
                risk=abs(entry-stop_fill)+(entry+stop_fill)*fee
                target=m15["resistance"] if d=="LONG" else m15["support"]
                target_fill=target*(1-p.SLIP) if d=="LONG" else target*(1+p.SLIP)
                reward=(target_fill-entry if d=="LONG" else entry-target_fill)-(entry+target_fill)*fee
                for rr in rr_values:
                    if reward>=rr*risk and abs(entry-stop)/entry<=.03:counts[f"candidate_rr_{rr}"]+=1
            rows.append({"fee":fee,"minimum_stop_pct":stop_pct*100,**dict(counts)})
    return {"observations":len(reports),"rows":rows,"limitations":"Signal geometry only. No execution simulation, trade outcomes, profit or loss estimates."}

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("snapshots")
    a=ap.parse_args()
    print(json.dumps(grid(a.snapshots),indent=2))
