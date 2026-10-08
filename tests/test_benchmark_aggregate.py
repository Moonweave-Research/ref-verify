import unittest

from scripts.benchmark_references import aggregate, wilson_interval


def _row(category, outcome, error_code=None, **extra):
    return {"id": f"{category}-{outcome}", "category": category, "outcome": outcome, "error_code": error_code, **extra}


class BenchmarkAggregateTests(unittest.TestCase):
    def test_wilson_interval_matches_known_values(self):
        low, high = wilson_interval(8, 10)
        self.assertAlmostEqual(low, 0.4902, places=3)
        self.assertAlmostEqual(high, 0.9433, places=3)
        self.assertEqual(wilson_interval(0, 0), None)
        low, high = wilson_interval(10, 10)
        self.assertEqual(high, 1.0)
        self.assertGreater(low, 0.69)

    def test_rates_use_each_category_as_denominator(self):
        results = [
            _row("REAL", "pass"),
            _row("REAL", "pass"),
            _row("REAL", "warn"),
            _row("REAL", "reject"),
            _row("FABRICATED", "reject", subtype="a_invented_doi"),
            _row("FABRICATED", "warn", subtype="b_no_doi"),
            _row("FABRICATED", "pass", subtype="b_no_doi"),
            _row("RETRACTED", "reject", "PAPER_RETRACTED", crossref_marks_retraction=True),
            _row("RETRACTED", "reject", "DOI_NOT_FOUND", crossref_marks_retraction=True),
            _row("RETRACTED", "pass", crossref_marks_retraction=False),
            _row("NOT_IN_CROSSREF", "warn"),
            _row("NOT_IN_CROSSREF", "reject", "DOI_NOT_FOUND"),
        ]

        summary = aggregate(results)

        self.assertEqual(summary["real_clean_pass"]["k"], 2)
        self.assertEqual(summary["real_clean_pass"]["n"], 4)
        self.assertEqual(summary["real_needs_check"]["k"], 1)
        self.assertEqual(summary["real_wrongly_rejected"]["k"], 1)
        self.assertEqual(summary["fabricated_flagged"]["k"], 2)
        self.assertEqual(summary["fabricated_flagged"]["n"], 3)
        self.assertEqual(summary["fabricated_flagged_by_type"]["b_no_doi"]["k"], 1)
        self.assertEqual(summary["fabricated_flagged_by_type"]["b_no_doi"]["n"], 2)
        # Only a PAPER_RETRACTED verdict counts, and only for CrossRef-marked retractions.
        self.assertEqual(summary["retracted_rejected"]["k"], 1)
        self.assertEqual(summary["retracted_rejected"]["n"], 2)
        self.assertEqual(summary["retracted_not_marked_by_crossref"], 1)
        self.assertEqual(summary["unindexed_rejected"]["k"], 1)
        self.assertEqual(summary["composition"]["REAL"], {"n": 4, "pass": 2, "warn": 1, "reject": 1})

    def test_pass_on_a_different_record_is_reported(self):
        results = [
            _row("REAL", "pass", truth_doi="10.1/A", fetched_doi="10.1/a", id="right"),
            _row("REAL", "pass", truth_doi="10.1/A", resolved_doi="10.1/review-of-a", id="wrong"),
            _row("NOT_IN_CROSSREF", "pass", resolved_doi="10.1/b", id="no-truth"),
        ]

        self.assertEqual(aggregate(results)["pass_on_wrong_record"], ["wrong"])

    def test_infrastructure_errors_are_excluded_from_rates(self):
        results = [
            _row("REAL", "pass"),
            _row("REAL", "warn", "ROW_CHECK_ERROR"),
        ]

        summary = aggregate(results)

        self.assertEqual(summary["infra_errors"], 1)
        self.assertEqual(summary["real_clean_pass"]["n"], 1)
        self.assertEqual(summary["real_clean_pass"]["rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
