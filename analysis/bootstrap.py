"""Bootstrap robustness: shuffle 1h blocks of 1-min log returns, rebuild price paths,
evaluate candidate strategies on 200 resampled windows. Also evaluate on the real dev window."""
import sys, random, math
sys.path.insert(0, "/home/hatch/workspace/make-fun-entries/btc-race-24h-20261123-0511")
import sim
from sim import BARS, ema_series

closes = [int(b["c"]) for b in BARS]
opens = [int(b["o"]) for b in BARS]
depths = [int(b["o_depth"][0]) for b in BARS]

# Build log-return blocks of 60 bars
rets = [math.log(closes[i+1]/closes[i]) for i in range(len(closes)-1)]
blocks = [rets[i:i+60] for i in range(0, len(rets), 60)]
# depth blocks aligned to bars
depth_blocks = [depths[i:i+60] for i in range(0, len(depths), 60)]

def make_window(rng):
    order = list(range(len(blocks)))
    rng.shuffle(order)
    r = []
    d = []
    for b in order:
        r.extend(blocks[b])
        d.extend(depth_blocks[b])
    # rebuild closes from start price
    cs = [closes[0]]
    for x in r:
        cs.append(int(cs[-1] * math.exp(x)))
    # opens: use previous close (approx; open of bar i+1 ~ close of bar i is fine for sim)
    os_ = [cs[0]] + cs[:-1]
    return cs, os_, d[:len(cs)]

# monkeypatch sim.BARS-dependent globals by re-implementing simulate with injected series
from sim import buy_fill, sell_fill, value, START_CASH

def simulate_on(cs, os_, ds, decide):
    cash = START_CASH; qty = 0; cost = 0
    peak_equity = START_CASH; max_dd = 0.0; trades = 0
    pending = None; entry_price = 0; peak_since_entry = 0; entry_idx = -1
    for i in range(len(cs)):
        if pending is not None:
            if pending[0] == "buy":
                q, p, f = buy_fill(pending[1], os_[i], ds[i])
                qty, cost, entry_price = q, pending[1], p
                cash -= pending[1]; trades += 1
                peak_since_entry = cs[i]; entry_idx = i
            else:
                proc, p, f = sell_fill(qty, os_[i], ds[i])
                cash += proc; trades += 1; qty, cost = 0, 0
            pending = None
        eq = cash + value(qty, cs[i])
        peak_equity = max(peak_equity, eq)
        max_dd = max(max_dd, (peak_equity - eq) / peak_equity)
        if qty:
            peak_since_entry = max(peak_since_entry, cs[i])
        if i < len(cs) - 1:
            st = {"i": i, "closes": cs, "cash": cash, "qty": qty, "cost": cost,
                  "entry_price": entry_price, "peak": peak_since_entry, "entry_idx": entry_idx,
                  "equity": eq}
            act = decide(st)
            if act == "buy" and qty == 0 and cash >= 1_000_000:
                pending = ("buy", cash)
            elif act == "sell" and qty > 0:
                pending = ("sell",)
    if qty:
        proc, p, f = sell_fill(qty, cs[-1], ds[-1])
        cash += proc; qty = 0
    eq = cash
    peak_equity = max(peak_equity, eq)
    max_dd = max(max_dd, (peak_equity - eq) / peak_equity)
    return (cash - START_CASH) / 1e6, max_dd * 100, trades

def strat_factory(kind, fast=8, slow=60, tp=0.035, trail=0.015, maxT=1):
    def make(cs):
        ef = ema_series(cs, fast)
        es = ema_series(cs, slow)
        entered_rounds = 0
        last_exit = -10**9
        prev = 0
        def decide(st):
            nonlocal entered_rounds, last_exit, prev
            i = st["i"]
            if i < slow:
                return None
            cross = 1 if ef[i] > es[i] else -1
            up = prev <= 0 and cross > 0
            dn = prev >= 0 and cross < 0
            prev = cross
            if st["qty"] == 0:
                if up and entered_rounds < maxT and i - last_exit >= 30:
                    entered_rounds += 1
                    return "buy"
                return None
            c = st["closes"][i]
            if dn:
                last_exit = i; return "sell"
            if tp is not None and c >= st["entry_price"] * (1 + tp):
                last_exit = i; return "sell"
            if trail is not None and c <= st["peak"] * (1 - trail):
                last_exit = i; return "sell"
            return None
        return decide
    return make

def bh(cs):
    def decide(st):
        if st["i"] == 0 and st["qty"] == 0:
            return "buy"
        return None
    return decide

if __name__ == "__main__":
    rng = random.Random(12345)
    cands = {
        "B&H": lambda cs: bh(cs),
        "single EMA8/60 TP3.5 trail1.5": strat_factory("x", 8, 60, 0.035, 0.015, 1),
        "multi EMA8/60 TP3.5 trail1.5 maxT3": strat_factory("x", 8, 60, 0.035, 0.015, 3),
        "single EMA8/60 TP2 trail1.5": strat_factory("x", 8, 60, 0.02, 0.015, 1),
        "single EMA8/60 TP5 trail2": strat_factory("x", 8, 60, 0.05, 0.02, 1),
        "single EMA8/60 noTP trail1.5": strat_factory("x", 8, 60, None, 0.015, 1),
    }
    N = 200
    windows = [make_window(rng) for _ in range(N)]
    for name, fac in cands.items():
        pnls = []
        dds = []
        for cs, os_, ds in windows:
            p, dd, tr = simulate_on(cs, os_, ds, fac(cs))
            pnls.append(p); dds.append(dd)
        pnls.sort()
        print("%-38s dev-check median $%6.2f  p10 $%6.2f  p90 $%6.2f  P(>0)=%.2f  medDD %.2f%%" % (
            name, pnls[N//2], pnls[N//10], pnls[9*N//10],
            sum(1 for p in pnls if p > 0)/N, sorted(dds)[N//2]))
    # real dev window numbers for the same candidates
    print("--- real dev window ---")
    for name, fac in cands.items():
        p, dd, tr = simulate_on(closes, opens, depths, fac(closes))
        print("%-38s pnl $%6.2f dd %.2f%% trades %d" % (name, p, dd, tr))
