"""Pre-registered-style statistical audit of BTC/EUR market-regime observations.
Use training to select ONE hypothesis, validation to confirm, untouched test
only if validation passes. Random-entry baseline, bootstrap and permutation
with deterministic seeds. Exploratory proxy, not executable Kraken fills.
"""
import json,math,random,statistics,sys
from research.donchian_risk import load

SEED=20261108
HORIZONS=(6,24,42)
COST=.0169
MIN_N=12
ITERATIONS=3000

def regime_at(rows,i):
    trend=rows[i][4]/rows[i-180][4]-1
    changes=[math.log(rows[k][4]/rows[k-1][4]) for k in range(i-41,i+1)]
    vol=statistics.pstdev(changes)*math.sqrt(6*365)
    trend_label="UP" if trend>.10 else "DOWN" if trend<-.10 else "SIDEWAYS"
    return trend_label+("__HIGH_VOL" if vol>.65 else "__LOW_VOL")

def observations(rows,start,end,h):
    # Fixed, non-overlapping h-bar sampling for each horizon, avoiding
    # artificial independence from overlapping forward returns.
    result=[]
    for i in range(max(start,180),end-h-1,h):
        r=rows[i+h][4]/rows[i+1][1]-1-COST
        result.append((regime_at(rows,i),r))
    return result

def audit(rows,start,end,h,target,seed):
    rng=random.Random(seed)
    data=observations(rows,start,end,h)
    chosen=[v for name,v in data if name==target]
    pool=[v for _,v in data]
    n=len(chosen)
    if n<MIN_N or len(pool)<n:
        return {"n":n,"eligible":False,"reason":"insufficient independent observations"}
    actual=statistics.mean(chosen)
    baseline=statistics.mean(pool)
    # Random-entry null: sample n entries without replacement from ALL
    # eligible times in the same time split and holding horizon.
    null_means=[statistics.mean(rng.sample(pool,n)) for _ in range(ITERATIONS)]
    p=(1+sum(x>=actual for x in null_means))/(ITERATIONS+1)
    boots=[statistics.mean(rng.choices(chosen,k=n)) for _ in range(ITERATIONS)]
    boots.sort()
    lo,hi=boots[int(.025*ITERATIONS)],boots[int(.975*ITERATIONS)]
    return {"n":n,"eligible":True,"mean_net_pct":round(100*actual,4),
            "random_entry_mean_net_pct":round(100*baseline,4),
            "excess_vs_random_pct":round(100*(actual-baseline),4),
            "bootstrap_95pct_mean_net_ci_pct":[round(100*lo,4),round(100*hi,4)],
            "random_entry_one_sided_p":round(p,5),
            "passes":bool(actual>0 and lo>0 and p<.05)}

def study(rows):
    a,b=int(len(rows)*.6),int(len(rows)*.8)
    # Family-wise correction for six regimes x three horizons (18 hypotheses).
    # Choose on training only, using positive net mean and sample sufficiency.
    candidates=[]
    for h in HORIZONS:
        train=observations(rows,180,a,h)
        for target in sorted(set(k for k,_ in train)):
            result=audit(rows,180,a,h,target,SEED+h)
            if result.get("eligible") and result["mean_net_pct"]>0:
                candidates.append((result["excess_vs_random_pct"],target,h,result))
    candidates.sort(reverse=True)
    if not candidates:
        return {"bars":len(rows),"train_candidate":None,"validation":None,
                "untouched_test":None,"decision":"NO_EDGE"}
    _,target,h,training=candidates[0]
    validation=audit(rows,a,b,h,target,SEED+1000+h)
    # Bonferroni adjustment for exploratory family of 18 potential choices.
    validated=validation.get("eligible") and validation.get("passes") and validation["random_entry_one_sided_p"]<.05/18
    test=audit(rows,b,len(rows),h,target,SEED+2000+h) if validated else None
    return {"bars":len(rows),"hypotheses_screened":18,
            "train_candidate":{"regime":target,"holding_4h_bars":h,"statistics":training},
            "validation":validation,"untouched_test":test,
            "decision":"CANDIDATE_FOR_FURTHER_RESEARCH" if validated and test and test.get("passes") else "NO_EDGE",
            "limitations":"Binance spot proxy, random-entry comparison is descriptive; bootstrap assumes sampled observations approximately independent; no fill model, no deployment."}

if __name__=="__main__":
    print(json.dumps(study(load(sys.argv[1])),indent=2))
