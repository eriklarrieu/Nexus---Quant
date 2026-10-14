#!/usr/bin/env python3
"""NEXUS QUANT: paper-only BTCUSDT spot prototype. Does not place real or testnet orders.
This module deliberately contains no exchange trading credentials or signed order endpoint.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

DATA_API = "https://data-api.binance.vision"
SYMBOL = "BTCUSDT"
INTERVAL = "1h"
INITIAL_USD = 20.0
MAX_ALLOCATION_USD = 10.0
FEE_RATE = 0.001
SLIPPAGE_RATE = 0.0003
MIN_PAPER_ORDER = 5.0
STOP_EQUITY_USD = 18.0
FAST_SMA = 12
SLOW_SMA = 48


def api(path: str, params: dict):
    url = DATA_API + path + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "NexusQuantPaper/0.1"})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def get_market(now_ms: int | None = None):
    if now_ms is None:
        now_ms = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    bars = api("/api/v3/klines", {"symbol": SYMBOL, "interval": INTERVAL, "limit": 300})
    closed = [x for x in bars if len(x) >= 7 and int(x[6]) < now_ms]
    if len(closed) < SLOW_SMA + 2:
        raise ValueError("Historial insuficiente de velas cerradas")
    quote = api("/api/v3/ticker/bookTicker", {"symbol": SYMBOL})
    bid, ask = float(quote["bidPrice"]), float(quote["askPrice"])
    if not (0 < bid <= ask):
        raise ValueError("Libro de cotizaciones invalido")
    return closed, bid, ask


def signal(closes: list[float], fast: int = FAST_SMA, slow: int = SLOW_SMA):
    if not 1 < fast < slow or len(closes) < slow + 1:
        return "WAIT"
    short = sum(closes[-fast:]) / fast
    long = sum(closes[-slow:]) / slow
    old_short = sum(closes[-fast-1:-1]) / fast
    old_long = sum(closes[-slow-1:-1]) / slow
    if old_short <= old_long and short > long:
        return "BUY"
    if old_short >= old_long and short < long:
        return "SELL"
    return "HOLD"


def new_state():
    return {"version": 1, "cash": INITIAL_USD, "btc": 0.0, "initial_capital": INITIAL_USD,
            "last_bar": None, "peak_equity": INITIAL_USD, "halted": False,
            "trades": [], "last_action": "INIT"}


def equity(state, bid):
    return state["cash"] + state["btc"] * bid * (1 - FEE_RATE - SLIPPAGE_RATE)


def step(state: dict, bar_open_time: int, closes: list[float], bid: float, ask: float,
         fast: int = FAST_SMA, slow: int = SLOW_SMA) -> dict:
    p = json.loads(json.dumps(state))
    if p["last_bar"] is not None and int(bar_open_time) <= int(p["last_bar"]):
        p["last_action"] = "ALREADY_PROCESSED"
        return p
    if not (bid > 0 and ask >= bid and closes):
        raise ValueError("Precios invalidos")
    p["last_bar"] = int(bar_open_time)
    before = equity(p, bid)
    p["peak_equity"] = max(p["peak_equity"], before)
    if before <= STOP_EQUITY_USD:
        p["halted"] = True
    action = signal(closes, fast=fast, slow=slow)
    if p["halted"] and p["btc"] > 0:
        action = "SELL"
    if p["halted"] and p["btc"] == 0:
        p["last_action"] = "HALTED"
        return p
    if action == "BUY" and p["btc"] < 1e-12:
        allocation = min(MAX_ALLOCATION_USD, p["cash"])
        if allocation >= MIN_PAPER_ORDER:
            execution = ask * (1 + SLIPPAGE_RATE)
            qty = allocation * (1 - FEE_RATE) / execution
            p["cash"] -= allocation
            p["btc"] += qty
            p["trades"].append({"bar": bar_open_time, "action": "BUY", "quantity": qty,
                                "execution": execution, "notional": allocation})
            p["last_action"] = "BUY"
        else:
            p["last_action"] = "TOO_SMALL"
    elif action == "SELL" and p["btc"] > 0:
        execution = bid * (1 - SLIPPAGE_RATE)
        qty = p["btc"]
        proceeds = qty * execution * (1 - FEE_RATE)
        p["cash"] += proceeds
        p["btc"] = 0.0
        p["trades"].append({"bar": bar_open_time, "action": "SELL", "quantity": qty,
                            "execution": execution, "proceeds": proceeds})
        p["last_action"] = "SELL"
    else:
        p["last_action"] = "HOLD"
    p["peak_equity"] = max(p["peak_equity"], equity(p, bid))
    return p


def save_report(state: dict, bid: float, ask: float, path: Path):
    mark = equity(state, bid)
    pnl = mark - state["initial_capital"]
    report = {
        "as_of_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "asset": SYMBOL,
        "simulation_only": True, "live_trading_enabled": False,
        "capital_reference_usd": state["initial_capital"],
        "cash_usd": round(state["cash"], 6), "btc_virtual": round(state["btc"], 10),
        "marked_equity_usd": round(mark, 6), "net_pnl_virtual_usd": round(pnl, 6),
        "bid": bid, "ask": ask, "operations": len(state["trades"]),
        "last_action": state["last_action"], "halted": state["halted"],
        "caveat": "Modelo de papel con bid/ask y deslizamiento supuesto. Resultados NO son ingresos ni rentabilidades garantizadas."}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md = ["# NEXUS Quant — reporte de simulacion", "", "**No opera con dinero real.**", "",
          f"- Valor virtual: US$ {mark:.4f}", f"- P&L virtual: US$ {pnl:+.4f}",
          f"- Operaciones: {len(state['trades'])}", f"- Ultima accion: {state['last_action']}",
          f"- Bloqueado por riesgo: {state['halted']}", "",
          "Los resultados son simulados; la operativa real puede diferir por costes, ejecucion y mercado."]
    path.with_suffix(".md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description="NEXUS Quant - solo simulacion Spot")
    parser.add_argument("--state", default="state/paper_state.json")
    parser.add_argument("--report", default="reports/latest.json")
    opts = parser.parse_args()
    state_file = Path(opts.state)
    try:
        state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else new_state()
        bars, bid, ask = get_market()
        closes = [float(x[4]) for x in bars]
        state = step(state, int(bars[-1][0]), closes, bid, ask)
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        report = save_report(state, bid, ask, Path(opts.report))
        print(json.dumps(report, ensure_ascii=False))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print("Error de simulacion (sin realizar operaciones): " + str(exc), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
