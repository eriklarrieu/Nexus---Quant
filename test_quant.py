import json
import tempfile
import unittest
from pathlib import Path
from quant import (INITIAL_USD, MAX_ALLOCATION_USD, equity, new_state, save_report,
                   signal, step)

class QuantTests(unittest.TestCase):
    def test_initial_capital(self):
        self.assertEqual(new_state()["cash"], 20.0)
    def test_no_data_no_signal(self):
        self.assertEqual(signal([1.] * 10), "WAIT")
    def test_flat_signal(self):
        self.assertEqual(signal([1.] * 100), "HOLD")
    def test_up_cross(self):
        self.assertEqual(signal([100.] * 49 + [120.]), "BUY")
    def test_down_cross(self):
        self.assertEqual(signal([100.] * 49 + [80.]), "SELL")
    def test_buy_cap(self):
        q = step(new_state(), 1, [100.] * 49 + [120.], 119., 120.)
        self.assertEqual(q["last_action"], "BUY")
        self.assertAlmostEqual(q["cash"], INITIAL_USD - MAX_ALLOCATION_USD)
        self.assertGreater(q["btc"], 0)
    def test_duplicate_idempotency(self):
        q = step(new_state(), 1, [100.] * 49 + [120.], 119., 120.)
        again = step(q, 1, [100.] * 49 + [120.], 119., 120.)
        self.assertEqual(again["last_action"], "ALREADY_PROCESSED")
        self.assertEqual(q["trades"], again["trades"])
    def test_sell(self):
        q = step(new_state(), 1, [100.] * 49 + [120.], 119., 120.)
        q = step(q, 2, [100.] * 49 + [80.], 80., 80.1)
        self.assertEqual(q["last_action"], "SELL")
        self.assertEqual(q["btc"], 0)
        self.assertEqual(len(q["trades"]), 2)
    def test_risk_halt(self):
        q = new_state()
        q["cash"], q["btc"] = 0.0, 2.0
        x = step(q, 1, [100.] * 60, 8., 8.1)
        self.assertTrue(x["halted"])
        self.assertEqual(x["btc"], 0.0)
    def test_invalid_bid_ask(self):
        with self.assertRaises(ValueError):
            step(new_state(), 1, [100.] * 60, 100., 90.)
    def test_mark_to_market_includes_costs(self):
        q = new_state()
        q["cash"], q["btc"] = 0, 1
        self.assertLess(equity(q, 20), 20)
    def test_report_virtual(self):
        with tempfile.TemporaryDirectory() as p:
            report = save_report(new_state(), 100., 101., Path(p) / "r.json")
            self.assertTrue(report["simulation_only"])
            self.assertFalse(report["live_trading_enabled"])
            self.assertIn("No opera", Path(p, "r.md").read_text(encoding="utf-8"))

if __name__ == "__main__":
    unittest.main()
