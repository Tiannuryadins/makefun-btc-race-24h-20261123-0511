# BUILD-TRANSCRIPT.md — btc-race-24h-20261123-0511

Build session for the make.fun bounty "Race a BTC trading bot live for 24 hours"
(slug `btc-race-24h-20261123-0511`, $50 total, 1st $12). Built 23 Nov 2026, ~15:05–16:45 WIB,
by the Muse agent under the user's standing auto-submit mandate (free bounties only).
No secrets, keys, seeds, or credentials were used or recorded anywhere in this build.

## 1. Kit (competition's own, never a sibling's)

- Downloaded `https://make.fun/c/btc-race-24h-20261123-0511/kit` → 9.5 MB tarball,
  `~/workspace/make-fun/kits/btc-race-24h-20261123-0511/`.
- Kit: `agent-fun/bars-replay/v1`, 1,440 one-minute bars of cbBTC/USDC (Orca Whirlpool),
  dev window ending at the opening; fee 4 bps, slippage 2 bps, price impact vs open depth.
- Read `competition.yaml` (rules), `protocol.schema.json`, `sdk/makefun-bars.ts`,
  baselines, and the harness fill math in `harness/harness-src.tar.gz` (`sim/bars/engine.ts`).

## 2. Dev-window analysis

- 1,440 bars: $58,956.59 → $61,102.18 (+3.64%), gains concentrated in the first 8h,
  then flat; 1-min return sd 8.1 bps; buy-and-hold max drawdown 1.98%.
- Baselines graded locally (`makefun grade-local --driver process`):
  buy-and-hold +$32.17, momentum +$34.94, ema-cross −$114.83, rsi-bollinger −$9.32,
  adx-momentum −$11.20, hold-cash $0.

## 3. Strategy search (analysis/ — Python simulator replicating the engine's integer fill math)

- Simulator validated against the grader: buy-and-hold reproduced exactly (+$32.167313).
- EMA-cross variants all lost money (28–102 trades, whipsaw in the flat second half).
- Few-trade trend riders won. 200 block-bootstrapped windows (shuffled 1h blocks):
  single-entry + TP 3.5% + trailing stop 2.5% → median +$33.48, P(>0) = 0.96;
  a 1.5% trail was much worse (median +$4.86, stop-outs in noise).
- Chosen: EMA(8)/EMA(60) cross entry after the first hour, full cash, one round trip,
  take-profit +3.5% over the entry fill, trailing stop −2.5% from the peak close,
  fallback buy at bar 1000 if no cross ever fires (guarantees ≥1 trade).

## 4. Implementation and local grading

- `main.ts` written from scratch (TypeScript, erasable syntax, Node 22 type stripping),
  using the kit SDK shim copied byte-identical to `vendor/makefun-bars.ts`.
- First grade: +$34.03 — entry fired on bar 1 (EMA seeding, not a real cross).
  Fixed by gating signals until the slow EMA has 60 bars of history, matching the backtest.
- Final grade (`makefun grade-local --kit <kit> --bot . --driver process`):
  **net PnL +$36.739919, max drawdown 1.18%, 2 trades, win rate 100%**,
  net PnL at 2x fees +$35.91. Dev gate (PnL > $0) passed with margin.
- Determinism: two independent grade runs produced the identical action log
  (`action_log_sha256 4d68558490ffe88460138f50b448e26472ac5784766e8d439c377d6b3c36c917`).
- Action log: buy seq 60 (full $1,000 cash), sell seq 424 (take-profit).

## 5. Repo contents (NOT pushed — parent publishes + submits after independent re-check)

- `main.ts`, `vendor/makefun-bars.ts`, `LICENSE` (MIT), `README.md` (3 live make.fun
  badges + bounty link), `BUILD-TRANSCRIPT.md` (this file), `analysis/` (simulator + sweeps).
- Local git repo initialized with one commit; no remote, no push by this session.

## 6. Pre-submit check

- `makefun check --kit <kit> --repo . --worktree` run after the local commit; see
  the check output in the parent's report. Expected-only failure: `transcripts_present`
  (the parent bundles the transcripts at submit time).
