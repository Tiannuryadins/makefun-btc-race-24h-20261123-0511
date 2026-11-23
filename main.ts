// Single-Ride Trend Bot — btc-race-24h-20261123-0511.
//
// Strategy, long only, one round trip at most:
//   - Build EMA(8) and EMA(60) of the 1-minute closes (float64, seeded with the
//     first close). Enter, full cash, the first time EMA(8) crosses above
//     EMA(60): the trend is confirmed up, so the bot does not buy into a
//     falling market at the open.
//   - Exit the whole position when the close reaches +3.5% above the entry
//     fill price (take profit: lock in a strong day), or when the close falls
//     2.5% below the highest close since entry (trailing stop: cap the loss
//     if the race window turns into a rout). A 2.5% trail is wide on purpose:
//     1-minute noise is ~8 bps, so it only fires on a real reversal.
//   - Fallback: if no cross ever fires by the 1001st scored bar, buy anyway,
//     so the entry still makes at least one trade and meets the race
//     guardrail instead of sitting in cash for a whole down day.
//   - No re-entry after an exit: on the dev window every re-entry in the
//     flat second half paid ~26 bps a round trip and gave the edge back.
//     One clean ride beats chopping.
//
// Sizing and costs: a full-size round trip pays ~26 bps (4 bps fee + 2 bps
// modelled slippage + ~7 bps price impact each way at the frozen depth), so
// the +3.5% take-profit target is ~13x the round-trip cost. Orders cap their
// slippage at 100 bps past the close they were decided on; a refused order
// is retried on the next bar while its reason still holds.
//
// Deterministic: no clock, no environment, no randomness; the same bars
// give the same orders, run after run. Only the standard library (via the
// kit's vendor shim) is used.

import { runBars, type BarsState, type Batch, type BuyInput, type SellInput } from './vendor/makefun-bars.ts';

const SYMBOL = 'CBBTC';
const FAST_BARS = 8;
const SLOW_BARS = 60;
const TAKE_PROFIT_NUM = 1035n; // +3.5% over the entry fill price
const TAKE_PROFIT_DEN = 1000n;
const TRAIL_NUM = 975n; // -2.5% below the highest close since entry
const TRAIL_DEN = 1000n;
const FALLBACK_BAR = 1000; // 0-based index of the scored bar for the fallback buy
const MAX_SLIPPAGE_BPS = 100;

const fastK = 2 / (FAST_BARS + 1);
const slowK = 2 / (SLOW_BARS + 1);

let fastEma: number | null = null;
let slowEma: number | null = null;
/** Whether EMA(8) was above EMA(60) on the last evaluated bar. Starts false,
 *  like the backtest: the first evaluated bar (index 60) buys when the trend
 *  is up, whatever the unobserved crosses before it were. */
let prevFastAboveSlow = false;
/** Scored bars seen (warm-up batches excluded); the fallback counts these. */
let scoredBars = 0;
/** True once a buy fill has landed; after the round trip ends, no re-entry. */
let entered = false;
/** True once the entry signal has fired (cross or fallback); the buy is then
 *  sent (and retried if refused) until its fill lands. */
let entryDecided = false;
/** The entry fill price, from the batch that reports the buy fill. */
let entryPrice: bigint | null = null;
/** Highest close seen while holding the position. */
let peakClose: bigint | null = null;
/** A sell is pending until the position is empty (refused sells are retried). */
let exitWanted = false;

function pushClose(c: number): void {
  fastEma = fastEma === null ? c : c * fastK + fastEma * (1 - fastK);
  slowEma = slowEma === null ? c : c * slowK + slowEma * (1 - slowK);
}

await runBars({
  onBatch(state: BarsState, batch: Batch) {
    // Learn the entry fill price from the fills this batch reports.
    for (const bar of batch.bars) {
      if (bar.symbol !== SYMBOL) continue;
      pushClose(Number(bar.c));
      if (!state.warmingUp) scoredBars++;
    }
    for (const f of batch.fills) {
      if (f.symbol === SYMBOL && f.side === 'buy' && f.status === 'filled') {
        entryPrice = BigInt(f.price);
        peakClose = null;
        entered = true;
      }
    }

    const held = state.positions.get(SYMBOL);
    const close = state.close(SYMBOL);
    if (close !== null && held !== undefined) {
      if (peakClose === null || close > peakClose) peakClose = close;
    }

    if (state.warmingUp) return [];

    // --- exit: whole position on take-profit or trailing stop ---
    if (held !== undefined) {
      if (entryPrice !== null && close !== null && peakClose !== null) {
        const atTakeProfit = close * TAKE_PROFIT_DEN >= entryPrice * TAKE_PROFIT_NUM;
        const atTrailStop = close * TRAIL_DEN <= peakClose * TRAIL_NUM;
        if (atTakeProfit || atTrailStop) exitWanted = true;
      }
      if (exitWanted) {
        return [{ side: 'sell', symbol: SYMBOL, qty: held.qty, max_slippage_bps: MAX_SLIPPAGE_BPS } satisfies SellInput];
      }
      return [];
    }
    // Position is empty now: a wanted exit has landed.
    exitWanted = false;

    // --- entry: one round trip only. A buy refused by the market is retried
    //     on the next bar; once a buy has filled, there is no second entry. ---
    if (entered) return [];
    // No signal before the slow EMA has SLOW_BARS of history: a cross on the
    // first bars is just the seeding, not a trend.
    if (scoredBars <= SLOW_BARS) return [];
    if (!entryDecided) {
      const fastAboveSlow = (fastEma as number) > (slowEma as number);
      const crossedUp = !prevFastAboveSlow && fastAboveSlow;
      prevFastAboveSlow = fastAboveSlow;
      if (crossedUp || scoredBars > FALLBACK_BAR) entryDecided = true;
    }
    if (entryDecided) {
      const cash = state.cash;
      if (cash < BigInt(state.hello.fees.min_notional_quote_units)) return [];
      return [{ side: 'buy', symbol: SYMBOL, notional_quote_units: cash, max_slippage_bps: MAX_SLIPPAGE_BPS } satisfies BuyInput];
    }
    return [];
  },
});
