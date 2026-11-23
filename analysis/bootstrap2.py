"""Bootstrap v2: corrected exits (TP / trailing stop only, no cross-down exit).
Strategies: entry on first EMA8>EMA60 cross; exit TP and/or trail; optional re-entry on
fresh breakout above prior exit price. Also B&H and momentum-baseline style for reference."""
import sys, random, math
sys.path.insert(0, "/home/hatch/workspace/make-fun-entries/btc-race-24h-20261123-0511")
from sim import BARS, ema_series
from bootstrap import make_window, simulate_on

closes = [int(b["c"]) for b in BARS]
opens = [int(b["o"]) for b in BARS]
depths = [int(b["o_depth"][0]) for b in BARS]

def strat(cs, fast=8, slow=60, tp=0.035, trail=0.015, maxT=1, reentry="none"):
    ef = ema_series(cs, fast)
    es = ema_series(cs, slow)
    rounds = 0
    last_exit = -10**9
    last_exit_price = 0
    prev = 0
    def decide(st):
        nonlocal rounds, last_exit, last_exit_price, prev
        i = st["i"]
        if i < slow:
            return None
        cross = 1 if ef[i] > es[i] else -1
        up = prev <= 0 and cross > 0
        prev = cross
        if st["qty"] == 0:
            if rounds >= maxT or i - last_exit < 30:
                return None
            if rounds == 0:
                if up:
                    rounds += 1
                    return "buy"
            else:
                if reentry == "breakout" and st["closes"][i] > last_exit_price * 1.002 and up:
                    rounds += 1
                    return "buy"
                if reentry == "dip" and st["closes"][i] <= es[i] * 1.003 and up:
                    rounds += 1
                    return "buy"
            return None
        c = st["closes"][i]
        if tp is not None and c >= st["entry_price"] * (1 + tp):
            last_exit = i; last_exit_price = c
            return "sell"
        if trail is not None and c <= st["peak"] * (1 - trail):
            last_exit = i; last_exit_price = c
            return "sell"
        return None
    return decide

def bh(cs):
    def decide(st):
        if st["i"] == 0 and st["qty"] == 0:
            return "buy"
        return None
    return decide

if __name__ == "__main__":
    rng = random.Random(777)
    cands = {
        "B&H": lambda cs: bh(cs),
        "single TP3.5 trail1.5": lambda cs: strat(cs, 8, 60, 0.035, 0.015, 1),
        "single TP3.5 trail2.5": lambda cs: strat(cs, 8, 60, 0.035, 0.025, 1),
        "single TP3.5 noTrail": lambda cs: strat(cs, 8, 60, 0.035, None, 1),
        "single TP2 trail1.5": lambda cs: strat(cs, 8, 60, 0.02, 0.015, 1),
        "single noTP trail1.5": lambda cs: strat(cs, 8, 60, None, 0.015, 1),
        "reentry-breakout TP3.5 trail1.5 maxT3": lambda cs: strat(cs, 8, 60, 0.035, 0.015, 3, "breakout"),
        "reentry-dip TP3.5 trail1.5 maxT3": lambda cs: strat(cs, 8, 60, 0.035, 0.015, 3, "dip"),
    }
    N = 200
    windows = [make_window(rng) for _ in range(N)]
    for name, fac in cands.items():
        pnls = []
        for cs, os_, ds in windows:
            p, dd, tr = simulate_on(cs, os_, ds, fac(cs))
            pnls.append(p)
        pnls.sort()
        print("%-38s median $%6.2f p10 $%6.2f p90 $%6.2f P(>0)=%.2f" % (
            name, pnls[N//2], pnls[N//10], pnls[9*N//10], sum(1 for p in pnls if p > 0)/N))
    print("--- real dev window ---")
    for name, fac in cands.items():
        p, dd, tr = simulate_on(closes, opens, depths, fac(closes))
        print("%-38s pnl $%6.2f dd %.2f%% trades %d" % (name, p, dd, tr))
