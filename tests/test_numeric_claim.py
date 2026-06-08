import unittest

from ref_verify.numeric_claim import check_numeric_claim_support


class NumericClaimTests(unittest.TestCase):
    def test_accepts_subject_matched_percent_claim(self):
        result = check_numeric_claim_support(
            "Device efficiency reached 95%.",
            "device efficiency above 90%",
        )

        self.assertEqual(result.status, "SUPPORTED")
        self.assertIn("95%", result.evidence)

    def test_accepts_subject_matched_count_claim(self):
        result = check_numeric_claim_support(
            "The actuator survived 5000 cycles.",
            "actuator survived at least 4000 cycles",
        )

        self.assertEqual(result.status, "SUPPORTED")
        self.assertIn("5000 cycles", result.evidence)

    def test_accepts_subject_matched_unit_claim(self):
        result = check_numeric_claim_support(
            "The device operated at 3.2 V.",
            "device operated at least 3 V",
        )

        self.assertEqual(result.status, "SUPPORTED")
        self.assertIn("3.2 V", result.evidence)

    def test_accepts_temperature_claim(self):
        result = check_numeric_claim_support(
            "Samples were maintained at 37 °C.",
            "samples maintained at 37 °C",
        )

        self.assertEqual(result.status, "SUPPORTED")
        self.assertIn("37 °C", result.evidence)

    def test_accepts_concentration_claim(self):
        result = check_numeric_claim_support(
            "Cells were treated with 10 mg/mL polymer.",
            "cells treated with 10 mg/mL polymer",
        )

        self.assertEqual(result.status, "SUPPORTED")
        self.assertIn("10 mg/mL", result.evidence)

    def test_rejects_wrong_subject_number_in_same_sentence(self):
        result = check_numeric_claim_support(
            "Device efficiency reached 80%, and response rate was 95%.",
            "device efficiency above 90%",
        )

        self.assertEqual(result.status, "PARTIAL")

    def test_rejects_wrong_unit(self):
        cases = (
            (
                "The device operated at 3.2 mA.",
                "device operated at least 3 V",
            ),
            (
                "Cells were treated with 10 mg polymer.",
                "cells treated with 10 mg/mL polymer",
            ),
        )

        for abstract, claim in cases:
            with self.subTest(claim=claim):
                result = check_numeric_claim_support(abstract, claim)

                self.assertEqual(result.status, "PARTIAL")

    def test_rejects_missing_subject_binding(self):
        result = check_numeric_claim_support(
            "The device was tested extensively. A 95% response rate was observed.",
            "device efficiency above 90%",
        )

        self.assertEqual(result.status, "PARTIAL")


if __name__ == "__main__":
    unittest.main()
