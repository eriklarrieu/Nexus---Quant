#!/usr/bin/env python3
"""Historical baseline evaluation. Does not predict future results or place orders."""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path
from quant import (api, equity, new_state, step, FEE_RATE, SLIPPAGE_RATE,
                   FAST_SMA, SLOW_SMA, INITIAL_USD, MAX_ALLOCATION_USD,
                   SYMBOL, INTERVAL)

SIMULATED_SPREAD = 0.0005


def simulate(rows: list, fast=FAST_SMA, slow=SLOW_SMA):
    if not 1 < fast < slow or len(rows) < slow + 3:
        raise ValueError("Se requieren mas velas cerradas")
    closes = [float(row[4]) for row in rows]
    s = new_state()
    portfolio = []
    for i in range(slow + 2, len(rows)):
        open_price = float(rows[i][1])
        bid = open_price * (1 - SIMULATED_SPREAD / 2)
        ask = open_price * (1 + SIMULATED_SPREAD / 2)
        s = step(s, int(rows[i-1][0]), closes[:i], bid, ask, fast=fast, slow=slow)
        portfolio.append(equity(s, bid))
    final_price = float(rows[-1][4])
    final_bid = final_price * (1 - SIMULATED_SPREAD / 2)
    strategy_equity = equity(s, final_bid)
    first_open = float(rows[slow+2][1])
    buy_ask = first_open * (1 + SIMULATED_SPREAD / 2) * (1 + SLIPPAGE_RATE)
    held_qty = MAX_ALLOCATION_USD * (1 - FEE_RATE) / buy_ask
    benchmark = INITIAL_USD - MAX_ALLOCATION_USD + held_qty * final_bid * (1 - FEE_RATE - SLIPPAGE_RATE)
    peak = INITIAL_USD
    max_dd = 0.0
    for value in portfolio + [strategy_equity]:
        peak = max(peak, value)
        max_dd = max(max_dd, (peak-value)/peak)
    return {
        "simulation_only": True,
        "fast_sma_bars": fast,
        "slow_sma_bars": slow,
        "source": "Binance public OHLC candles; bid/ask historical not provided",
        "assumed_spread_pct": SIMULATED_SPREAD * 100,
        "assumed_fee_each_side_pct": FEE_RATE * 100,
        "assumed_slippage_each_side_pct": SLIPPAGE_RATE * 100,
        "start_virtual_usd": INITIAL_USD,
        "strategy_end_virtual_usd": round(strategy_equity, 4),
        "strategy_net_virtual_usd": round(strategy_equity-INITIAL_USD, 4),
        "buy_and_hold_end_virtual_usd": round(benchmark, 4),
        "strategy_max_drawdown_pct": round(max_dd*100, 3),
        "strategy_trades": len(s["trades"]),
        "circuit_breaker": s["halted"],
        "bars_analyzed": len(rows),
        "warning": "Una prueba retrospectiva no prueba ventaja estadistica ni rentabilidad futura; falta prueba prospectiva fuera de muestra y estimacion real de costos.",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--output", default="reports/backtest.json")
    args = ap.parse_args()
    if not 60 <= args.limit <= 1000:
        ap.error("limit must be between 60 and 1000")
    data = api("/api/v3/klines", {"symbol": SYMBOL, "interval": INTERVAL, "limit": args.limit})
    now_ms = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    closed = [row for row in data if len(row) >= 7 and int(row[6]) < now_ms]
    results = simulate(closed)
    outfile = Path(args.output)
    outfile.parent.mkdir(parents=True, exist_ok=True)
    outfile.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False))

if __name__ == "__main__":
    main()
