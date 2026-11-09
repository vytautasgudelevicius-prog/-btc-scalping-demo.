"""Research-only, long-only adaptive grid benchmark. No exchange orders.

One position maximum. Completed 1m bars set ATR/grid spacing; fills use
NEXT bar open, never the same bar that generated the signal. Conservative
stop-first exits. This is NOT a replication of Bybit's proprietary AI.
"""
import json
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backtest import read_csv

INITIAL = 1000.0

def simulate(rows, *, fee=.008, spread_bps=5., slippage_bps=2.,
             start=240, stop_pct=.012, risk_fraction=.005, daily_limit=.02):
    if len(rows) < 300 or start < 240 or not (0 <= fee < .1):
        raise ValueError("insufficient data or invalid parameters")
    cash = INITIAL
    pos = None
    trades = []
    curve = [cash]
    daily_start = cash
    day = None
    blocked_days = 0
    rejected_costs = 0
    rejected_targets = 0
    last_exit = -30
    friction = spread_bps / 20000 + slippage_bps / 10000
    if friction < 0 or stop_pct <= 0 or risk_fraction <= 0 or daily_limit <= 0:
        raise ValueError("invalid costs or risk")
    for i in range(start, len(rows)-1):
        current, nxt = rows[i], rows[i+1]
        today = current[0].date()
        if today != day:
            day, daily_start = today, cash
        closes = [r[4] for r in rows[i-239:i+1]]
        high = [r[2] for r in rows[i-29:i+1]]
        low = [r[3] for r in rows[i-29:i+1]]
        tr = [max(high[k]-low[k],abs(high[k]-closes[-30+k-1]),abs(low[k]-closes[-30+k-1])) for k in range(1,30)]
        atr = sum(tr[-14:])/14
        reference = sum(closes[-60:])/60
        slow = sum(closes)/len(closes)
        # Range regime only: avoid directional moves that can break grids.
        ranging = abs(reference/slow-1) <= .008 and atr/current[4] <= .008
        grid_pct = max(.0025, min(.015, 1.8*atr/current[4]))
        # Do not enter when a mean-reversion exit cannot cover roundtrip
        # friction and a 1.5:1 net reward-to-risk requirement.
        roundtrip_cost = 2*(fee+friction)
        minimum_net_target = roundtrip_cost + 1.5*(stop_pct+roundtrip_cost)
        if pos:
            entry, qty, fee_in, opened, target = pos
            stop = entry*(1-stop_pct)
            # A bar can touch both stop and target: assume stop fills first.
            if i >= opened and current[3] <= stop:
                mid = min(stop,current[1])
            elif i >= opened and current[2] >= target:
                mid = target
            elif i-opened >= 120:
                mid = nxt[1]
            else:
                mid = None
            if mid is not None:
                exit_fill = mid*(1-friction)
                pnl = (exit_fill-entry)*qty-fee_in-exit_fill*qty*fee
                cash += pnl
                trades.append(pnl)
                pos = None
                last_exit = i
        if not pos and i-last_exit >= 15 and ranging and cash > 0:
            # Entry when price drops one adaptive grid spacing below 60m mean.
            if current[4] <= reference*(1-grid_pct) and cash > daily_start*(1-daily_limit):
                # A grid is not profitable merely because its price bounces.
                # Only consider exits near the observed mean; avoid assuming
                # an implausibly large future price move to pay commissions.
                projected_entry = nxt[1]*(1+friction)
                achievable_target = reference/projected_entry-1
                if grid_pct <= roundtrip_cost:
                    rejected_costs += 1
                    continue
                if achievable_target < minimum_net_target:
                    rejected_targets += 1
                    continue
                entry = projected_entry
                unit_risk = stop_pct+2*fee+2*friction
                notional = min(cash*.10, cash*risk_fraction/unit_risk)
                qty = notional/entry
                target = reference
                pos = (entry,qty,entry*qty*fee,i+1,target)
            elif cash <= daily_start*(1-daily_limit):
                blocked_days += 1
        marked = cash
        if pos:
            entry,qty,fee_in,opened,target=pos
            exit_fill = current[4]*(1-friction)
            marked += (exit_fill-entry)*qty-fee_in-exit_fill*qty*fee
        curve.append(marked)
    if pos:
        entry,qty,fee_in,_,_=pos
        exit_fill=rows[-1][4]*(1-friction)
        pnl=(exit_fill-entry)*qty-fee_in-exit_fill*qty*fee
        cash+=pnl
        trades.append(pnl)
        curve.append(cash)
    peak=INITIAL
    max_dd=0.
    for x in curve:
        peak=max(peak,x)
        max_dd=max(max_dd,(peak-x)/peak)
    wins=sum(p>0 for p in trades)
    return {"trades":len(trades),"wins":wins,
            "win_rate_pct":round(100*wins/len(trades),2) if trades else None,
            "net_pnl_eur":round(cash-INITIAL,4),
            "max_drawdown_pct":round(max_dd*100,4),
            "profit_factor":round(sum(x for x in trades if x>0)/-sum(x for x in trades if x<0),4) if any(x<0 for x in trades) else None,
            "blocked_daily_entries":blocked_days,
            "rejected_costs":rejected_costs,
            "rejected_targets":rejected_targets}

def main():
    rows=read_csv(sys.argv[1])
    split=int(len(rows)*.7)
    # Independent holdout is simulated separately from initial capital.
    out={}
    for name,fee in (("conservative_0_8pct_each_side",.008),
                     ("hypothetical_0_05pct_each_side",.0005)):
        out[name]={"development":simulate(rows[:split],fee=fee),
                   "untouched_holdout":simulate(rows[split:],fee=fee)}
    print(json.dumps({"strategy":"adaptive_grid_research_long_only",
                      "not_bybit_proprietary_ai":True,"results":out},indent=2))

if __name__=="__main__":
    main()
