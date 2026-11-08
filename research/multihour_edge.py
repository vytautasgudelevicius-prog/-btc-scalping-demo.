"""Research-only multi-hour BTC LONG/SHORT strategy, strict chronological holdout.

Uses completed 5m bars, next bar OPEN entry, fixed-horizon CLOSE exit.
Non-overlapping trades; flat at validation/test boundaries; no intrabar fill claims.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backtest import read_csv
from research.candles import aggregate

HORIZONS = (12, 36, 72)  # 1h, 3h, 6h
LOOKBACKS = (12, 36, 72)

def signal(bars, i, lookback, mode):
    if i < max(lookback + 1, 30):
        return 0
    closes = [b[4] for b in bars[i-lookback:i+1]]
    if mode == "trend":
        fast = sum(closes[-6:]) / 6
        slow = sum(closes[:-1]) / len(closes[:-1])
        return 1 if fast > slow * 1.001 else -1 if fast < slow * .999 else 0
    previous = bars[i-lookback:i]
    close = bars[i][4]
    return 1 if close > max(b[2] for b in previous) else -1 if close < min(b[3] for b in previous) else 0

def evaluate(bars, start, end, mode, lookback, horizon, cost):
    gross_returns, net_returns, sides = [], [], []
    i = max(start, lookback + 1, 30)
    while i + horizon < end:
        side = signal(bars, i, lookback, mode)
        if not side:
            i += 1
            continue
        entry = bars[i+1][1]
        exit_price = bars[i+horizon][4]
        gross = side * (exit_price / entry - 1)
        gross_returns.append(gross)
        net_returns.append(gross - cost)
        sides.append(side)
        i += horizon + 1
    n = len(net_returns)
    running = peak = max_dd = 0.0
    for value in net_returns:
        running += value
        peak = max(peak, running)
        max_dd = max(max_dd, peak-running)
    return {"trades":n, "longs":sides.count(1), "shorts":sides.count(-1),
            "avg_gross_pct":round(100*sum(gross_returns)/n,5) if n else None,
            "avg_net_pct":round(100*sum(net_returns)/n,5) if n else None,
            "win_rate_pct":round(100*sum(x>0 for x in net_returns)/n,3) if n else None,
            "sum_unit_notional_net_pct":round(100*sum(net_returns),4),
            "max_cumulative_unit_notional_drawdown_pct":round(100*max_dd,4)}

def run(rows, fee_per_side=.008, spread_bps=5, slippage_bps=2, min_validation_trades=30):
    if min(fee_per_side,spread_bps,slippage_bps)<0:
        raise ValueError("Negative trading costs")
    if any((b[0]-a[0]).total_seconds()!=60 for a,b in zip(rows,rows[1:])):
        raise ValueError("Noncontiguous 1m history")
    bars=aggregate(rows,5)
    if len(bars)<1000:
        raise ValueError("Insufficient completed 5m history")
    cost=2*fee_per_side+(spread_bps+2*slippage_bps)/10000
    a,b=int(len(bars)*.6),int(len(bars)*.8)
    validation={}
    for mode in ("trend","breakout"):
        for lookback in LOOKBACKS:
            for horizon in HORIZONS:
                key=f"{mode}_{lookback}_{horizon}"
                validation[key]=evaluate(bars,a,b,mode,lookback,horizon,cost)
    candidates=[(v["avg_net_pct"],key) for key,v in validation.items()
                if v["trades"]>=min_validation_trades and v["avg_net_pct"] is not None
                and v["avg_net_pct"]>0 and v["longs"]>0 and v["shorts"]>0]
    selected=max(candidates)[1] if candidates else None
    test=None
    if selected:
        mode,lookback,horizon=selected.rsplit("_",2)
        test=evaluate(bars,b,len(bars),mode,int(lookback),int(horizon),cost)
    passed=bool(test and test["trades"]>=min_validation_trades and
                test["longs"]>0 and test["shorts"]>0 and test["avg_net_pct"]>0)
    return {"method":"nonoverlapping_multihour_validation_selected_holdout",
            "roundtrip_cost_pct":round(cost*100,5),
            "validation":validation,"selected_on_validation":selected,
            "untouched_test":test,
            "decision":"RESEARCH_ONLY" if passed else "NO_TRADE",
            "warning":"Unit-notional diagnostic only; drawdown is not account equity. No stop fills, funding, exchange verification, or live orders. No Railway deployment authorization."}

if __name__=="__main__":
    print(json.dumps(run(read_csv(sys.argv[1])),indent=2))
