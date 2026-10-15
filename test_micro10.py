import unittest
from micro10_core import (PERIOD_MS, TenSecondAggregator, evaluate, initial_state,
                          marked_equity, signal, summary, MAX_BUYS_PER_UTC_DAY)


def second(t, price=100., closed=True):
    return {"i": "1s", "x": closed, "t": t*1000,
            "o": str(price), "h": str(price + 1), "l": str(price - 1),
            "c": str(price), "v": "0.5"}


def bullish_state(bar=1_000_000):
    s = initial_state()
    s["history"] = [{"t": bar - (19-i)*PERIOD_MS, "c": 100.} for i in range(19)]
    s["last_bar"] = bar - PERIOD_MS
    return s


def buy(bar=1_000_000):
    return evaluate(bullish_state(bar), {"t": bar, "c": 101.},
                    (100.99, 101.), receipt_ms=2000, now_ms=2100)


class Micro10Tests(unittest.TestCase):
    def test_aggregate_only_10_consecutive_closed_seconds(self):
        a = TenSecondAggregator()
        for i in range(9):
            self.assertIsNone(a.push(second(i, 100+i)))
        candle = a.push(second(9, 109))
        self.assertEqual(candle["t"], 0)
        self.assertEqual(candle["seconds"], 10)
        self.assertEqual(candle["o"], 100.)
        self.assertEqual(candle["c"], 109.)
        self.assertEqual(candle["h"], 110.)
        self.assertEqual(candle["l"], 99.)
        self.assertEqual(candle["v"], 5.)

    def test_partial_second_update_not_counted(self):
        a = TenSecondAggregator()
        self.assertIsNone(a.push(second(0, closed=False)))
        for i in range(1, 10):
            self.assertIsNone(a.push(second(i)))
        self.assertEqual(a.incomplete, 1)

    def test_missing_second_rejects_bucket(self):
        a = TenSecondAggregator()
        for i in [0, 1, 2, 4, 5, 6, 7, 8, 9]:
            self.assertIsNone(a.push(second(i)))
        self.assertEqual(a.incomplete, 1)

    def test_duplicate_1s_frame_does_not_make_fake_10s_bar(self):
        a = TenSecondAggregator()
        self.assertIsNone(a.push(second(0)))
        self.assertIsNone(a.push(second(0)))
        for i in range(1, 10):
            out = a.push(second(i))
        self.assertEqual(out["seconds"], 10)
        self.assertEqual(a.ignored, 1)
        self.assertIsNone(a.push(second(9)))

    def test_missing_whole_bucket_tracked(self):
        a = TenSecondAggregator()
        a.push(second(0))
        a.push(second(30))
        self.assertEqual(a.incomplete, 3)

    def test_reject_bad_prices(self):
        a = TenSecondAggregator()
        with self.assertRaises(ValueError):
            a.push({"i": "1s", "x": True, "t": 1000,
                    "o": "100", "h": "90", "l": "80", "c": "100", "v": "1"})

    def test_requires_completed_history(self):
        self.assertEqual(signal([100.] * 3), "WARMUP")
        self.assertEqual(signal([100.] * 19 + [101.]), "CROSS_AND_MOMENTUM")
        self.assertEqual(signal([100.] * 19 + [100.01]), "CROSS_TOO_WEAK")

    def test_buy_is_virtual_and_capped(self):
        s = buy()
        self.assertEqual(s["last_action"], "BUY")
        self.assertEqual(s["cash"], 10.0)
        self.assertGreater(s["btc"], 0)
        self.assertEqual(s["trades"][-1]["reason"], "CROSS_AND_MOMENTUM")
        self.assertLess(marked_equity(s, 100.99), 20.)
        self.assertTrue(summary(s, (100.99,101.))["simulation_only"])
        self.assertFalse(summary(s, (100.99,101.))["live_trading_enabled"])

    def test_no_double_counting(self):
        s = buy()
        again = evaluate(s, {"t": 1_000_000, "c": 101.},
                         (100.99,101.), 2000,2100)
        self.assertEqual(again["last_action"], "ALREADY_PROCESSED")
        self.assertEqual(len(again["trades"]), 1)

    def test_quote_stale_blocks_entry(self):
        s = evaluate(bullish_state(), {"t": 1_000_000, "c": 101.},
                     (100.99,101.), 1000, 5000)
        self.assertEqual(s["last_action"], "HOLD")
        self.assertEqual(s["signal_events"][-1]["reason"], "STALE_BID_ASK")

    def test_spread_blocks_entry(self):
        s = evaluate(bullish_state(), {"t": 1_000_000, "c": 101.},
                     (99.,101.), 2000,2100)
        self.assertEqual(s["signal_events"][-1]["reason"], "SPREAD_TOO_WIDE")
        self.assertEqual(s["cash"], 20.)

    def test_missing_book_blocks_entry(self):
        s = evaluate(bullish_state(), {"t": 1_000_000, "c": 101.})
        self.assertEqual(s["signal_events"][-1]["reason"], "NO_FRESH_BID_ASK")

    def test_exit_loss_accounts_net_fees(self):
        first = buy()
        second = evaluate(first, {"t": 1_010_000, "c": 99.},
                          (99.,99.01), 2000,2100)
        self.assertEqual(second["last_action"], "SELL")
        self.assertEqual(second["trades"][-1]["reason"], "PAPER_STOP_LOSS")
        self.assertLess(second["realized_pnl_usd"], 0)
        self.assertAlmostEqual(second["cash"], 20 + second["realized_pnl_usd"])

    def test_exit_profit(self):
        first = buy()
        second = evaluate(first, {"t": 1_010_000, "c": 102.},
                          (102.1,102.11), 2000,2100)
        self.assertEqual(second["last_action"], "SELL")
        self.assertEqual(second["trades"][-1]["reason"], "PAPER_TAKE_PROFIT")
        self.assertGreater(second["realized_pnl_usd"], 0)

    def test_daily_entries_limit(self):
        s = bullish_state()
        s["trades"] = [{"action": "BUY", "bar": 990_000} for _ in range(MAX_BUYS_PER_UTC_DAY)]
        t = evaluate(s, {"t": 1_000_000, "c": 101.},
                     (100.99,101.), 2000,2100)
        self.assertEqual(t["signal_events"][-1]["reason"], "MAX_BUYS_TODAY")
        self.assertEqual(t["cash"], 20.)

    def test_halt_at_19(self):
        s = bullish_state()
        s["cash"] = 18.9
        t = evaluate(s, {"t": 1_000_000, "c": 101.},
                     (100.99,101.), 2000,2100)
        self.assertTrue(t["halted"])
        self.assertEqual(t["cash"], 18.9)

    def test_cooldown(self):
        s = bullish_state()
        s["last_sell_bar"] = 990_000
        t = evaluate(s, {"t": 1_000_000, "c": 101.},
                     (100.99,101.), 2000,2100)
        self.assertEqual(t["signal_events"][-1]["reason"], "COOLDOWN")

    def test_no_force_buy_in_flat_market(self):
        s = initial_state()
        for i in range(30):
            s = evaluate(s, {"t": i*PERIOD_MS, "c": 100.}, (99.99,100.), 2000,2100)
        self.assertEqual(s["cash"], 20.)
        self.assertEqual(s["trades"], [])
        self.assertEqual(s["evaluations"], 30)

if __name__ == "__main__":
    unittest.main()
