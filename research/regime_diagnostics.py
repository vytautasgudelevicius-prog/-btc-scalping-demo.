"""Regime diagnostics, NOT a signal generator. 36m BTC/EUR 4h spot proxy.
Classifies market using PAST completed bars, measures subsequent returns after
hypothetical Kraken spot roundtrip costs. Overlapping outcomes are descriptive,
not independent evidence. No deployment authorization.
"""
import json,math,statistics,sys
from research.donchian_risk import load

def study(rows):
    horizons=(6,24,42) # 1, 4, 7 days
    fees={"taker_taker":.0169,"maker_maker_hypothetical":.0089}
    results={}
    # 180 4h bars ~30 days, 42 bars ~7 days
    # Disjoint 42-bar evaluation blocks reduce dependence, not eliminate it.
    for phase,(start,end) in {"train":(180,int(len(rows)*.6)),
                               "validation":(int(len(rows)*.6),int(len(rows)*.8)),
                               "untouched_test":(int(len(rows)*.8),len(rows))}.items():
        buckets={}
        for i in range(max(180,start),end-max(horizons),42):
            now=rows[i][4]
            trend=now/rows[i-180][4]-1
            moves=[math.log(rows[k][4]/rows[k-1][4]) for k in range(i-41,i+1)]
            realized_vol=statistics.pstdev(moves)*math.sqrt(6*365)
            if trend>.10: regime="UP_30D"
            elif trend<-.10: regime="DOWN_30D"
            else: regime="SIDEWAYS_30D"
            vol_regime="HIGH_VOL" if realized_vol>.65 else "LOW_VOL"
            key=regime+"__"+vol_regime
            bucket=buckets.setdefault(key,{"samples":0,"forward":{str(h):[] for h in horizons}})
            bucket["samples"]+=1
            for h in horizons:
                bucket["forward"][str(h)].append(rows[i+h][4]/rows[i+1][1]-1)
        phase_result={}
        for regime,bucket in buckets.items():
            outcomes={}
            for h,values in bucket["forward"].items():
                outcomes[h]={"samples":len(values),
                    "avg_gross_pct":round(100*statistics.mean(values),4),
                    "median_gross_pct":round(100*statistics.median(values),4),
                    "positive_gross_pct":round(100*sum(x>0 for x in values)/len(values),2),
                    "after_costs":{name:{"avg_net_pct":round(100*(statistics.mean(values)-cost),4),
                        "positive_net_pct":round(100*sum(x>cost for x in values)/len(values),2)}
                        for name,cost in fees.items()}}
            phase_result[regime]={"observations":bucket["samples"],"horizons":outcomes}
        results[phase]=phase_result
    return {"source":"Binance BTC/EUR spot 4h proxy; NOT Kraken execution",
            "bars":len(rows),"regime_definitions":"30-day past return >+10%, <-10%, else sideways; 7-day annualized realized vol >65%",
            "sampling":"42-bar nonoverlapping starts per split, forward horizons 1d/4d/7d",
            "fee_assumptions_roundtrip":fees,"splits":results,
            "decision":"DIAGNOSTICS_ONLY_NO_DEPLOYMENT",
            "limitations":"Exploratory multiple comparisons; no significance corrections, no portfolio simulation, no fill probability, no trading approval."}

if __name__=="__main__":
    print(json.dumps(study(load(sys.argv[1])),indent=2))
