"""Sweep 4: final tuning - TP level, EMA lengths, fallback entry."""
import sys, random
sys.path.insert(0, "/home/hatch/workspace/make-fun-entries/btc-race-24h-20261123-0511")
from sim import BARS, ema_series
from bootstrap import make_window, simulate_on
from bootstrap2 import strat

closes = [int(b["c"]) for b in BARS]
opens = [int(b["o"]) for b in BARS]
depths = [int(b["o_depth"][0]) for b in BARS]

def strat_fb(cs, fast=8, slow=60, tp=0.035, trail=0.025, fallback_bar=None):
    ef = ema_series(cs, fast)
    es = ema_series(cs, slow)
    entered = False
    prev = 0
    def decide(st):
        nonlocal entered, prev
        i = st["i"]
        if st["qty"] == 0:
            if entered:
                return None
            if i >= slow:
                cross = 1 if ef[i] > es[i] else -1
                up = prev <= 0 and cross > 0
                prev = cross
                if up:
                    entered = True
                    return "buy"
            if fallback_bar is not None and i >= fallback_bar:
                entered = True
                return "buy"
            return None
        c = st["closes"][i]
        if tp is not None and c >= st["entry_price"] * (1 + tp):
            return "sell"
        if trail is not None and c <= st["peak"] * (1 - trail):
            return "sell"
        return None
    return decide

if __name__ == "__main__":
    rng = random.Random(999)
    N = 200
    windows = [make_window(rng) for _ in range(N)]
    cands = {
        "TP3.5 trail2.5": lambda cs: strat_fb(cs, 8, 60, 0.035, 0.025),
        "TP3.5 noTrail": lambda cs: strat_fb(cs, 8, 60, 0.035, None),
        "TP2.5 trail2.5": lambda cs: strat_fb(cs, 8, 60, 0.025, 0.025),
        "TP5 trail2.5": lambda cs: strat_fb(cs, 8, 60, 0.05, 0.025),
        "noTP trail2.5": lambda cs: strat_fb(cs, 8, 60, None, 0.025),
        "TP3.5 trail2.5 f12/60": lambda cs: strat_fb(cs, 12, 60, 0.035, 0.025),
        "TP3.5 trail2.5 f8/120": lambda cs: strat_fb(cs, 8, 120, 0.035, 0.025),
        "TP3.5 trail2.5 fb1000": lambda cs: strat_fb(cs, 8, 60, 0.035, 0.025, 1000),
        "TP3.5 trail2.5 fb720": lambda cs: strat_fb(cs, 8, 60, 0.035, 0.025, 720),
    }
    for name, fac in cands.items():
        pnls = []
        ntrades0 = 0
        for cs, os_, ds in windows:
            p, dd, tr = simulate_on(cs, os_, ds, fac(cs))
            pnls.append(p)
            if tr == 0:
                ntrades0 += 1
        pnls.sort()
        p, dd, tr = simulate_on(closes, opens, depths, fac(closes))
        print("%-28s boot med $%6.2f p10 $%6.2f P(>0)=%.2f zeroTrade=%d | dev $%6.2f dd %.2f%% tr %d" % (
            name, pnls[N//2], pnls[N//10], sum(1 for x in pnls if x > 0)/N, ntrades0, p, dd, tr))
    # first-cross timing on dev for EMA 8/60
    ef = ema_series(closes, 8); es = ema_series(closes, 60)
    for i in range(60, 300):
        if ef[i] > es[i] and ef[i-1] <= es[i-1]:
            print("first EMA8>EMA60 cross on dev at bar", i)
            break
