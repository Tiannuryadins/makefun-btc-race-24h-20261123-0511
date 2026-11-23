"""Sweep 3: single-entry riders - enter once on confirmation, hold with trailing stop / TP."""
import sys
sys.path.insert(0, "/home/hatch/workspace/make-fun-entries/btc-race-24h-20261123-0511")
from sim import simulate, BARS, ema_series

closes = [int(b["c"]) for b in BARS]

def make_single(entry="ema", fast=8, slow=60, trail=0.02, tp=None, mom_n=24, mom_min=0.0):
    ef = ema_series(closes, fast)
    es = ema_series(closes, slow)
    entered = False
    prev = 0
    def decide(st):
        nonlocal entered, prev
        i = st["i"]
        if st["qty"] == 0:
            if entered or i < slow:
                return None
            if entry == "ema":
                cross = 1 if ef[i] > es[i] else -1
                up = prev <= 0 and cross > 0
                prev = cross
                if up:
                    entered = True
                    return "buy"
            elif entry == "momentum":
                if i >= mom_n and closes[i] / closes[i - mom_n] - 1 > mom_min:
                    entered = True
                    return "buy"
            elif entry == "immediate":
                if i >= 1:
                    entered = True
                    return "buy"
            return None
        c = st["closes"][i]
        if tp is not None and c >= st["entry_price"] * (1 + tp):
            return "sell"
        if c <= st["peak"] * (1 - trail):
            return "sell"
        return None
    return decide

if __name__ == "__main__":
    rows = []
    for entry in ["ema", "momentum", "immediate"]:
        for trail in [0.01, 0.015, 0.02, 0.03, 0.05, 1.0]:
            for tp in [None, 0.02, 0.035, 0.05]:
                r = simulate(make_single(entry, 8, 60, trail, tp))
                rows.append((r["net_pnl_usd"], f"single entry={entry} trail={trail} tp={tp}", r["max_dd_pct"], r["trades"]))
    for mom_min in [0.0, 0.002, 0.005]:
        for trail in [0.02, 0.03, 1.0]:
            for tp in [None, 0.035]:
                r = simulate(make_single("momentum", 8, 60, trail, tp, 24, mom_min))
                rows.append((r["net_pnl_usd"], f"single momentum min={mom_min} trail={trail} tp={tp}", r["max_dd_pct"], r["trades"]))
    rows.sort(key=lambda x: x[0], reverse=True)
    for p, name, dd, tr in rows[:20]:
        print("pnl $%7.2f dd=%.2f%% trades=%d  %s" % (p, dd, tr, name))
