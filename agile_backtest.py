#!/usr/bin/env python3
"""Historical-only agile 15m backtest: fill at following candle open, assumed costs."""
from __future__ import annotations
import datetime as dt
import json
from pathlib import Path
from quant import api, equity, INITIAL_USD, MAX_ALLOCATION_USD, FEE_RATE, SLIPPAGE_RATE
from paper15_agile import step_agile, initial_state, SLOW

SPREAD = 0.0005


def simulate(rows):
    if len(rows) < SLOW + 30:
        raise ValueError("At least 51 closed candles required")
    closes = [float(x[4]) for x in rows]
    s = initial_state()
    values = []
    for i in range(SLOW + 2, len(rows)):
        # Evaluate close i-1; model execution at the start of the next bar i.
        # No future high/low/close is used for any entry/exit decision.
        mid = float(rows[i][1])
        bid, ask = mid * (1 - SPREAD / 2), mid * (1 + SPREAD / 2)
        s = step_agile(s, int(rows[i - 1][0]), closes[:i], bid, ask)
        values.append(equity(s, bid))
    last_bid = float(rows[-1][4]) * (1 - SPREAD / 2)
    final = equity(s, last_bid)
    first_price = float(rows[SLOW + 2][1]) * (1 + SPREAD / 2) * (1 + SLIPPAGE_RATE)
    passive_qty = MAX_ALLOCATION_USD * (1 - FEE_RATE) / first_price
    passive = INITIAL_USD - MAX_ALLOCATION_USD + passive_qty * last_bid * (1 - FEE_RATE - SLIPPAGE_RATE)
    peak, maxdd = INITIAL_USD, 0.0
    for value in values + [final]:
        peak = max(peak, value)
        maxdd = max(maxdd, (peak - value) / peak)
    sells = [t for t in s["trades"] if t["action"] == "SELL"]
    wins = [t for t in sells if t["net_pnl_usd"] > 0]
    return {
        "simulation_only": True,
        "strategy": "agile_15m_v1",
        "bars": len(rows),
        "start_virtual_usd": INITIAL_USD,
        "strategy_end_virtual_usd": round(final, 6),
        "strategy_net_virtual_usd": round(final - INITIAL_USD, 6),
        "passive_10_usd_btc_end_virtual_usd": round(passive, 6),
        "buys": sum(t["action"] == "BUY" for t in s["trades"]),
        "sells": len(sells),
        "roundtrip_wins": len(wins),
        "roundtrip_win_pct": round(100 * len(wins) / len(sells), 2) if sells else None,
        "realized_net_pnl_virtual_usd": round(s["realized_pnl_usd"], 6),
        "max_drawdown_pct": round(maxdd * 100, 4),
        "halted": s["halted"],
        "assumed_spread_pct": SPREAD * 100,
        "fee_each_side_pct": FEE_RATE * 100,
        "slippage_each_side_pct": SLIPPAGE_RATE * 100,
        "warning": "Historico modelado, no operaciones reales. Entrada/salida a apertura siguiente usando cierres previos, precios de apertura y spread artificial; no hay stops intrabar, book real historico ni certeza futura."
    }


def main():
    now_ms = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    candles = api("/api/v3/klines", {"symbol": "BTCUSDT", "interval": "15m", "limit": 1000})
    closed = [c for c in candles if len(c) >= 7 and int(c[6]) < now_ms]
    result = simulate(closed)
    path = Path("reports/agile_backtest.json")
    path.parent.mkdir(exist_ok=True, parents=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
