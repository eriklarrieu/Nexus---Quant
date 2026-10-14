#!/usr/bin/env python3
"""Three independent virtual BTCUSDT portfolios; transparent observation comparison."""
from __future__ import annotations
import datetime as dt
import json
from pathlib import Path
from quant import api, equity

ACCOUNTS = [
    ("1h_reference", "state/paper_state.json"),
    ("15m_reference", "state/paper_15m.json"),
    ("15m_agile_experiment", "state/paper_15m_agile.json")
]

def snapshot(state, label, bid):
    initial = float(state["initial_capital"])
    mark = equity(state, bid)
    return {"strategy": label, "initial_virtual_usd": initial,
            "equity_virtual_usd": round(mark, 6),
            "pnl_virtual_usd": round(mark - initial, 6),
            "buys": sum(t["action"] == "BUY" for t in state["trades"]),
            "sells": sum(t["action"] == "SELL" for t in state["trades"]),
            "last_action": state["last_action"],
            "last_candle": state["last_bar"],
            "evaluations": state.get("evaluations"),
            "skipped_intervals": state.get("skipped_intervals"),
            "first_observed_utc": state.get("started_utc")}


def main():
    quote = api("/api/v3/ticker/bookTicker", {"symbol": "BTCUSDT"})
    bid = float(quote["bidPrice"])
    if bid <= 0:
        raise ValueError("Invalid BTC quote")
    data = []
    for label, name in ACCOUNTS:
        state = json.loads(Path(name).read_text(encoding="utf-8"))
        data.append(snapshot(state, label, bid))
    result = {"as_of_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
              "simulation_only": True,
              "exchange_orders_executed": 0,
              "real_capital_spent_usd": 0,
              "accounts": data,
              "warning": "Independent USD 20 VIRTUAL accounts; different observation start times, missed candles and very short period. No evidence of live profitability."}
    dest = Path("reports/agile_three_way.json")
    dest.parent.mkdir(exist_ok=True, parents=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# NEXUS Quant — tres carteras independientes", "",
             "**Comparacion experimental exclusivamente virtual**", "",
             "| Estrategia | Saldo USD | P&L virtual USD | Compras | Ventas | Decision |",
             "|---|---:|---:|---:|---:|---|"]
    for row in data:
        lines.append(f"| {row['strategy']} | {row['equity_virtual_usd']:.4f} | "
                     f"{row['pnl_virtual_usd']:+.4f} | {row['buys']} | {row['sells']} | "
                     f"{row['last_action']} |")
    lines.extend(["", result["warning"]])
    dest.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
