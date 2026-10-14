#!/usr/bin/env python3
"""Approximate matched-window historical comparison of paper-only strategies."""
from __future__ import annotations
import datetime as dt
import json
from pathlib import Path
from quant import api
from backtest import simulate
from paper15 import FAST_15M, SLOW_15M


def only_closed(rows, now_ms):
    return [r for r in rows if len(r) >= 7 and int(r[6]) < now_ms]


def compare(h1: list, m15: list):
    if len(h1) < 220 or len(m15) < 870:
        raise ValueError("Insufficient matched historical period (need approx 9 days)")
    last_time = min(int(h1[-1][6]), int(m15[-1][6]))
    # A 215-hour common historical period, plus both timeframes' 48h warmup.
    first_time = last_time - 216 * 3600000
    a = [r for r in h1 if first_time <= int(r[0]) and int(r[6]) <= last_time]
    b = [r for r in m15 if first_time <= int(r[0]) and int(r[6]) <= last_time]
    if len(a) < 210 or len(b) < 850:
        raise ValueError("Historical windows could not be sufficiently matched")
    r1 = simulate(a, fast=12, slow=48)
    r15 = simulate(b, fast=FAST_15M, slow=SLOW_15M)
    return {
        "simulation_only": True,
        "first_bar_utc": dt.datetime.fromtimestamp(first_time / 1000, dt.timezone.utc).isoformat(),
        "last_bar_utc": dt.datetime.fromtimestamp(last_time / 1000, dt.timezone.utc).isoformat(),
        "hourly": r1,
        "fifteen_minutes": r15,
        "limitation": "Comparacion retrospectiva aproximada con periodos y calentamientos cercanos, no identicos. Spread y deslizamiento estimados; no demuestra rentabilidad futura. Retornos no validos como autorizacion de operaciones reales."
    }


def main():
    now_ms = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    hour = only_closed(api("/api/v3/klines", {"symbol": "BTCUSDT", "interval": "1h", "limit": 300}), now_ms)
    quarter = only_closed(api("/api/v3/klines", {"symbol": "BTCUSDT", "interval": "15m", "limit": 1000}), now_ms)
    result = compare(hour, quarter)
    path = Path("reports/comparison_history.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"historical_1h_virtual_pnl":result["hourly"]["strategy_net_virtual_usd"],
                      "historical_15m_virtual_pnl":result["fifteen_minutes"]["strategy_net_virtual_usd"],
                      "warnings":result["limitation"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
