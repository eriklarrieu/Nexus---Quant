import unittest
from backtest import simulate

class BacktestTests(unittest.TestCase):
    def test_reject_short_data(self):
        with self.assertRaises(ValueError):
            simulate([])

    def test_constant_price_loses_to_fees(self):
        rows = [[i*3600000, '100', '101', '99', '100', '1', (i+1)*3600000-1] for i in range(100)]
        result = simulate(rows)
        self.assertEqual(result["strategy_end_virtual_usd"], 20)
        self.assertLess(result["buy_and_hold_end_virtual_usd"], 20)
        self.assertEqual(result["strategy_trades"], 0)

    def test_stability_with_upward_data(self):
        rows = []
        for i in range(150):
            price = 100 + i*0.3
            rows.append([i*3600000, str(price), str(price), str(price), str(price), '1', (i+1)*3600000-1])
        result = simulate(rows)
        self.assertTrue(result["simulation_only"])
        self.assertGreaterEqual(result["strategy_trades"], 0)
        self.assertLessEqual(result["strategy_max_drawdown_pct"], 100)

if __name__ == '__main__':
    unittest.main()
