import unittest
from quant import new_state, signal
from paper15 import FAST_15M, SLOW_15M, BAR_MS, next_state


def candles(prices):
    return [[i * BAR_MS, str(p), str(p), str(p), str(p), "1", (i+1)*BAR_MS-1]
            for i, p in enumerate(prices)]


class Paper15Tests(unittest.TestCase):
    def test_same_horizon_in_hours(self):
        self.assertEqual(FAST_15M * 15, 12 * 60)
        self.assertEqual(SLOW_15M * 15, 48 * 60)

    def test_buy_signal_on_cross(self):
        x = signal([100.] * SLOW_15M + [120.], fast=FAST_15M, slow=SLOW_15M)
        self.assertEqual(x, "BUY")

    def test_sell_signal_on_cross(self):
        x = signal([100.] * SLOW_15M + [80.], fast=FAST_15M, slow=SLOW_15M)
        self.assertEqual(x, "SELL")

    def test_paper_buy_is_limited_to_ten(self):
        data = candles([100.] * SLOW_15M + [120.])
        s = next_state(new_state(), data, 119., 120.)
        self.assertEqual(s["last_action"], "BUY")
        self.assertAlmostEqual(s["cash"], 10)
        self.assertEqual(s["evaluations"], 1)

    def test_same_bar_does_not_duplicate_order(self):
        data = candles([100.] * SLOW_15M + [120.])
        first = next_state(new_state(), data, 119., 120.)
        second = next_state(first, data, 119., 120.)
        self.assertEqual(second["last_action"], "ALREADY_PROCESSED")
        self.assertEqual(second["evaluations"], 1)
        self.assertEqual(second["trades"], first["trades"])

    def test_skipped_schedule_intervals_are_reported(self):
        data = candles([100.] * SLOW_15M + [120.])
        s = new_state()
        s["last_bar"] = int(data[-1][0]) - 3 * BAR_MS
        result = next_state(s, data, 119., 120.)
        self.assertEqual(result["skipped_intervals"], 2)

    def test_no_real_trading_parameters(self):
        s = new_state()
        r = next_state(s, candles([100.] * (SLOW_15M + 1)), 100., 101.)
        self.assertEqual(r["cash"], 20)
        self.assertEqual(r["btc"], 0)

if __name__ == "__main__":
    unittest.main()
