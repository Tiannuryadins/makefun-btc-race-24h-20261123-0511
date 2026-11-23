"""Sweep 2: few-trade trend riders. Reuses sim.py engine."""
import sys
sys.path.insert(0, "/home/hatch/workspace/make-fun-entries/btc-race-24h-20261123-0511")
from sim import simulate, BARS, ema_series

closes = [int(b["c"]) for b in BARS]

def make_breakout(n=60, trail=0.015, ema_n=60, max_trades=3, tp=None, cooldown=0):
    es = ema_series(closes, ema_n)
    last_exit = -10**9
    n_trades = 0
    def decide(st):
        nonlocal last_exit, n_trades
        i = st["i"]
        if i < n:
            return None
        if st["qty"] == 0:
            if n_trades >= max_trades or i - last_exit < cooldown:
                return None
            # breakout: close above max close of prior n bars and above EMA
            if st["closes"][i] > max(st["closes"][i-n:i]) and st["closes"][i] > es[i]:
                n_trades += 1
                return "buy"
            return None
        c = st["closes"][i]
        if tp is not None and c >= st["entry_price"] * (1 + tp):
            last_exit = i
            return "sell"
        if c <= st["peak"] * (1 - trail):
            last_exit = i
            return "sell"
        if c < es[i]:  # trend broken
            last_exit = i
            return "sell"
        return None
    return decide

def make_ema_hold(fast=12, slow=60, trail=0.015, tp=None, max_trades=3, gap_bps=5):
    ef = ema_series(closes, fast)
    es = ema_series(closes, slow)
    last_exit = -10**9
    n_trades = 0
    prev = 0
    def decide(st):
        nonlocal last_exit, n_trades, prev
        i = st["i"]
        if i < slow:
            return None
        cross = 1 if ef[i] > es[i] else -1
        up = prev <= 0 and cross > 0
        dn = prev >= 0 and cross < 0
        prev = cross
        gap = (ef[i] - es[i]) / es[i] * 10000
        if st["qty"] == 0:
            if up and gap >= gap_bps and n_trades < max_trades and i - last_exit >= 30:
                n_trades += 1
                return "buy"
            return None
        c = st["closes"][i]
        if dn:
            last_exit = i
            return "sell"
        if tp is not None and c >= st["entry_price"] * (1 + tp):
            last_exit = i
            return "sell"
        if c <= st["peak"] * (1 - trail):
            last_exit = i
            return "sell"
        return None
    return decide

if __name__ == "__main__":
    rows = []
    for n in [20, 30, 60, 120]:
        for trail in [0.008, 0.015, 0.025, 0.04]:
            for mt in [1, 2, 3]:
                for tp in [None, 0.02, 0.035]:
                    r = simulate(make_breakout(n, trail, 60, mt, tp))
                    rows.append((r["net_pnl_usd"], f"breakout n={n} trail={trail} maxT={mt} tp={tp}", r["max_dd_pct"], r["trades"]))
    for fast, slow in [(12, 60), (8, 60), (12, 120), (6, 60)]:
        for trail in [0.015, 0.025, 0.04]:
            for tp in [None, 0.02, 0.035]:
                for gap in [0, 5, 15]:
                    r = simulate(make_ema_hold(fast, slow, trail, tp, 3, gap))
                    rows.append((r["net_pnl_usd"], f"emahold f={fast} s={slow} trail={trail} tp={tp} gap={gap}", r["max_dd_pct"], r["trades"]))
    rows.sort(key=lambda x: x[0], reverse=True)
    for p, name, dd, tr in rows[:20]:
        print("pnl $%7.2f dd=%.2f%% trades=%d  %s" % (p, dd, tr, name))
