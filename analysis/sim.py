"""Local simulator replicating sim/bars/engine.ts fill math exactly (single-hop pool).
Bars: o,c as ints at price_scale 5; qty_scale 8; quote_scale 6. Cash in micro-USDC.
Fill at next bar's open; buy: spend=notional*(10000-4)/10000; price=open*(10000+2)*m/10000
with m = 1 + spend*1e6 / D, D = o_depth[0]*1e6. qty = spend*10^(8+5)/(price*10^6).
Sell: m as above with value=qty valued at open; price = open*(10000-2)/(10000*m); gross=value(qty,price);
proceeds = gross*(10000-4)/10000. Final flatten at last close with same math, no max_slippage.
"""
import gzip, json, math

KIT = "/home/hatch/workspace/make-fun/kits/btc-race-24h-20261123-0511/btc-race-24h-20261123-0511-kit"
BARS = [json.loads(l) for l in gzip.open(f"{KIT}/dataset/bars/CBBTC.ndjson.gz", "rt")]
FEE, SLIP = 4, 2
START_CASH = 1_000_000_000  # micro-USDC

def value(qty, price):
    return (qty * price * 10**6) // 10**(8 + 5)

def buy_fill(notional, op, depth):
    spend = notional * (10000 - FEE) // 10000
    D = depth * 10**6
    # factor num/den = (D + spend*1e6)/D ; price = open*(10000+2)*num/(10000*den)
    price = (op * (10000 + SLIP) * (D + spend * 10**6)) // (10000 * D)
    qty = (spend * 10**(8 + 5)) // (price * 10**6)
    return qty, price, notional - spend

def sell_fill(qty, op, depth):
    D = depth * 10**6
    v = value(qty, op)
    # sell factor: price = open*(10000-2)*D/(10000*(D+v*1e6))
    price = (op * (10000 - SLIP) * D) // (10000 * (D + v * 10**6))
    if price < 1:
        price = 1
    gross = value(qty, price)
    proceeds = gross * (10000 - FEE) // 10000
    return proceeds, price, gross - proceeds

def simulate(decide, verbose=False):
    """decide(state) -> 'buy'|'sell'|None ; state has closes list, idx, cash, qty, entry_cost, peak.
    Orders decided on bar i fill at bar i+1 open. Returns dict of metrics."""
    cash = START_CASH
    qty = 0
    cost = 0  # cash spent on current position (incl fees)
    peak_equity = START_CASH
    max_dd = 0.0
    trades = 0
    fees = 0
    closes = [int(b["c"]) for b in BARS]
    opens = [int(b["o"]) for b in BARS]
    depths = [int(b["o_depth"][0]) for b in BARS]
    pending = None  # ('buy', notional) or ('sell',)
    entry_price = 0
    peak_since_entry = 0
    entry_idx = -1
    for i in range(len(BARS)):
        # fill pending order at this bar's open
        if pending is not None:
            if pending[0] == "buy":
                q, p, f = buy_fill(pending[1], opens[i], depths[i])
                qty, cost, entry_price = q, pending[1], p
                cash -= pending[1]
                fees += f
                trades += 1
                peak_since_entry = closes[i]
                entry_idx = i
            else:
                proc, p, f = sell_fill(qty, opens[i], depths[i])
                cash += proc
                fees += f
                trades += 1
                qty, cost = 0, 0
            pending = None
        # equity at close
        eq = cash + value(qty, closes[i])
        if eq > peak_equity:
            peak_equity = eq
        dd = (peak_equity - eq) / peak_equity
        if dd > max_dd:
            max_dd = dd
        if qty:
            peak_since_entry = max(peak_since_entry, closes[i])
        # decide on this close (fills next open); no decision on last bar
        if i < len(BARS) - 1:
            st = {"i": i, "closes": closes, "cash": cash, "qty": qty, "cost": cost,
                  "entry_price": entry_price, "peak": peak_since_entry, "entry_idx": entry_idx,
                  "equity": eq}
            act = decide(st)
            if act == "buy" and qty == 0 and cash >= 1_000_000:
                pending = ("buy", cash)  # full size
            elif act == "sell" and qty > 0:
                pending = ("sell",)
    # final flatten at last close
    if qty:
        proc, p, f = sell_fill(qty, closes[-1], int(BARS[-1]["c_depth"][0]))
        cash += proc
        fees += f
        qty = 0
    eq = cash
    if eq > peak_equity:
        peak_equity = eq
    dd = (peak_equity - eq) / peak_equity
    max_dd = max(max_dd, dd)
    return {"net_pnl_usd": (cash - START_CASH) / 1e6, "max_dd_pct": max_dd * 100,
            "trades": trades, "fees_usd": fees / 1e6, "final_cash": cash / 1e6}

def ema_series(closes, n):
    k = 2 / (n + 1)
    out = []
    e = None
    for c in closes:
        e = c if e is None else c * k + e * (1 - k)
        out.append(e)
    return out

def make_strategy(fast=12, slow=36, tp=None, trail=None, cooldown=0, gap_bps=0, time_stop=None):
    ef = ema_series([int(b["c"]) for b in BARS], fast)
    es = ema_series([int(b["c"]) for b in BARS], slow)
    last_exit = -10**9
    prev_cross = 0  # +1 fast above slow
    def decide(st):
        nonlocal last_exit, prev_cross
        i = st["i"]
        if i < slow:
            return None
        cross = 1 if ef[i] > es[i] else -1
        crossed_up = prev_cross <= 0 and cross > 0
        crossed_dn = prev_cross >= 0 and cross < 0
        prev_cross = cross
        gap = (ef[i] - es[i]) / es[i] * 10000
        if st["qty"] == 0:
            if crossed_up and gap >= gap_bps and i - last_exit >= cooldown:
                return "buy"
            return None
        # holding
        entry = st["entry_price"]
        c = st["closes"][i]
        if crossed_dn:
            last_exit = i
            return "sell"
        if tp is not None and c >= entry * (1 + tp):
            last_exit = i
            return "sell"
        if trail is not None and c <= st["peak"] * (1 - trail):
            last_exit = i
            return "sell"
        if time_stop is not None and i - st["entry_idx"] >= time_stop:
            last_exit = i
            return "sell"
        return None
    return decide

if __name__ == "__main__":
    import itertools
    best = []
    for fast, slow in [(8, 21), (8, 26), (12, 26), (12, 36), (6, 18), (10, 30), (12, 48), (5, 15)]:
        for tp in [None, 0.015, 0.025, 0.04]:
            for trail in [None, 0.008, 0.012, 0.02]:
                for cd in [0, 30]:
                    r = simulate(make_strategy(fast, slow, tp, trail, cd))
                    best.append((r["net_pnl_usd"], fast, slow, tp, trail, cd, r["max_dd_pct"], r["trades"]))
    best.sort(key=lambda x: x[0], reverse=True)
    for b in best[:15]:
        print("pnl $%7.2f fast=%d slow=%d tp=%s trail=%s cd=%d dd=%.2f%% trades=%d" % b)
    print("--- worst ---")
    for b in best[-3:]:
        print("pnl $%7.2f fast=%d slow=%d tp=%s trail=%s cd=%d dd=%.2f%% trades=%d" % b)
