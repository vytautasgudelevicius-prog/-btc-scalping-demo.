"""Kraken spot BTC/EUR economics. Research only; no authenticated orders.
Public schedule examples are assumptions until actual account tier is verified.
"""
import json

# Entry and exit fee rates as fractions of notional. Spread is full bid-ask width.
SCENARIOS={
 "tier1_taker_taker":(.008,.008),
 "tier1_maker_taker":(.004,.008),
 "tier1_maker_maker":(.004,.004),
 "tier2_taker_taker":(.006,.006),
 "tier3_taker_taker":(.0038,.0038),
}
def required_gross_move(entry_fee,exit_fee,spread_bps=5,slippage_bps_each=2):
    if min(entry_fee,exit_fee,spread_bps,slippage_bps_each)<0:
        raise ValueError("Negative trading costs")
    # Buy ask plus slippage, sell bid minus slippage.
    spread=spread_bps/10000
    slip=slippage_bps_each/10000
    buy_multiplier=(1+spread/2)*(1+slip)*(1+entry_fee)
    sell_multiplier=(1-spread/2)*(1-slip)*(1-exit_fee)
    if sell_multiplier<=0: raise ValueError("Invalid exit cost")
    return buy_multiplier/sell_multiplier-1

def analyze(spread_bps=5,slippage_bps_each=2,expected_move_pct=None):
    out={}
    for name,(entry,exit_fee) in SCENARIOS.items():
        threshold=required_gross_move(entry,exit_fee,spread_bps,slippage_bps_each)
        out[name]={"entry_fee_pct":round(entry*100,4),
                   "exit_fee_pct":round(exit_fee*100,4),
                   "break_even_gross_move_pct":round(threshold*100,5),
                   "net_if_gross_move_pct":(round(100*((1+expected_move_pct/100)/(1+threshold)-1),5)
                                             if expected_move_pct is not None else None)}
    return {"pair":"BTC/EUR","mode":"SPOT_LONG_ONLY","assumed_full_spread_bps":spread_bps,
            "assumed_slippage_bps_each":slippage_bps_each,
            "scenarios":out,"decision":"RESEARCH_ONLY",
            "warning":"Maker execution and adverse selection not modeled; account fee tier unverified. No SHORT borrowing or financing. No orders."}

if __name__=="__main__":
    print(json.dumps(analyze(),indent=2))
