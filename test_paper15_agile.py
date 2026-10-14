import unittest
from paper15_agile import (BAR_MS, initial_state, indicators, entry_reason, step_agile,
                           report, MAX_ENTRIES_PER_DAY)


def rising():
    return [100.] * 21 + [120.]


class Agile15Tests(unittest.TestCase):
    def test_independent_funds(self):
        s = initial_state()
        self.assertEqual(s["cash"], 20)
        self.assertEqual(s["btc"], 0)
        self.assertEqual(s["trades"], [])

    def test_fast_signals(self):
        self.assertEqual(entry_reason(rising()), "BULLISH_CROSS")
        self.assertIsNone(entry_reason([100.] * 30))
        self.assertIsNone(indicators([100.] * 12))

    def test_pullback_recovery(self):
        prices = [100.] * 30 + [110.] * 12 + [108., 115.]
        self.assertEqual(entry_reason(prices), "PULLBACK_RECOVERY")

    def test_buy_capped(self):
        s = step_agile(initial_state(), 100 * BAR_MS, rising(), 119., 120.)
        self.assertEqual(s["last_action"], "BUY")
        self.assertEqual(len(s["trades"]), 1)
        self.assertEqual(s["cash"], 10)
        self.assertGreater(s["btc"], 0)

    def test_duplicate_candle_does_not_double_buy(self):
        s = step_agile(initial_state(), 100 * BAR_MS, rising(), 119., 120.)
        t = step_agile(s, 100 * BAR_MS, rising(), 119., 120.)
        self.assertEqual(t["last_action"], "ALREADY_PROCESSED")
        self.assertEqual(t["evaluations"], 1)
        self.assertEqual(len(t["trades"]), 1)

    def test_stop_loss_and_realized_pnl(self):
        s = step_agile(initial_state(), 100 * BAR_MS, rising(), 119., 120.)
        t = step_agile(s, 101 * BAR_MS, [100.] * 30, 117., 117.1)
        self.assertEqual(t["last_action"], "SELL")
        self.assertEqual(t["trades"][-1]["reason"], "STOP_LOSS")
        self.assertLess(t["realized_pnl_usd"], 0)
        self.assertEqual(t["btc"], 0)

    def test_take_profit(self):
        s = step_agile(initial_state(), 100 * BAR_MS, rising(), 119., 120.)
        t = step_agile(s, 101 * BAR_MS, [100.] * 30, 123., 123.01)
        self.assertEqual(t["last_action"], "SELL")
        self.assertEqual(t["trades"][-1]["reason"], "TAKE_PROFIT")
        self.assertGreater(t["realized_pnl_usd"], 0)

    def test_daily_buy_limit(self):
        s = initial_state()
        bar = 100 * BAR_MS
        s["trades"] = [{"action": "BUY", "bar": bar} for _ in range(MAX_ENTRIES_PER_DAY)]
        t = step_agile(s, bar, rising(), 119., 120.)
        self.assertEqual(t["last_action"], "HOLD")
        self.assertEqual(t["signal_events"][-1]["reason"], "DAILY_LIMIT")

    def test_skip_accounting(self):
        s = initial_state()
        s["last_bar"] = 97 * BAR_MS
        t = step_agile(s, 100 * BAR_MS, [100.] * 30, 99., 100.)
        self.assertEqual(t["skipped_intervals"], 2)
        self.assertEqual(t["evaluations"], 1)

    def test_cooldown_after_exit(self):
        s = initial_state()
        s["last_exit_bar"] = 99 * BAR_MS
        t = step_agile(s, 100 * BAR_MS, rising(), 119., 120.)
        self.assertEqual(t["last_action"], "HOLD")
        self.assertEqual(t["signal_events"][-1]["reason"], "COOLDOWN")

    def test_stop_equity(self):
        s = initial_state()
        s["cash"] = 17
        t = step_agile(s, 100 * BAR_MS, rising(), 119., 120.)
        self.assertTrue(t["halted"])
        self.assertEqual(t["last_action"], "HALTED")

    def test_report_virtual_only(self):
        s = step_agile(initial_state(), 100 * BAR_MS, [100.] * 30, 100., 100.01)
        r = report(s, 100., 100.01)
        self.assertTrue(r["simulation_only"])
        self.assertFalse(r["live_trading_enabled"])
        self.assertEqual(r["net_pnl_virtual_usd"], 0)
        self.assertEqual(r["buys"], 0)

    def test_invalid_book_rejected(self):
        with self.assertRaises(ValueError):
            step_agile(initial_state(), 100 * BAR_MS, rising(), 101., 100.)

if __name__ == "__main__":
    unittest.main()
