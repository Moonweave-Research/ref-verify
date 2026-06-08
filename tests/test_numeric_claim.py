import json
import unittest
from pathlib import Path

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

    def test_accepts_matching_up_to_unit_claim(self):
        result = check_numeric_claim_support(
            "The device survived up to 3000 cycles.",
            "The device survived up to 3000 cycles.",
        )

        self.assertEqual(result.status, "SUPPORTED")
        self.assertIn("3000 cycles", result.evidence)

    def test_accepts_subject_matched_unit_claim(self):
        result = check_numeric_claim_support(
            "The device operated at 3.2 V.",
            "device operated at least 3 V",
        )

        self.assertEqual(result.status, "SUPPORTED")
        self.assertIn("3.2 V", result.evidence)

    def test_accepts_present_study_intro_with_subject_after_commas(self):
        result = check_numeric_claim_support(
            (
                "Hence, in the present study, we synthesized a 200 g scale of "
                "amorphous, hydrophobic as well as translucent, hyperbranched "
                "polymeric sulfur networks that provide high thermal resistance "
                "(>220 °C)."
            ),
            "The polymeric sulfur networks were synthesized on a 200 g scale.",
        )

        self.assertEqual(result.status, "SUPPORTED")
        self.assertIn("200 g", result.evidence)

    def test_rejects_wrong_subject_when_same_unit_repeats_across_commas(self):
        result = check_numeric_claim_support(
            "Device A survived 5000 cycles, Device B survived 1000 cycles.",
            "Device B survived 5000 cycles.",
        )

        self.assertEqual(result.status, "PARTIAL")

    def test_accepts_temperature_claim(self):
        result = check_numeric_claim_support(
            "Samples were maintained at 37 °C.",
            "samples maintained at 37 °C",
        )

        self.assertEqual(result.status, "SUPPORTED")
        self.assertIn("37 °C", result.evidence)

    def test_accepts_generic_measurement_subject_from_previous_sentence(self):
        result = check_numeric_claim_support(
            (
                "This paper reports electrical conductivity in wet polyimide. "
                "Measurements were carried out at 30 °C with electric fields in the range."
            ),
            "The conductivity measurements were carried out at 30 °C.",
        )

        self.assertEqual(result.status, "SUPPORTED")
        self.assertIn("30 °C", result.evidence)

    def test_rejects_previous_sentence_subject_for_qualified_measurements(self):
        result = check_numeric_claim_support(
            (
                "This paper reports electrical conductivity in wet polyimide. "
                "Tensile measurements were carried out at 30 °C."
            ),
            "The conductivity measurements were carried out at 30 °C.",
        )

        self.assertEqual(result.status, "PARTIAL")

    def test_rejects_comparative_evidence_for_exact_claim(self):
        cases = (
            "The polymer provided high thermal resistance (>220 °C).",
            "The polymer provided high thermal resistance at least 220 °C.",
            "The polymer provided high thermal resistance up to 220 °C.",
        )

        for abstract in cases:
            with self.subTest(abstract=abstract):
                result = check_numeric_claim_support(
                    abstract,
                    "polymer thermal resistance 220 °C",
                )

                self.assertEqual(result.status, "PARTIAL")

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

    def test_rejects_composite_unit_as_distinct_from_numerator_unit(self):
        result = check_numeric_claim_support(
            "The field strength was 18 MV.",
            "field strength was 18 MV/m",
        )

        self.assertEqual(result.status, "PARTIAL")

    def test_accepts_physical_science_units(self):
        cases = (
            (
                "The trap energy was estimated to be 1.7 eV.",
                "trap energy was 1.7 eV",
            ),
            (
                "The resistivity reached 10 ohm-cm.",
                "resistivity reached 10 Ω·cm",
            ),
            (
                "The conductivity reached 5 S/m.",
                "conductivity reached 5 S/m",
            ),
            (
                "The stress reached 120 MPa.",
                "stress reached 120 MPa",
            ),
        )

        for abstract, claim in cases:
            with self.subTest(claim=claim):
                result = check_numeric_claim_support(abstract, claim)

                self.assertEqual(result.status, "SUPPORTED")

    def test_accepts_physical_measurement_condition_suffixes(self):
        cases = (
            (
                (
                    "The effective work function for aluminum-polyimide is estimated "
                    "to be 1.7 eV in the temperature range between 100 and 270 °C."
                ),
                "effective work function for aluminum-polyimide is 1.7 eV",
            ),
            (
                "The conductivity reached 5 S/m at 1 kHz.",
                "conductivity reached 5 S/m",
            ),
            (
                "The stress reached 120 MPa at 300 K.",
                "stress reached 120 MPa",
            ),
            (
                (
                    "Conductivity measurements were carried out at 30 °C with "
                    "electric fields in the range."
                ),
                "conductivity measurements were carried out at 30 °C",
            ),
        )

        for abstract, claim in cases:
            with self.subTest(claim=claim):
                result = check_numeric_claim_support(abstract, claim)

                self.assertEqual(result.status, "SUPPORTED")

    def test_rejects_count_claim_condition_suffixes(self):
        result = check_numeric_claim_support(
            "The device lifetime was 5000 cycles at 5 V.",
            "device lifetime was 5000 cycles",
        )

        self.assertEqual(result.status, "PARTIAL")

    def test_rejects_missing_subject_binding(self):
        result = check_numeric_claim_support(
            "The device was tested extensively. A 95% response rate was observed.",
            "device efficiency above 90%",
        )

        self.assertEqual(result.status, "PARTIAL")


class NumericClaimEvalFixtureTests(unittest.TestCase):
    def test_numeric_claim_eval_fixture(self):
        fixture = Path(__file__).parent / "fixtures" / "numeric_claim_eval.jsonl"
        with fixture.open("r", encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle if line.strip()]

        self.assertGreaterEqual(len(rows), 7)
        self.assertEqual(
            {row["domain"] for row in rows},
            {"materials", "biomedicine", "machine-learning", "chemistry", "general-science"},
        )

        for row in rows:
            with self.subTest(row=row["id"]):
                result = check_numeric_claim_support(row["abstract"], row["claim"])
                self.assertEqual(result.status, row["expected_status"], row["why"])


if __name__ == "__main__":
    unittest.main()
