#!/usr/bin/env python3
"""Independent agile 15m BTCUSDT PAPER strategy; no exchange order endpoints."""
from __future__ import annotations
import datetime as dt
import json
import sys
from pathlib import Path
from quant import api, equity, new_state, FEE_RATE, SLIPPAGE_RATE, STOP_EQUITY_USD, INITIAL_USD, MAX_ALLOCATION_USD, MIN_PAPER_ORDER

BAR_MS = 900000
FAST, SLOW = 8, 21
STOP_LOSS, TAKE_PROFIT = 0.010, 0.015
MAX_HOLD_BARS, MAX_ENTRIES_PER_DAY, COOLDOWN_BARS = 16, 4, 2


def initial_state():
    s = new_state()
    s.update({"strategy": "agile_15m_v1", "evaluations": 0, "skipped_intervals": 0,
              "realized_pnl_usd": 0.0, "last_entry": None, "last_exit_bar": None,
              "signal_events": [], "started_utc": None})
    return s


def indicators(closes):
    if len(closes) < SLOW + 1:
        return None
    return (sum(closes[-FAST:]) / FAST, sum(closes[-SLOW:]) / SLOW,
            sum(closes[-FAST-1:-1]) / FAST, sum(closes[-SLOW-1:-1]) / SLOW)


def entry_reason(closes):
    vals = indicators(closes)
    if vals is None:
        return None
    fast, slow, prev_fast, prev_slow = vals
    if prev_fast <= prev_slow and fast > slow:
        return "BULLISH_CROSS"
    if fast > slow and closes[-2] <= prev_fast and closes[-1] > fast and closes[-1] > closes[-2]:
        return "PULLBACK_RECOVERY"
    return None


def daily_entries(trades, bar):
    day = dt.datetime.fromtimestamp(bar / 1000, dt.timezone.utc).date()
    return sum(t["action"] == "BUY" and
               dt.datetime.fromtimestamp(t["bar"] / 1000, dt.timezone.utc).date() == day
               for t in trades)


def step_agile(state, bar, closes, bid, ask):
    p = json.loads(json.dumps(state))
    bar = int(bar)
    if p["last_bar"] is not None and bar <= int(p["last_bar"]):
        p["last_action"] = "ALREADY_PROCESSED"
        return p
    if not (bid > 0 and ask >= bid and len(closes) >= SLOW + 1):
        raise ValueError("Invalid market data")
    previous = p["last_bar"]
    gap = max(0, (bar - int(previous)) // BAR_MS - 1) if previous is not None else 0
    p["skipped_intervals"] += gap
    p["last_bar"] = bar
    p["evaluations"] += 1
    p["started_utc"] = p.get("started_utc") or dt.datetime.now(dt.timezone.utc).isoformat()
    p["peak_equity"] = max(p["peak_equity"], equity(p, bid))
    if equity(p, bid) <= STOP_EQUITY_USD:
        p["halted"] = True

    reason = "NO_SETUP"
    vals = indicators(closes)
    if p["btc"] > 0:
        entry = p.get("last_entry")
        if not entry:
            raise ValueError("Open paper position without entry record")
        held = (bar - int(entry["bar"])) // BAR_MS
        if p["halted"]:
            reason = "CIRCUIT_BREAKER"
        elif bid <= float(entry["execution"]) * (1 - STOP_LOSS):
            reason = "STOP_LOSS"
        elif bid >= float(entry["execution"]) * (1 + TAKE_PROFIT):
            reason = "TAKE_PROFIT"
        elif vals[0] < vals[1]:
            reason = "BEARISH_TREND"
        elif held >= MAX_HOLD_BARS:
            reason = "TIME_LIMIT"
        else:
            reason = "POSITION_OPEN"
        if reason == "POSITION_OPEN":
            p["last_action"] = "HOLD"
        else:
            qty = p["btc"]
            execution = bid * (1 - SLIPPAGE_RATE)
            proceeds = qty * execution * (1 - FEE_RATE)
            realized = proceeds - float(entry["notional"])
            p["cash"] += proceeds
            p["btc"] = 0.0
            p["last_exit_bar"] = bar
            p["realized_pnl_usd"] += realized
            p["trades"].append({"bar": bar, "action": "SELL", "quantity": qty,
                                "execution": execution, "proceeds": proceeds,
                                "net_pnl_usd": realized, "reason": reason})
            p["last_entry"] = None
            p["last_action"] = "SELL"
    elif p["halted"]:
        reason = "CIRCUIT_BREAKER"
        p["last_action"] = "HALTED"
    else:
        setup = entry_reason(closes)
        if setup is None:
            p["last_action"] = "HOLD"
        elif daily_entries(p["trades"], bar) >= MAX_ENTRIES_PER_DAY:
            reason = "DAILY_LIMIT"
            p["last_action"] = "HOLD"
        elif p.get("last_exit_bar") is not None and bar - int(p["last_exit_bar"]) < COOLDOWN_BARS * BAR_MS:
            reason = "COOLDOWN"
            p["last_action"] = "HOLD"
        else:
            amount = min(MAX_ALLOCATION_USD, p["cash"])
            if amount < MIN_PAPER_ORDER:
                reason = "INSUFFICIENT_CASH"
                p["last_action"] = "HOLD"
            else:
                execution = ask * (1 + SLIPPAGE_RATE)
                qty = amount * (1 - FEE_RATE) / execution
                p["cash"] -= amount
                p["btc"] += qty
                p["last_entry"] = {"bar": bar, "execution": execution, "notional": amount}
                p["trades"].append({"bar": bar, "action": "BUY", "quantity": qty,
                                    "execution": execution, "notional": amount, "reason": setup})
                reason = setup
                p["last_action"] = "BUY"
    p["signal_events"].append({"bar": bar, "decision": p["last_action"],
                               "reason": reason, "close": float(closes[-1]),
                               "bid": bid, "ask": ask, "missed_bars": gap})
    p["signal_events"] = p["signal_events"][-500:]
    p["peak_equity"] = max(p["peak_equity"], equity(p, bid))
    return p


def market():
    now_ms = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    candles = api("/api/v3/klines", {"symbol": "BTCUSDT", "interval": "15m", "limit": 150})
    candles = [c for c in candles if len(c) >= 7 and int(c[6]) < now_ms]
    if len(candles) < SLOW + 1:
        raise ValueError("Not enough closed candles")
    quote = api("/api/v3/ticker/bookTicker", {"symbol": "BTCUSDT"})
    bid, ask = float(quote["bidPrice"]), float(quote["askPrice"])
    if bid <= 0 or ask < bid:
        raise ValueError("Invalid bid ask")
    return candles, bid, ask


def report(state, bid, ask):
    total = equity(state, bid)
    trades = state["trades"]
    events = state["signal_events"]
    return {"timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "name": "agile_15m_v1", "symbol": "BTCUSDT", "simulation_only": True,
            "live_trading_enabled": False, "capital_usd": INITIAL_USD,
            "equity_usd": round(total, 6), "cash_usd": round(state["cash"], 6),
            "btc_virtual": round(state["btc"], 10),
            "net_pnl_virtual_usd": round(total - INITIAL_USD, 6),
            "realized_pnl_virtual_usd": round(state["realized_pnl_usd"], 6),
            "buys": sum(t["action"] == "BUY" for t in trades),
            "sells": sum(t["action"] == "SELL" for t in trades),
            "last_trade": trades[-1] if trades else None,
            "last_decision": state["last_action"],
            "last_reason": events[-1]["reason"] if events else None,
            "evaluations": state["evaluations"],
            "skipped_intervals": state["skipped_intervals"], "halted": state["halted"],
            "bid": bid, "ask": ask,
            "risk_limits": {"order_usd_max": MAX_ALLOCATION_USD, "stop_loss_pct": STOP_LOSS * 100,
                            "take_profit_pct": TAKE_PROFIT * 100,
                            "max_buys_per_utc_day": MAX_ENTRIES_PER_DAY,
                            "fee_each_side_pct": FEE_RATE * 100,
                            "slippage_each_side_pct": SLIPPAGE_RATE * 100},
            "caveat": "Only local PAPER orders modeled with public quotes. Scheduler delays can miss signals and risk exits. Stops not guaranteed."}


def main():
    file = Path("state/paper_15m_agile.json")
    out = Path("reports/agile_latest.json")
    try:
        s = json.loads(file.read_text(encoding="utf-8")) if file.exists() else initial_state()
        bars, bid, ask = market()
        s = step_agile(s, int(bars[-1][0]), [float(x[4]) for x in bars], bid, ask)
        file.parent.mkdir(exist_ok=True, parents=True)
        file.write_text(json.dumps(s, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        result = report(s, bid, ask)
        out.parent.mkdir(exist_ok=True, parents=True)
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        lines = ["# NEXUS Quant: 15m agile experimental", "",
                 "**Virtual only: no Binance exchange orders**", "",
                 f"Virtual balance: USD {result['equity_usd']:.4f}",
                 f"Virtual net P&L: USD {result['net_pnl_virtual_usd']:+.4f}",
                 f"Realized virtual P&L: USD {result['realized_pnl_virtual_usd']:+.4f}",
                 f"Buys/sells: {result['buys']}/{result['sells']}",
                 f"Last: {result['last_decision']} ({result['last_reason']})",
                 f"Skipped 15m bars: {result['skipped_intervals']}", "", result["caveat"]]
        out.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as err:
        print("Safe failure: no simulated orders: " + str(err), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
