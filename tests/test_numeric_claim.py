import json
import unittest
from pathlib import Path

from ref_verify.numeric_claim import check_numeric_claim_support, claim_quantities_supported


class ClaimQuantitiesTests(unittest.TestCase):
    def test_every_claim_number_needs_a_match(self):
        evidence = "The service lifetime was 16 years at 80 °C and 1.65 years at 100 °C."

        self.assertTrue(claim_quantities_supported("16 years at 80 °C", evidence))
        self.assertFalse(claim_quantities_supported("61 years at 80 °C", evidence))
        self.assertFalse(claim_quantities_supported("16 years at 90 °C", evidence))

    def test_units_prefixes_and_signs_must_match(self):
        cases = (
            ("Cells cycled for 2000 h at 0.1 mA cm −2.", "2000 h at 0.1 A cm−2", False),
            ("Cells cycled for 2000 h at 0.1 mA cm −2.", "2000 h at 0.1 mA cm−2", True),
            ("The response time was 42 ms.", "a response time of 42 s", False),
            ("Patients received 40 mg daily.", "40 g daily", False),
            ("Curcumin 8 grams/day was given.", "8 g/day", True),
            ("The modulus was 3 MPa.", "3 mPa", False),
            ("The film stayed flexible at −25 °C.", "flexible at 25 °C", False),
            ("The film stayed flexible at −25 °C.", "flexible at −25 °C", True),
        )

        for evidence, claim, expected in cases:
            with self.subTest(claim=claim):
                self.assertEqual(claim_quantities_supported(claim, evidence), expected)

    def test_reads_number_formats(self):
        cases = (
            ("an ionic conductivity of 3.14 × 10−4 S cm−1", "3.14 × 10−4 S cm−1", True),
            ("an ionic conductivity of 3.14 × 10−4 S cm−1", "3.14 × 10−3 S cm−1", False),
            ("stable for 10 000 cycles", "stable for 10,000 cycles", True),
            ("a pressure range of 0–6 kPa", "from 0 to 6 kPa", True),
            ("optimal at 50 and 60 nm, respectively", "60 nm", True),
            ("a sensitivity of 0.243 kPa −1", "0.243 kPa−1", True),
            ("κ = 2.56 ± 0.07 W/mK", "2.56 W/mK", True),
            ("SNC 700 reached 97.83% at −0.6 V vs. RHE", "97.83% at −0.8 V", False),
        )

        for evidence, claim, expected in cases:
            with self.subTest(claim=claim):
                self.assertEqual(claim_quantities_supported(claim, evidence), expected)

    def test_names_and_citation_markers_are_not_quantities(self):
        evidence = "COVID-19 patients received 40 mg of atorvastatin."

        self.assertTrue(claim_quantities_supported("COVID-19 patients received 40 mg [12]", evidence))
        self.assertTrue(claim_quantities_supported("40 mg of atorvastatin (Smith et al., 2024)", evidence))
        self.assertTrue(claim_quantities_supported("LiFePO4 and Fe2C cells with 40 mg", evidence))

    def test_comparators_and_direction_words(self):
        cases = (
            ("Selectivity reached up to 70.2%.", "selectivity above 60%", True),
            ("Selectivity reached up to 70.2%.", "selectivity over 70.2%", False),
            ("C1 selectivity was minimized to 19.0%.", "C1 selectivity exceeded 19.0%", False),
            ("The particle size was 518.9 nm.", "a particle size below 500 nm", False),
            ("The lifetime was ~5000 cycles.", "a lifetime of 5000 cycles", False),
            ("The lifetime was ~5000 cycles.", "a lifetime of about 5000 cycles", True),
            ("The value was higher than the reference of 11.85%.", "lower than the reference of 11.85%", False),
            ("The value was higher than the reference of 11.85%.", "higher than the reference of 11.85%", True),
        )

        for evidence, claim, expected in cases:
            with self.subTest(claim=claim):
                self.assertEqual(claim_quantities_supported(claim, evidence), expected)


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

    def test_upper_bounded_evidence_does_not_support_lower_bounded_claim(self):
        for abstract, claim in (
            ("The modulus was below 50 MPa.", "modulus above 40 MPa"),
            ("The breakdown field was at most 100 MV/m.", "breakdown field at least 80 MV/m"),
            ("The modulus was at least 50 MPa.", "modulus below 60 MPa"),
        ):
            with self.subTest(abstract=abstract, claim=claim):
                result = check_numeric_claim_support(abstract, claim)

                self.assertEqual(result.status, "PARTIAL")

    def test_one_sided_evidence_supports_claim_bounded_on_the_same_side(self):
        for abstract, claim in (
            ("The modulus was below 50 MPa.", "modulus below 60 MPa"),
            ("The modulus was at least 50 MPa.", "modulus above 40 MPa"),
        ):
            with self.subTest(abstract=abstract, claim=claim):
                result = check_numeric_claim_support(abstract, claim)

                self.assertEqual(result.status, "SUPPORTED")

    def test_milli_and_mega_prefixes_do_not_match(self):
        for abstract, claim in (
            ("The output voltage was 5 mV.", "output voltage of 5 MV"),
            ("The current reached 2 mA.", "current reached 2 MA"),
            ("The modulus was 3 MPa.", "modulus of 3 mPa"),
        ):
            with self.subTest(abstract=abstract, claim=claim):
                result = check_numeric_claim_support(abstract, claim)

                self.assertEqual(result.status, "PARTIAL")

    def test_lowercase_unit_prefix_stays_ambiguous(self):
        result = check_numeric_claim_support(
            "The output voltage was 5 mV.",
            "output voltage of 5 mv",
        )

        self.assertEqual(result.status, "SUPPORTED")


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
