#!/usr/bin/env python3
"""15-minute paper trader alongside hourly; no real orders or exchange keys."""
from __future__ import annotations
import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from quant import (api, new_state, step, save_report, STOP_EQUITY_USD)

INTERVAL_15M = "15m"
FAST_15M = 48  # 12 hours, same as hourly 12 x 1h
SLOW_15M = 192 # 48 hours, same as hourly 48 x 1h
BAR_MS = 15 * 60 * 1000


def get_market_15m(now_ms: int | None = None):
    if now_ms is None:
        now_ms = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    candles = api("/api/v3/klines", {"symbol": "BTCUSDT", "interval": INTERVAL_15M, "limit": 300})
    closed = [c for c in candles if len(c) >= 7 and int(c[6]) < now_ms]
    if len(closed) < SLOW_15M + 1:
        raise ValueError("Faltan velas de 15 minutos cerradas")
    quote = api("/api/v3/ticker/bookTicker", {"symbol": "BTCUSDT"})
    bid, ask = float(quote["bidPrice"]), float(quote["askPrice"])
    if bid <= 0 or ask < bid:
        raise ValueError("Libro de precios invalido")
    return closed, bid, ask


def next_state(state: dict, candles: list, bid: float, ask: float):
    last = int(candles[-1][0])
    prev = state.get("last_bar")
    skipped = max(0, (last - int(prev)) // BAR_MS - 1) if prev is not None and last > int(prev) else 0
    closes = [float(c[4]) for c in candles]
    updated = step(state, last, closes, bid, ask, fast=FAST_15M, slow=SLOW_15M)
    if updated["last_action"] != "ALREADY_PROCESSED":
        updated["skipped_intervals"] = int(state.get("skipped_intervals", 0)) + skipped
        updated["evaluations"] = int(state.get("evaluations", 0)) + 1
    return updated


def main():
    parser = argparse.ArgumentParser(description="BTCUSDT 15-min paper-only, no live trading")
    parser.add_argument("--state", default="state/paper_15m.json")
    parser.add_argument("--report", default="reports/latest_15m.json")
    args = parser.parse_args()
    path = Path(args.state)
    try:
        state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else new_state()
        candles, bid, ask = get_market_15m()
        state = next_state(state, candles, bid, ask)
        state.setdefault("started_utc", dt.datetime.now(dt.timezone.utc).isoformat())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        result = save_report(state, bid, ask, Path(args.report))
        result["interval"] = INTERVAL_15M
        result["sma_fast"] = FAST_15M
        result["sma_slow"] = SLOW_15M
        result["evaluations"] = state.get("evaluations", 0)
        result["skipped_intervals"] = state.get("skipped_intervals", 0)
        Path(args.report).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("No se opero (simulacion 15m): " + str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
