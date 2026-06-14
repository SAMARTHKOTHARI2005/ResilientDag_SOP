import unittest

from experiments.run_experiments import aggregate_results, format_table_summary, run_once


class ExperimentRunnerTests(unittest.TestCase):
    def test_run_once_confirms_round_one_first(self):
        result = run_once(500, "baseline", seed=30, sim_time=5.0)
        self.assertTrue(result["confirmed_rounds"], "baseline should confirm at least one round")
        self.assertEqual(result["confirmed_rounds"], sorted(result["confirmed_rounds"]))
        self.assertEqual([round_num for round_num, _ in result["confirmation_times"]], sorted(result["confirmed_rounds"]))

    def test_aggregate_results_reports_mean_std_for_table_i(self):
        rows = aggregate_results([(500, 30)], seeds=30, sim_time=2.0)
        self.assertEqual(len(rows), 4)
        for row in rows:
            self.assertIn("latency_ms_mean", row)
            self.assertIn("latency_ms_std", row)
            self.assertIn("throughput_mean", row)
            self.assertIn("throughput_std", row)
            self.assertIn("overhead_mean", row)
            self.assertIn("overhead_std", row)

        table = format_table_summary(rows)
        self.assertIn("Latency (ms)", table)
        self.assertIn("Throughput", table)
        self.assertIn("Overhead (%)", table)
        self.assertIn("±", table)


if __name__ == "__main__":
    unittest.main()
