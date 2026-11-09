"""Research-only EUR/USD FOREX scalp backtest; no broker orders.

Input CSV columns: timestamp,open,high,low,close (UTC ISO timestamps).
Bid/ask spread and slippage are charged on both entry and exit.
Use broker-quality bid/ask historical quotes before making deployment claims.
"""
import csv
import json
import sys
from datetime import datetime, timezone

INITIAL_EUR = 100.0

def load_bars(path):
    with open(path, newline="") as f:
        data = list(csv.DictReader(f))
    bars = []
    for row in data:
        t = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
        if t.tzinfo is None:
            raise ValueError("timestamps must include UTC offset")
        values = tuple(float(row[k]) for k in ("open", "high", "low", "close"))
        if min(values) <= 0 or values[1] < max(values[0], values[3]) or values[2] > min(values[0], values[3]):
            raise ValueError("invalid OHLC")
        bars.append((t.astimezone(timezone.utc), *values))
    if any(bars[i][0] >= bars[i+1][0] for i in range(len(bars)-1)):
        raise ValueError("bars must be strictly chronological")
    return bars

def simulate(bars, *, spread_pips=1.0, slippage_pips=0.2, commission_eur_per_100k_side=3.5):
    if len(bars) < 300 or min(spread_pips, slippage_pips, commission_eur_per_100k_side) < 0:
        raise ValueError("insufficient bars or invalid costs")
    cash = INITIAL_EUR
    position = None
    trades = []
    curve = [cash]
    rejected_costs = 0
    last_exit = -20
    consecutive_losses = 0
    day = None
    day_start = cash
    halted_days = set()
    max_positions = 1
    # EUR/USD: one pip is 0.0001 USD per EUR.
    pip = .0001
    for i in range(200, len(bars)-1):
        now, nxt = bars[i], bars[i+1]
        today = now[0].date()
        if today != day:
            day = today
            day_start = cash
            consecutive_losses = 0
        if cash <= day_start*.98 or consecutive_losses >= 5:
            halted_days.add(today)
        closes = [b[4] for b in bars[i-49:i+1]]
        mean_fast = sum(closes[-20:])/20
        mean_slow = sum(closes)/50
        # Completed bar determines direction, next bar open determines fill.
        direction = 1 if mean_fast > mean_slow * 1.00015 else -1 if mean_fast < mean_slow * .99985 else 0
        # Avoid weekends, and only trade liquid London/NY overlap (UTC).
        if position is None and direction and now[0].weekday() < 5 and 12 <= now[0].hour < 16 and i-last_exit >= 10 and today not in halted_days:
            entry_mid = nxt[1]
            stop_pips = max(8.0, (max(b[2] for b in bars[i-13:i+1]) - min(b[3] for b in bars[i-13:i+1])) / pip)
            take_pips = 2.0*stop_pips
            # Roundtrip friction, in pips, including USD-to-EUR conversion for commissions.
            roundtrip_pips = spread_pips + 2*slippage_pips + 2*commission_eur_per_100k_side*entry_mid/10
            if take_pips <= roundtrip_pips + 1.5*(stop_pips + roundtrip_pips):
                rejected_costs += 1
                continue
            risk_eur = cash*.005
            # EUR base notional capped at 1x equity; no leverage assumed.
            units = min(cash, risk_eur*entry_mid/(stop_pips*pip + roundtrip_pips*pip))
            position = (direction, entry_mid, units, i+1, stop_pips, take_pips)
        if position and i >= position[3]:
            side, entry, units, opened, stop, take = position
            # Conservative stop-first when both levels occur in the same candle.
            stop_mid = entry-side*stop*pip
            take_mid = entry+side*take*pip
            hit_stop = now[3] <= stop_mid if side == 1 else now[2] >= stop_mid
            hit_take = now[2] >= take_mid if side == 1 else now[3] <= take_mid
            exit_mid = (min(stop_mid,now[1]) if side==1 else max(stop_mid,now[1])) if hit_stop else take_mid if hit_take else nxt[1] if i-opened >= 60 else None
            if exit_mid is not None:
                gross_eur = side*(exit_mid-entry)*units/exit_mid
                spread_slip_eur = units*(spread_pips+2*slippage_pips)*pip/exit_mid
                commissions = 2*commission_eur_per_100k_side*units/100000
                pnl = gross_eur-spread_slip_eur-commissions
                cash += pnl
                trades.append(pnl)
                consecutive_losses = consecutive_losses+1 if pnl < 0 else 0
                if cash <= day_start*.98 or consecutive_losses >= 5:
                    halted_days.add(today)
                position = None
                last_exit = i
        curve.append(cash)
    if position:
        side, entry, units, _, _, _ = position
        exit_mid = bars[-1][4]
        pnl = side*(exit_mid-entry)*units/exit_mid-units*(spread_pips+2*slippage_pips)*pip/exit_mid-2*commission_eur_per_100k_side*units/100000
        cash += pnl
        trades.append(pnl)
        curve.append(cash)
    peak = INITIAL_EUR
    dd = 0.0
    for v in curve:
        peak = max(peak,v)
        dd = max(dd,(peak-v)/peak)
    return {"trades":len(trades),"net_pnl_eur":round(cash-INITIAL_EUR,4),
            "win_rate_pct":round(100*sum(x>0 for x in trades)/len(trades),2) if trades else None,
            "max_drawdown_pct":round(100*dd,4),"rejected_costs":rejected_costs,
            "initial_capital_eur":INITIAL_EUR,"daily_loss_limit_eur":2.0,
            "risk_per_trade_eur_initial":0.5,"max_consecutive_losses":5,"halted_days":len(halted_days),
            "max_simultaneous_positions":max_positions,
            "status":"RESEARCH_ONLY_NO_BROKER_ORDERS"}

if __name__ == "__main__":
    bars = load_bars(sys.argv[1])
    split = int(len(bars)*.7)
    print(json.dumps({"pair":"EUR/USD","development":simulate(bars[:split]),
                      "untouched_holdout":simulate(bars[split:])},indent=2))
