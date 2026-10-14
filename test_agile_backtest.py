import unittest
from agile_backtest import simulate

def rows(prices):
    interval = 900000
    return [[i*interval, str(p), str(p), str(p), str(p), "1", (i+1)*interval - 1] for i, p in enumerate(prices)]

class AgileBacktestTests(unittest.TestCase):
    def test_flat_market_zero_trades(self):
        r = simulate(rows([100.] * 100))
        self.assertEqual(r["buys"], 0)
        self.assertEqual(r["sells"], 0)
        self.assertEqual(r["strategy_net_virtual_usd"], 0)
        self.assertTrue(r["simulation_only"])

    def test_trending_market_records_trades(self):
        prices = [100.] * 40 + [120.] * 40 + [110.] * 50
        r = simulate(rows(prices))
        self.assertGreaterEqual(r["buys"], 1)
        self.assertGreaterEqual(r["sells"], 1)
        self.assertLessEqual(r["max_drawdown_pct"], 100)

    def test_reject_short_history(self):
        with self.assertRaises(ValueError):
            simulate(rows([100.] * 15))

if __name__ == "__main__":
    unittest.main()
