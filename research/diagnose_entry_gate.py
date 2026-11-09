"""Explain why eligible paper candidates do not become trades (offline only)."""
import argparse,json,sqlite3
from collections import Counter
from research import isolated_paper_experiment as p

def analyze(path,fee=None,slip=None):
    fee=p.FEE if fee is None else fee
    slip=p.SLIP if slip is None else slip
    counts=Counter()
    samples=[]
    target_requirements=[]
    with sqlite3.connect(":memory:") as db:
        p.init(db)
        with open(path,encoding="utf-8") as stream:
            for line in stream:
                r=json.loads(line)
                r["estimated_roundtrip_cost_pct"]=200*(fee+slip)+float(r["spread_pct"])
                m5,m15=r["structure"]["5"],r["structure"]["15"]
                long_ok=m5["ema9"]>m5["ema21"] and m15["ema9"]>m15["ema21"] and m5["close"]>m5["support"] and m15["close"]>m15["support"]
                short_ok=m5["ema9"]<m5["ema21"] and m15["ema9"]<m15["ema21"] and m5["close"]<m5["resistance"] and m15["close"]<m15["resistance"]
                d="LONG" if long_ok else ("SHORT" if short_ok else "WAIT")
                if d=="WAIT": continue
                structure_ok=m5.get("higher_lows",False) if d=="LONG" else m5.get("lower_highs",False)
                rejection=m5.get("upper_wick_ratio",0)>0.6 if d=="LONG" else m5.get("lower_wick_ratio",0)>0.6
                false_break=(m5.get("false_break_up",False) or m15.get("false_break_up",False)) if d=="LONG" else (m5.get("false_break_down",False) or m15.get("false_break_down",False))
                eligible=r["spread_pct"]<=p.MAX_SPREAD_PCT and r["hourly_range_pct"]>=r["estimated_roundtrip_cost_pct"]*1.25 and m5.get("volume_ratio",0)>=.8 and structure_ok and not rejection and not false_break
                if not eligible: continue
                counts["eligible"]+=1
                entry=r["ask"]*(1+slip) if d=="LONG" else r["bid"]*(1-slip)
                structural=m5["support"]*(1-.001) if d=="LONG" else m5["resistance"]*(1+.001)
                stop=min(entry*(1-p.STOP_PCT),structural) if d=="LONG" else max(entry*(1+p.STOP_PCT),structural)
                stop_fill=stop*(1-slip) if d=="LONG" else stop*(1+slip)
                risk=abs(entry-stop_fill)+(entry+stop_fill)*fee
                target=m15["resistance"] if d=="LONG" else m15["support"]
                target_fill=target*(1-slip) if d=="LONG" else target*(1+slip)
                reward=(target_fill-entry) if d=="LONG" else (entry-target_fill)
                net=reward-(entry+target_fill)*fee
                rr=net/risk if risk>0 else None
                # Exact target price required for 2:1 net reward after exit slip and fees.
                required_target=(entry*(1+fee)+2*risk)/((1-slip)*(1-fee)) if d=="LONG" else (entry*(1-fee)-2*risk)/((1+slip)*(1+fee))
                required_move=abs(required_target-entry)/entry*100
                actual_move=((target-entry) if d=="LONG" else (entry-target))/entry*100
                if actual_move<=0: counts["target_behind_entry"]+=1
                else: counts["target_ahead_of_entry"]+=1
                target_requirements.append((required_move,actual_move))
                wide=abs(entry-stop)/entry>.03
                if wide: counts["stop_over_3pct"]+=1
                if net<=0: counts["nonpositive_net_reward"]+=1
                if net<2*risk: counts["net_rr_below_2"]+=1
                if net>=2*risk and not wide: counts["would_open_if_flat"]+=1
                if len(samples)<5: samples.append({"time":r["timestamp_utc"],"direction":d,"net_rr":round(rr,3) if rr is not None else None,"stop_pct":round(abs(entry-stop)/entry*100,3),"signed_target_pct":round(actual_move,3)})
    required_sorted=sorted(x[0] for x in target_requirements)
    actual_sorted=sorted(x[1] for x in target_requirements)
    positive_targets=sorted(x[1] for x in target_requirements if x[1]>0)
    median=lambda values: round(values[len(values)//2],3) if values else None
    return {"required_target_move_median_pct":median(required_sorted),"signed_target_move_median_pct":median(actual_sorted),"positive_target_move_median_pct":median(positive_targets),"fee_one_way":fee,"slippage_one_way":slip,"counts":dict(counts),"sample_candidates":samples,"note":"Counterfactual signal math on point-in-time Kraken snapshots; not actual fills or trading PnL."}

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("snapshots")
    ap.add_argument("--fee",type=float)
    ap.add_argument("--slip",type=float)
    args=ap.parse_args()
    print(json.dumps(analyze(args.snapshots,args.fee,args.slip),indent=2))
