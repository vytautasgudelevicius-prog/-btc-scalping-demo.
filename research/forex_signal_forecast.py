"""Research-only forecast of possible EUR/USD scalp signals.

Only completed 1-minute candles are used. ETA is a scenario estimate, not
a prediction of the future, a calibrated probability, or an order.
"""
from statistics import mean

def forecast_signal(bars, *, spread_pips=1.0, slippage_pips=.2,
                    commission_eur_per_100k_side=3.5):
    if len(bars) < 60:
        return {"status":"WAIT","reason":"insufficient_history","eta_minutes":None}
    from research.forex_eurusd_backtest import scalp_market_gate
    i=len(bars)-1
    ok,reason,vol=scalp_market_gate(
        bars,i,spread_pips=spread_pips,slippage_pips=slippage_pips,
        commission_eur_per_100k_side=commission_eur_per_100k_side)
    if not ok:
        return {"status":"WAIT","reason":reason,"eta_minutes":None}
    closes=[b[4] for b in bars[-50:]]
    fast=mean(closes[-20:])
    slow=mean(closes)
    last=closes[-1]
    direction="LONG" if fast>slow*1.00015 else "SHORT" if fast<slow*.99985 else None
    if direction is None:
        return {"status":"WAIT","reason":"no_directional_setup","eta_minutes":None}
    # Candidate entry trigger is a fresh 10-bar high/low breakout.
    trigger=max(b[2] for b in bars[-11:-1]) if direction=="LONG" else min(b[3] for b in bars[-11:-1])
    distance_pips=max(0,(trigger-last)/.0001) if direction=="LONG" else max(0,(last-trigger)/.0001)
    # Use recent realized absolute close-to-close motion, not future candles.
    pace_pips=mean(abs(closes[j]-closes[j-1])/.0001 for j in range(-10,0))
    if pace_pips<.1:
        return {"status":"WAIT","reason":"low_momentum","eta_minutes":None}
    eta=max(1,min(30,round(distance_pips/pace_pips)))
    return {"status":"WATCH","direction":direction,"eta_minutes":eta,
            "trigger_price":round(trigger,5),"distance_pips":round(distance_pips,2),
            "reason":"possible_breakout_not_confirmed",
            "confidence":"uncalibrated","order_allowed":False}

if __name__=="__main__":
    import json,sys
    from research.forex_eurusd_backtest import load_bars
    print(json.dumps(forecast_signal(load_bars(sys.argv[1])),indent=2))
