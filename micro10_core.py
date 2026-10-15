#!/usr/bin/env python3
"""NEXUS Micro 10s: auditable PAPER-ONLY decision engine.

Inputs are CLOSED exchange 1-second candles and a contemporaneous bid/ask.
No authenticated exchange API, trading endpoint, or account credentials.
"""
from __future__ import annotations

import datetime as dt
import json
from collections import deque

PERIOD_MS = 10_000
ONE_SEC_MS = 1_000
CAPITAL_USD = 20.0
MAX_BUY_USD = 10.0
MIN_PAPER_BUY_USD = 5.0
FEE = 0.001
SLIPPAGE = 0.0003
FAST, SLOW = 6, 18
MOMENTUM_BARS = 3
MIN_MOMENTUM = 0.0025  # 0.25% in 30s: fees alone can consume tiny gains.
MAX_SPREAD = 0.0008
STOP_LOSS = 0.004
TAKE_PROFIT = 0.006
TIME_STOP_BARS = 60
COOLDOWN_BARS = 12
MAX_BUYS_PER_UTC_DAY = 4
MIN_EQUITY_USD = 19.0
MAX_REALIZED_LOSS_PER_UTC_DAY = 0.35
QUOTE_MAX_AGE_MS = 3000
MAX_HISTORY = 500
MAX_EVENTS = 500


def initial_state():
    return {
        "version": 1, "strategy": "micro_10s_v1", "paper_only": True,
        "initial_capital": CAPITAL_USD, "cash": CAPITAL_USD, "btc": 0.0,
        "last_bar": None, "evaluations": 0, "incomplete_10s_bars": 0,
        "reconnects": 0, "signal_events": [], "trades": [], "history": [],
        "realized_pnl_usd": 0.0, "peak_equity": CAPITAL_USD,
        "halted": False, "entry": None, "last_sell_bar": None,
        "last_action": "INIT", "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "last_updated_utc": None,
    }


def marked_equity(state, bid):
    return float(state["cash"]) + float(state["btc"]) * bid * (1 - FEE - SLIPPAGE)


def sma(values, period):
    return sum(values[-period:]) / period


def day_of(bar_ms):
    return dt.datetime.fromtimestamp(bar_ms / 1000, tz=dt.timezone.utc).date()


def purchases_today(trades, bar_ms):
    today = day_of(bar_ms)
    return sum(t["action"] == "BUY" and day_of(int(t["bar"])) == today for t in trades)


def losses_today(trades, bar_ms):
    today = day_of(bar_ms)
    return sum(min(0.0, float(t["net_pnl_usd"])) for t in trades
               if t["action"] == "SELL" and day_of(int(t["bar"])) == today)


class TenSecondAggregator:
    """Exactly 10 distinct consecutive CLOSED 1s candles per 10s candle.

    Missing/duplicate seconds are never forward-filled. Completed buckets
    are emitted once, and incomplete buckets are explicitly discarded.
    """
    def __init__(self):
        self.bucket = None
        self.seconds = {}
        self.last_completed_bucket = None
        self.incomplete = 0
        self.ignored = 0

    def push(self, k):
        if k.get("i") != "1s" or k.get("x") is not True:
            return None
        t = int(k["t"])
        if t % ONE_SEC_MS:
            raise ValueError("One-second candle timestamp not aligned")
        bucket = t // PERIOD_MS * PERIOD_MS
        if self.last_completed_bucket is not None and bucket <= self.last_completed_bucket:
            self.ignored += 1
            return None
        if self.bucket is not None and bucket < self.bucket:
            self.ignored += 1
            return None
        if self.bucket is not None and bucket > self.bucket:
            if len(self.seconds) and len(self.seconds) != 10:
                self.incomplete += 1
            if bucket - self.bucket > PERIOD_MS:
                self.incomplete += (bucket - self.bucket) // PERIOD_MS - 1
            self.seconds = {}
        self.bucket = bucket
        if t in self.seconds:
            self.ignored += 1
            return None
        o, h, l, c, v = [float(k[key]) for key in ("o", "h", "l", "c", "v")]
        if not (0 < l <= o <= h and l <= c <= h and v >= 0):
            raise ValueError("Invalid 1s candle OHLCV")
        self.seconds[t] = (o, h, l, c, v)
        if t != bucket + 9 * ONE_SEC_MS:
            return None
        if len(self.seconds) != 10 or any(bucket + i * ONE_SEC_MS not in self.seconds for i in range(10)):
            self.incomplete += 1
            self.last_completed_bucket = bucket
            self.seconds = {}
            return None
        values = [self.seconds[bucket + i * ONE_SEC_MS] for i in range(10)]
        result = {"t": bucket, "o": values[0][0], "h": max(v[1] for v in values),
                  "l": min(v[2] for v in values), "c": values[-1][3],
                  "v": sum(v[4] for v in values), "seconds": 10}
        self.last_completed_bucket = bucket
        self.seconds = {}
        return result


def signal(closes):
    if len(closes) < SLOW + 1:
        return "WARMUP"
    short, long = sma(closes, FAST), sma(closes, SLOW)
    old_short = sma(closes[:-1], FAST)
    old_long = sma(closes[:-1], SLOW)
    if old_short <= old_long and short > long:
        if closes[-1] / closes[-1 - MOMENTUM_BARS] - 1 >= MIN_MOMENTUM:
            return "CROSS_AND_MOMENTUM"
        return "CROSS_TOO_WEAK"
    return "NO_CROSS"


def evaluate(state, candle, quote=None, receipt_ms=None, now_ms=None):
    """One decision per freshly closed 10s candle. quote=(bid,ask)."""
    st = json.loads(json.dumps(state))
    bar = int(candle["t"])
    if bar % PERIOD_MS:
        raise ValueError("Misaligned 10s candle")
    if st["last_bar"] is not None and bar <= int(st["last_bar"]):
        st["last_action"] = "ALREADY_PROCESSED"
        return st
    close = float(candle["c"])
    if close <= 0:
        raise ValueError("Invalid candle close")
    st["last_bar"] = bar
    st["evaluations"] += 1
    st["history"].append({"t": bar, "c": close})
    st["history"] = st["history"][-MAX_HISTORY:]
    st["last_updated_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    closes = [float(c["c"]) for c in st["history"]]
    reason = signal(closes)
    action = "HOLD"
    bid = ask = None
    if quote is None or receipt_ms is None or now_ms is None:
        reason = "NO_FRESH_BID_ASK"
    else:
        bid, ask = float(quote[0]), float(quote[1])
        if not (0 < bid <= ask):
            reason = "INVALID_BID_ASK"
        elif int(receipt_ms) > int(now_ms) or int(now_ms) - int(receipt_ms) > QUOTE_MAX_AGE_MS:
            reason = "STALE_BID_ASK"
        elif (ask - bid) / ask > MAX_SPREAD:
            reason = "SPREAD_TOO_WIDE"
        else:
            account_equity = marked_equity(st, bid)
            st["peak_equity"] = max(st["peak_equity"], account_equity)
            if account_equity <= MIN_EQUITY_USD:
                st["halted"] = True
            if st["btc"] > 0:
                entry = st["entry"]
                if entry is None:
                    raise ValueError("Open position without entry audit")
                held = (bar - int(entry["bar"])) // PERIOD_MS
                if st["halted"]:
                    reason = "EQUITY_CIRCUIT_BREAKER"
                elif bid <= float(entry["price"]) * (1 - STOP_LOSS):
                    reason = "PAPER_STOP_LOSS"
                elif bid >= float(entry["price"]) * (1 + TAKE_PROFIT):
                    reason = "PAPER_TAKE_PROFIT"
                elif held >= TIME_STOP_BARS:
                    reason = "TIME_STOP"
                elif len(closes) >= SLOW and sma(closes, FAST) < sma(closes, SLOW) and held >= 3:
                    reason = "TREND_REVERSAL"
                else:
                    reason = "POSITION_OPEN"
                if reason != "POSITION_OPEN":
                    sold_qty = st["btc"]
                    exec_price = bid * (1 - SLIPPAGE)
                    proceeds = sold_qty * exec_price * (1 - FEE)
                    net = proceeds - float(entry["notional"])
                    st["cash"] += proceeds
                    st["btc"] = 0.0
                    st["realized_pnl_usd"] += net
                    st["last_sell_bar"] = bar
                    st["trades"].append({"bar": bar, "action": "SELL",
                                         "quantity": sold_qty, "execution": exec_price,
                                         "proceeds": proceeds, "net_pnl_usd": net,
                                         "reason": reason})
                    st["entry"] = None
                    action = "SELL"
            elif st["halted"]:
                reason = "EQUITY_CIRCUIT_BREAKER"
            elif len(closes) < SLOW + 1:
                reason = "WARMUP"
            elif purchases_today(st["trades"], bar) >= MAX_BUYS_PER_UTC_DAY:
                reason = "MAX_BUYS_TODAY"
            elif losses_today(st["trades"], bar) <= -MAX_REALIZED_LOSS_PER_UTC_DAY:
                reason = "DAILY_LOSS_LIMIT"
            elif st["last_sell_bar"] is not None and bar - int(st["last_sell_bar"]) < COOLDOWN_BARS * PERIOD_MS:
                reason = "COOLDOWN"
            elif reason == "CROSS_AND_MOMENTUM":
                amount = min(MAX_BUY_USD, st["cash"])
                if amount < MIN_PAPER_BUY_USD:
                    reason = "BELOW_MIN_PAPER_BUY"
                else:
                    price = ask * (1 + SLIPPAGE)
                    qty = amount * (1 - FEE) / price
                    st["cash"] -= amount
                    st["btc"] += qty
                    st["entry"] = {"bar": bar, "price": price, "notional": amount}
                    st["trades"].append({"bar": bar, "action": "BUY", "quantity": qty,
                                         "execution": price, "notional": amount,
                                         "reason": reason})
                    action = "BUY"
    st["last_action"] = action
    st["signal_events"].append({"bar": bar, "action": action, "reason": reason,
                                "close": close, "bid": bid, "ask": ask})
    st["signal_events"] = st["signal_events"][-MAX_EVENTS:]
    return st


def summary(state, quote=None):
    bid = float(quote[0]) if quote else None
    mark = marked_equity(state, bid) if bid and bid > 0 else (state["cash"] if not state["btc"] else None)
    return {"strategy": "micro_10s_v1", "simulation_only": True,
            "live_trading_enabled": False, "exchange_orders": 0,
            "as_of_utc": state.get("last_updated_utc"),
            "capital_virtual_usd": state["initial_capital"],
            "equity_virtual_usd": round(mark, 6) if mark is not None else None,
            "net_pnl_virtual_usd": round(mark-state["initial_capital"], 6) if mark is not None else None,
            "realized_pnl_virtual_usd": round(state["realized_pnl_usd"], 6),
            "cash_virtual_usd": round(state["cash"], 6),
            "btc_virtual": round(state["btc"], 10),
            "buys": sum(t["action"] == "BUY" for t in state["trades"]),
            "sells": sum(t["action"] == "SELL" for t in state["trades"]),
            "last_trade": state["trades"][-1] if state["trades"] else None,
            "last_signal": state["signal_events"][-1] if state["signal_events"] else None,
            "decisions": state["evaluations"],
            "incomplete_bars": state["incomplete_10s_bars"],
            "reconnects": state["reconnects"], "halted": state["halted"],
            "warning": "Paper model only. Incomplete feeds, delayed quotes or disconnection suspend decisions; protective exits only on evaluated candles, not guaranteed."}
