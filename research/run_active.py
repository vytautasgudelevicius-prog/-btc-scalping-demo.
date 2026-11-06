"""Fixed comparison, no parameter search. All prior study periods are reused."""
import json
import os
from pathlib import Path
import pandas as pd
from research.active_study import read, features, simulate, rolling_ema

root = Path("../market-data")
d = read(root / "XBTEUR_1.csv", 60)
h = read(root / "XBTEUR_240.csv", 14400)
utc = lambda s: int(pd.Timestamp(s, tz="UTC").timestamp())
start, end = utc("2024-10-01"), utc("2026-10-01")
if os.getenv("UNSEEN_2023"):
    start, end = utc("2023-01-01"), utc("2024-01-01")
d = d[d.timestamp.between(start-120*86400, end-1)].reset_index(drop=True)
h = h[h.timestamp < end].reset_index(drop=True)
# Construct only complete 5m groups; never forward-fill a missing minute.
five = d.assign(bucket=(d.timestamp//300)*300).groupby("bucket").agg(
    close=("close","last"), count=("close","size")).reset_index()
five = five[five["count"] == 5].copy()
fast, slow = rolling_ema(five.close, 9), rolling_ema(five.close, 21)
five["trend5"] = ((fast>slow).astype(int)-(fast<slow).astype(int))
five["available5"] = five.bucket+300
d = features(d,h)
d = pd.merge_asof(d, five[["available5","trend5"]], left_on="decision",
                  right_on="available5",direction="backward")
d.loc[d.decision-d.available5>=300,"trend5"] = 0
periods = {"development":(start,utc("2025-10-01")),
           "reused_validation":(utc("2025-10-01"),utc("2026-04-01")),
           "reused_test":(utc("2026-04-01"),end)}
if os.getenv("UNSEEN_2023"):
    periods = {"unseen_2023":(start,end)}
out = {"independent_holdout":False,
       "note":"Prior periods already inspected. Fixed candidate; no optimization. OHLC proxy, hypothetical shorts, no funding.",
       "last_data_timestamp":int(d.timestamp.max()),"results":{}}
for variant in os.getenv("VARIANTS", "baseline,active,active_5m").split(","):
    out["results"][variant]={}
    for name,(lo,hi) in periods.items():
        result,_=simulate(d,lo,hi,variant)
        result["trades_per_calendar_day"]=result["trades"]/((hi-lo)/86400)
        out["results"][variant][name]=result
        print(variant,name,json.dumps(result),flush=True)
Path(os.getenv("OUTPUT", "research/active_results.json")).write_text(json.dumps(out,indent=2))
