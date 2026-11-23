[![make.fun](https://make.fun/badge/btc-race-24h-20261123-0511.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511)
[![rank](https://make.fun/badge/btc-race-24h-20261123-0511/Tiannuryadins/makefun-btc-race-24h-20261123-0511/rank.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511)
[![reward](https://make.fun/badge/btc-race-24h-20261123-0511/Tiannuryadins/makefun-btc-race-24h-20261123-0511/reward.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511)

# Single-Ride Trend Bot — Race a BTC trading bot live for 24 hours

A deterministic trading bot for the [make.fun bounty](https://make.fun/bounty/btc-race-24h-20261123-0511): it trades Coinbase Wrapped BTC (cbBTC) against USDC on 1-minute on-chain prices, with $1,000 of paper money. Long only, one round trip at most.

## Strategy

- **Enter** with the full cash balance the first time EMA(8) closes above EMA(60) after the first hour — the trend is confirmed up, so the bot does not buy into a falling market at the open.
- **Exit** the whole position at **+3.5%** above the entry fill price (take profit), or when the close falls **2.5%** below the highest close since entry (trailing stop, wide on purpose: 1-minute noise is ~8 bps, so it only fires on a real reversal).
- **Fallback:** if no cross ever fires by the 1001st bar, buy anyway, so the entry still makes at least one trade and meets the race guardrail instead of sitting in cash for a whole down day.
- **No re-entry** after an exit: on the dev window every re-entry in the flat second half paid ~26 bps a round trip and gave the edge back. One clean ride beats chopping.

A full-size round trip pays ~26 bps (4 bps fee + 2 bps modelled slippage + ~7 bps price impact each way at the frozen depth), so the +3.5% take-profit target is ~13x the round-trip cost. Orders cap slippage at 100 bps past the close they were decided on; a refused order is retried on the next bar.

## Dev-window result (kit's `grade-local`, process driver)

| Metric | Value |
|---|---|
| Net PnL | **+$36.74** (dev gate: > $0 — passed) |
| Net PnL at 2x fees | +$35.91 |
| Max drawdown | 1.18% (bar: ≤ 25%) |
| Trades | 2 (buy bar 60, sell bar 424 on take-profit) |
| Win rate | 100% |
| Determinism | Two independent grades, identical action log (`4d685584…`) |

Baselines on the same window for reference: buy-and-hold +$32.17, momentum +$34.94, ema-cross −$114.83, rsi-bollinger −$9.32, adx-momentum −$11.20.

## Files

- `main.ts` — the bot (Node 22, `agent-fun/bars-replay/v1`, standard library only)
- `vendor/makefun-bars.ts` — byte-identical copy of the kit's SDK shim
- `analysis/` — backtest simulator and parameter sweeps used to pick the strategy (not run by the grader)
- `LICENSE` — MIT

## Run it

The grader runs `node /bot/main.ts` against the replay harness. Locally, with the competition kit:

```sh
node cli/makefun.mjs grade-local --kit <kit-dir> --bot . --driver process
```
