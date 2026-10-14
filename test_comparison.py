import unittest
from quant import new_state
from comparison import build_report, summarize
from compare_history import compare


class ComparisonTests(unittest.TestCase):
    def test_independent_portfolios(self):
        hourly, quarter = new_state(), new_state()
        quarter["cash"] = 10.0
        quarter["btc"] = 0.1
        report = build_report(hourly, quarter, 100.0)
        self.assertTrue(report["simulation_only"])
        self.assertEqual(report["portfolio_1h"]["equity_virtual_usd"], 20)
        self.assertLess(report["portfolio_15m"]["equity_virtual_usd"], 20)
        self.assertEqual(report["portfolio_1h"]["capital_virtual_usd"], 20)
        self.assertEqual(report["portfolio_15m"]["capital_virtual_usd"], 20)

    def test_no_extra_account_movement(self):
        s = new_state()
        before = dict(s)
        summarize(s, 100.0, "1h")
        self.assertEqual(s, before)

    def test_history_needs_sufficient_data(self):
        with self.assertRaises(ValueError):
            compare([], [])

if __name__ == "__main__":
    unittest.main()
