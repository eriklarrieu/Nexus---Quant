#!/usr/bin/env python3
"""Auditable side-by-side PAPER portfolio snapshot; no monetary trades."""
from __future__ import annotations
import datetime as dt
import json
from pathlib import Path
from quant import api, equity


def summarize(state: dict, bid: float, interval: str):
    initial = float(state["initial_capital"])
    value = equity(state, bid)
    return {
        "interval": interval,
        "capital_virtual_usd": initial,
        "equity_virtual_usd": round(value, 6),
        "pnl_virtual_usd": round(value - initial, 6),
        "pnl_pct_virtual": round((value / initial - 1) * 100, 5),
        "orders_virtuales": len(state.get("trades", [])),
        "compras_virtuales": sum(t["action"] == "BUY" for t in state.get("trades", [])),
        "ventas_virtuales": sum(t["action"] == "SELL" for t in state.get("trades", [])),
        "blocked": state.get("halted", False),
        "last_action": state.get("last_action", "UNKNOWN"),
        "last_candle": state.get("last_bar"),
        "skipped_intervals": state.get("skipped_intervals", "not_tracked"),
        "started_utc": state.get("started_utc", "not_tracked"),
    }


def build_report(hourly: dict, quarter: dict, bid: float):
    h = summarize(hourly, bid, "1h")
    q = summarize(quarter, bid, "15m")
    return {
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "simulation_only": True,
        "live_trading_enabled": False,
        "asset": "BTCUSDT",
        "portfolio_1h": h,
        "portfolio_15m": q,
        "pnl_difference_15m_minus_1h_virtual_usd": round(q["pnl_virtual_usd"] - h["pnl_virtual_usd"], 6),
        "warning": "Dos cuentas VIRTUALES independientes de US$20, no US$40 reales. Fechas de inicio distintas y pocos datos: diferencia NO prueba mejor rentabilidad. El saldo NO es dinero cobrado.",
    }


def main():
    h = json.loads(Path("state/paper_state.json").read_text(encoding="utf-8"))
    q = json.loads(Path("state/paper_15m.json").read_text(encoding="utf-8"))
    quote = api("/api/v3/ticker/bookTicker", {"symbol": "BTCUSDT"})
    bid = float(quote["bidPrice"])
    if bid <= 0:
        raise ValueError("Invalid bid")
    report = build_report(h, q, bid)
    out = Path("reports/comparison.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# NEXUS Quant: comparación virtual 1h frente a 15m", "",
             "**NO HAY OPERACIONES CON DINERO REAL**", "",
             "| Métrica | 1 hora | 15 minutos |", "|---|---:|---:|"]
    a, b = report["portfolio_1h"], report["portfolio_15m"]
    for label, key in [("Valor de cartera virtual (USD)", "equity_virtual_usd"),
                       ("Ganancia/perdida virtual (USD)", "pnl_virtual_usd"),
                       ("Resultado virtual (%)", "pnl_pct_virtual"),
                       ("Ordenes virtuales", "orders_virtuales")]:
        lines.append(f"| {label} | {a[key]} | {b[key]} |")
    lines.extend(["", report["warning"], "",
                  "Los resultados provienen de una muestra muy corta. Requieren validacion historica, prospectiva y de costos antes de operar en vivo."])
    out.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
