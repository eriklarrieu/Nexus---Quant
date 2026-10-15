#!/usr/bin/env python3
"""Continuous Binance PUBLIC WebSocket sampler for 10s PAPER trading.

Requires: pip install -r requirements-micro10.txt
No API keys, no order endpoints, no real/testnet trading.

Use a continuously running machine/VM for continuous operation.
GitHub Actions can only do bounded connection smoke tests, not 24/7 service.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

from micro10_core import (QUOTE_MAX_AGE_MS, TenSecondAggregator, evaluate,
                          initial_state, summary)

STREAM = ("wss://data-stream.binance.vision:443/stream"
          "?streams=btcusdt@kline_1s/btcusdt@bookTicker")


def write_json_atomic(path, value):
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, dest)


def load_state(path):
    p = Path(path)
    if not p.exists():
        return initial_state()
    s = json.loads(p.read_text(encoding="utf-8"))
    if s.get("strategy") != "micro_10s_v1" or s.get("paper_only") is not True:
        raise ValueError("Unrecognized or non-paper portfolio file")
    return s


async def run(duration_seconds, state_path, report_path, min_complete_bars=0, ws_url=STREAM):
    try:
        from websockets.asyncio.client import connect
    except ImportError as exc:
        raise RuntimeError("Install websockets: pip install -r requirements-micro10.txt") from exc

    state = load_state(state_path)
    started = time.monotonic()
    deadline = (started + duration_seconds) if duration_seconds > 0 else None
    completed = 0
    websocket_frames = 0
    connection_attempts = 0
    errors = 0
    reconnect_backoff = 2
    last_quote = None
    quote_received_ms = None

    def safe_quote():
        now_ms = int(time.time() * 1000)
        if last_quote is not None and quote_received_ms is not None and 0 <= now_ms-quote_received_ms <= QUOTE_MAX_AGE_MS:
            return last_quote
        return None

    def store(phase):
        base = summary(state, safe_quote())
        base["runtime"] = {
            "phase": phase, "continuous_host_required": True,
            "stream": "Binance public BTCUSDT 1s kline + best bid/ask",
            "complete_10s_bars_in_this_session": completed,
            "frames_in_this_session": websocket_frames,
            "connection_attempts": connection_attempts,
            "websocket_errors": errors,
            "window_seconds": round(time.monotonic() - started, 1),
        }
        write_json_atomic(state_path, state)
        write_json_atomic(report_path, base)
        return base

    store("STARTED")
    while True:
        if deadline is not None and time.monotonic() >= deadline:
            break
        connection_attempts += 1
        agg = TenSecondAggregator()
        last_quote, quote_received_ms = None, None
        if connection_attempts > 1:
            state["reconnects"] += 1
        try:
            async with connect(ws_url, open_timeout=18, close_timeout=5,
                               ping_interval=20, ping_timeout=20,
                               max_size=1_000_000, max_queue=512) as socket:
                reconnect_backoff = 2
                print(json.dumps({"event": "CONNECTED", "utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                                  "attempt": connection_attempts}), flush=True)
                while True:
                    if deadline is not None and time.monotonic() >= deadline:
                        break
                    timeout = min(8, max(0.1, deadline - time.monotonic())) if deadline is not None else 8
                    try:
                        raw = await asyncio.wait_for(socket.recv(), timeout=timeout)
                    except asyncio.TimeoutError:
                        if deadline is not None and time.monotonic() >= deadline:
                            break
                        raise TimeoutError("No fresh public market messages for 8 seconds")
                    websocket_frames += 1
                    packet = json.loads(raw)
                    stream_name = packet.get("stream", "")
                    data = packet.get("data", {})
                    if stream_name.endswith("@bookTicker"):
                        bid, ask = float(data["b"]), float(data["a"])
                        if 0 < bid <= ask:
                            last_quote = (bid, ask)
                            quote_received_ms = int(time.time() * 1000)
                        continue
                    if stream_name.endswith("@kline_1s"):
                        kline = data.get("k", {})
                        before = agg.incomplete
                        candle = agg.push(kline)
                        if agg.incomplete != before:
                            state["incomplete_10s_bars"] += agg.incomplete - before
                        if candle is None:
                            continue
                        completed += 1
                        now_ms = int(time.time() * 1000)
                        state = evaluate(state, candle, last_quote, quote_received_ms, now_ms)
                        latest = state["signal_events"][-1] if state["signal_events"] else None
                        print(json.dumps({
                            "event": "CLOSED_10S_BAR", "utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                            "bar_open_ms": candle["t"], "decision": state["last_action"],
                            "reason": latest["reason"] if latest else None,
                            "virtual_equity_usd": summary(state, safe_quote())["equity_virtual_usd"]
                        }, ensure_ascii=False), flush=True)
                        store("STREAMING")
                if deadline is not None and time.monotonic() >= deadline:
                    break
        except (OSError, ValueError, TypeError, KeyError, RuntimeError, TimeoutError, asyncio.TimeoutError) as err:
            errors += 1
            print(json.dumps({"event": "FEED_INTERRUPTED", "error": str(err),
                              "utc": dt.datetime.now(dt.timezone.utc).isoformat()}), file=sys.stderr, flush=True)
            store("RECONNECT_WAIT")
            if deadline is not None and time.monotonic() >= deadline:
                break
            delay = min(reconnect_backoff, max(0, deadline - time.monotonic())) if deadline else reconnect_backoff
            await asyncio.sleep(delay)
            reconnect_backoff = min(reconnect_backoff * 2, 30)
    result = store("SESSION_ENDED" if duration_seconds > 0 else "DISCONNECTED")
    print(json.dumps(result, ensure_ascii=False), flush=True)
    if completed < min_complete_bars:
        raise RuntimeError("Received only " + str(completed) + " complete live 10s candles (minimum " + str(min_complete_bars) + ")")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-seconds", type=int, default=0,
                        help="0=run continuously, >0=bounded smoke test")
    parser.add_argument("--state", default="state/micro10_state.json")
    parser.add_argument("--report", default="reports/micro10_latest.json")
    parser.add_argument("--min-complete-bars", type=int, default=0)
    args = parser.parse_args()
    if args.duration_seconds < 0 or args.min_complete_bars < 0:
        parser.error("Durations and counts must be nonnegative")
    try:
        asyncio.run(run(args.duration_seconds, args.state, args.report, args.min_complete_bars))
    except (OSError, RuntimeError, ValueError) as err:
        print("Micro 10s not verified: " + str(err), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
