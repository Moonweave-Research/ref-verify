import unittest

from ref_verify.claim_check import check_claim_support
from ref_verify.models import PaperRecord


class ClaimCheckTests(unittest.TestCase):
    def test_supported_when_claim_threshold_is_reported_as_actuated_strain(self):
        record = PaperRecord(
            doi="10.1000/example",
            title="Dielectric elastomer actuators",
            authors=["Pelrine", "Kornbluh"],
            year=2000,
            abstract=(
                "Actuated strains up to 117% were demonstrated with silicone "
                "elastomers, and up to 215% with acrylic elastomers."
            ),
            source="fixture",
        )

        result = check_claim_support(record, "actuation strain above 100%")

        self.assertEqual(result.status, "SUPPORTED")
        self.assertEqual(result.verdict, "ACCEPT")
        self.assertIn("117%", result.evidence)

    def test_supported_actuated_strain_even_when_sentence_mentions_prestrained_films(self):
        record = PaperRecord(
            doi="10.1000/science",
            title="High-speed electrically actuated elastomers",
            authors=["Pelrine"],
            year=2000,
            abstract=(
                "Actuated strains up to 117% were demonstrated with silicone "
                "elastomers, and up to 215% with acrylic elastomers using "
                "biaxially and uniaxially prestrained films."
            ),
            source="fixture",
        )

        result = check_claim_support(record, "actuation strain above 100%")

        self.assertEqual(result.status, "SUPPORTED")
        self.assertEqual(result.verdict, "ACCEPT")
        self.assertIn("117%", result.evidence)

    def test_supported_when_later_sentence_matches_quantitative_claim(self):
        record = PaperRecord(
            doi="10.1000/multisentence",
            title="Optimized elastomer actuators",
            authors=["Lee"],
            year=2024,
            abstract=(
                "Actuation strain below 50% was common in stiff samples. "
                "Actuated strains up to 117% were demonstrated."
            ),
            source="fixture",
        )

        result = check_claim_support(record, "actuation strain above 100%")

        self.assertEqual(result.status, "SUPPORTED")
        self.assertEqual(result.verdict, "ACCEPT")
        self.assertIn("117%", result.evidence)

    def test_partial_when_percentage_is_prestrain_not_actuation_output(self):
        record = PaperRecord(
            doi="10.1000/prestrain",
            title="Breakdown fields in elastomers",
            authors=["Kofod"],
            year=2003,
            abstract=(
                "Breakdown field was measured at 500% pre-strain for acrylic "
                "elastomers."
            ),
            source="fixture",
        )

        result = check_claim_support(record, "actuation strain above 100%")

        self.assertEqual(result.status, "PARTIAL")
        self.assertEqual(result.verdict, "WARN")
        self.assertIn("pre-strain", result.reason)

    def test_below_claim_is_not_supported_by_higher_abstract_percentage(self):
        record = PaperRecord(
            doi="10.1000/highstrain",
            title="Dielectric elastomer actuators",
            authors=["Pelrine"],
            year=2000,
            abstract="Actuated strains up to 117% were demonstrated.",
            source="fixture",
        )

        result = check_claim_support(record, "actuation strain below 50%")

        self.assertEqual(result.status, "PARTIAL")
        self.assertEqual(result.verdict, "WARN")
        self.assertIn("does not explicitly support", result.reason)

    def test_strict_lower_bound_claim_is_not_supported_by_exact_threshold(self):
        record = PaperRecord(
            doi="10.1000/exactstrain",
            title="Boundary strain actuator",
            authors=["Lee"],
            year=2020,
            abstract="Actuated strain reached 50% at the tested voltage.",
            source="fixture",
        )

        for phrase in ("below 50%", "under 50%", "less than 50%"):
            with self.subTest(phrase=phrase):
                result = check_claim_support(record, f"actuation strain {phrase}")

                self.assertEqual(result.status, "PARTIAL")
                self.assertEqual(result.verdict, "WARN")
                self.assertIn("does not explicitly support", result.reason)

    def test_at_most_claim_is_supported_by_lower_abstract_percentage(self):
        record = PaperRecord(
            doi="10.1000/lowstrain",
            title="Low strain actuator",
            authors=["Lee"],
            year=2020,
            abstract="Actuated strain reached 42% at the tested voltage.",
            source="fixture",
        )

        result = check_claim_support(record, "actuation strain at most 50%")

        self.assertEqual(result.status, "SUPPORTED")
        self.assertEqual(result.verdict, "ACCEPT")
        self.assertIn("42%", result.evidence)

    def test_exact_percentage_claim_requires_exact_value(self):
        exact_record = PaperRecord(
            doi="10.1000/exact",
            title="Exact strain actuator",
            authors=["Lee"],
            year=2020,
            abstract="Actuated strain reached 50% at the tested voltage.",
            source="fixture",
        )
        different_record = PaperRecord(
            doi="10.1000/different",
            title="Different strain actuator",
            authors=["Lee"],
            year=2020,
            abstract="Actuated strain reached 60% at the tested voltage.",
            source="fixture",
        )

        exact_result = check_claim_support(exact_record, "actuation strain 50%")
        different_result = check_claim_support(different_record, "actuation strain 50%")

        self.assertEqual(exact_result.status, "SUPPORTED")
        self.assertEqual(exact_result.verdict, "ACCEPT")
        self.assertEqual(different_result.status, "PARTIAL")
        self.assertEqual(different_result.verdict, "WARN")

    def test_exact_percentage_claim_is_not_supported_by_up_to_upper_bound(self):
        cases = (
            "Actuated strains up to 117% were demonstrated.",
            "Actuation strain was 117% or more.",
            "Actuation strain was 117% or less.",
        )

        for abstract in cases:
            with self.subTest(abstract=abstract):
                record = PaperRecord(
                    doi="10.1000/bounded",
                    title="Bounded strain actuator",
                    authors=["Lee"],
                    year=2020,
                    abstract=abstract,
                    source="fixture",
                )

                result = check_claim_support(record, "actuation strain 117%")

                self.assertEqual(result.status, "PARTIAL")
                self.assertEqual(result.verdict, "WARN")
                self.assertIn("does not explicitly support", result.reason)

    def test_unrelated_strain_percentage_in_same_sentence_does_not_support_claim(self):
        abstracts = (
            (
                "Actuated strain reached 42%, and the film tolerated 200% "
                "tensile strain before failure."
            ),
            (
                "Actuated strain reached 42% and the film tolerated 200% "
                "tensile strain before failure."
            ),
            (
                "Actuation strain reached 42%, voltage efficiency improved by "
                "200% under the same protocol."
            ),
        )

        for abstract in abstracts:
            with self.subTest(abstract=abstract):
                record = PaperRecord(
                    doi="10.1000/mixedstrain",
                    title="Mixed strain contexts",
                    authors=["Lee"],
                    year=2020,
                    abstract=abstract,
                    source="fixture",
                )

                result = check_claim_support(record, "actuation strain above 100%")

                self.assertEqual(result.status, "PARTIAL")
                self.assertEqual(result.verdict, "WARN")
                self.assertIn("does not explicitly support", result.reason)

    def test_tensile_strain_claim_is_not_supported_by_actuated_strain_context(self):
        record = PaperRecord(
            doi="10.1000/actuated",
            title="Actuated strain actuator",
            authors=["Lee"],
            year=2020,
            abstract="Actuated strains up to 117% were demonstrated.",
            source="fixture",
        )

        result = check_claim_support(record, "tensile strain above 100%")

        self.assertEqual(result.status, "PARTIAL")
        self.assertEqual(result.verdict, "WARN")
        self.assertIn("does not explicitly support", result.reason)

    def test_actuation_strain_claim_rejects_tensile_strain_during_actuation(self):
        record = PaperRecord(
            doi="10.1000/tensile-during-actuation",
            title="Tensile strain during actuation",
            authors=["Lee"],
            year=2020,
            abstract="The film tolerated 200% tensile strain during actuation.",
            source="fixture",
        )

        result = check_claim_support(record, "actuation strain above 100%")

        self.assertEqual(result.status, "PARTIAL")
        self.assertEqual(result.verdict, "WARN")
        self.assertIn("does not explicitly support", result.reason)

    def test_upper_bound_evidence_does_not_support_lower_bound_claim(self):
        cases = (
            (
                "Actuated strain remained below 50% throughout testing.",
                "actuation strain above 40%",
            ),
            (
                "Actuated strain remained under 50% throughout testing.",
                "actuation strain at least 45%",
            ),
            (
                "Actuated strain reached at most 50% at the tested voltage.",
                "actuation strain above 49%",
            ),
            (
                "Actuation strain was 117% or less.",
                "actuation strain above 100%",
            ),
            (
                "Actuation strain was 117% or more.",
                "actuation strain below 200%",
            ),
        )

        for abstract, claim in cases:
            with self.subTest(claim=claim):
                record = PaperRecord(
                    doi="10.1000/upperbound",
                    title="Upper bound actuator",
                    authors=["Lee"],
                    year=2020,
                    abstract=abstract,
                    source="fixture",
                )

                result = check_claim_support(record, claim)

                self.assertEqual(result.status, "PARTIAL")
                self.assertEqual(result.verdict, "WARN")
                self.assertIn("does not explicitly support", result.reason)

    def test_percentage_claim_rejects_contradictory_coordinated_context(self):
        cases = (
            "Actuated strain remained below 50%, and occasionally reached 60%.",
            "Actuated strain was below 50% but later reached 60%.",
            "Actuated strain stayed under 50% and later exceeded 60%.",
        )

        for abstract in cases:
            with self.subTest(abstract=abstract):
                record = PaperRecord(
                    doi="10.1000/coordinated",
                    title="Coordinated strain actuator",
                    authors=["Lee"],
                    year=2020,
                    abstract=abstract,
                    source="fixture",
                )

                result = check_claim_support(record, "actuation strain below 50%")

                self.assertEqual(result.status, "PARTIAL")
                self.assertEqual(result.verdict, "WARN")
                self.assertIn("does not explicitly support", result.reason)

    def test_percentage_claim_rejects_scope_qualified_context(self):
        cases = (
            ("Before treatment, actuation strain exceeded 117%.", "actuation strain above 100%"),
            (
                "Under standard conditions, actuation strain exceeded 117%.",
                "actuation strain above 100%",
            ),
            ("In saline solution, actuation strain exceeded 117%.", "actuation strain above 100%"),
            ("After annealing, actuation strain remained below 50%.", "actuation strain below 50%"),
            ("Actuation strain was below 50% before treatment.", "actuation strain below 50%"),
            ("Actuation strain exceeded 117% in saline solution.", "actuation strain above 100%"),
        )

        for abstract, claim in cases:
            with self.subTest(abstract=abstract):
                record = PaperRecord(
                    doi="10.1000/scoped-percentage",
                    title="Scoped percentage actuator",
                    authors=["Lee"],
                    year=2020,
                    abstract=abstract,
                    source="fixture",
                )

                result = check_claim_support(record, claim)

                self.assertEqual(result.status, "PARTIAL")
                self.assertEqual(result.verdict, "WARN")
                self.assertIn("does not explicitly support", result.reason)

    def test_percentage_claim_rejects_reporting_and_negation_frames(self):
        cases = (
            "We investigated whether actuation strain above 100% was achievable.",
            "It is not true that actuation strain exceeded 117% in this material.",
            "Actuation strain did not exceed 117% in any sample.",
            "Actuation strain cannot exceed 117% in this material.",
            "Actuation strain could not exceed 117% in this material.",
            "Actuation strain failed to exceed 117% in this material.",
            "Actuation strain was unable to exceed 117% in this material.",
            "Actuation strain was measured without exceeding 117%.",
            "No actuation strain above 100% was observed.",
            "No actuation strain exceeding 117% was observed.",
            "Actuation strain exceeded 117% in no sample.",
            "No sample showed actuation strain above 100%.",
            "None of the samples showed actuation strain above 100%.",
            "None showed actuation strain above 100%.",
            "None showed actuation strain exceeded 117%.",
            "Previous work reported actuation strain above 100% in acrylic films.",
            "According to prior work, actuation strain above 100% was observed.",
        )

        for abstract in cases:
            with self.subTest(abstract=abstract):
                record = PaperRecord(
                    doi="10.1000/reporting-percentage",
                    title="Reporting frame actuator",
                    authors=["Lee"],
                    year=2020,
                    abstract=abstract,
                    source="fixture",
                )

                result = check_claim_support(record, "actuation strain above 100%")

                self.assertEqual(result.status, "PARTIAL")
                self.assertEqual(result.verdict, "WARN")
                self.assertIn("does not explicitly support", result.reason)

    def test_supported_when_non_percentage_claim_is_stated_in_abstract(self):
        record = PaperRecord(
            doi="10.1000/lifetime",
            title="Hydrogel actuator lifetime",
            authors=["Lee"],
            year=2022,
            abstract=(
                "A hydrogel actuator showed 10% strain under 5 V. "
                "The device lifetime was 5000 cycles."
            ),
            source="fixture",
        )

        result = check_claim_support(record, "the device lifetime was 5000 cycles")

        self.assertEqual(result.status, "SUPPORTED")
        self.assertEqual(result.verdict, "ACCEPT")
        self.assertIn("5000 cycles", result.evidence)

    def test_non_percentage_claim_requires_matching_numeric_value(self):
        record = PaperRecord(
            doi="10.1000/lifetime",
            title="Hydrogel actuator lifetime",
            authors=["Lee"],
            year=2022,
            abstract="The device lifetime was 5000 cycles.",
            source="fixture",
        )

        result = check_claim_support(record, "the device lifetime was 10000 cycles")

        self.assertEqual(result.status, "PARTIAL")
        self.assertEqual(result.verdict, "WARN")
        self.assertIn("does not explicitly support", result.reason)

    def test_non_percentage_claim_rejects_comparative_suffix(self):
        cases = (
            "The device lifetime was 5000 cycles longer after annealing.",
            "The device lifetime was 5000 cycles or more after annealing.",
        )

        for abstract in cases:
            with self.subTest(abstract=abstract):
                record = PaperRecord(
                    doi="10.1000/comparative",
                    title="Hydrogel actuator lifetime",
                    authors=["Lee"],
                    year=2022,
                    abstract=abstract,
                    source="fixture",
                )

                result = check_claim_support(record, "the device lifetime was 5000 cycles")

                self.assertEqual(result.status, "PARTIAL")
                self.assertEqual(result.verdict, "WARN")
                self.assertIn("does not explicitly support", result.reason)

    def test_non_percentage_claim_rejects_reporting_frame(self):
        cases = (
            "We tested whether the device lifetime was 5000 cycles.",
            "Previous work reported the device lifetime was 5000 cycles.",
            "According to Lee, the device lifetime was 5000 cycles.",
            (
                "We investigated whether, under standard conditions and after "
                "annealing, the device lifetime was 5000 cycles."
            ),
        )

        for abstract in cases:
            with self.subTest(abstract=abstract):
                record = PaperRecord(
                    doi="10.1000/reporting",
                    title="Hydrogel actuator lifetime",
                    authors=["Lee"],
                    year=2022,
                    abstract=abstract,
                    source="fixture",
                )

                result = check_claim_support(record, "the device lifetime was 5000 cycles")

                self.assertEqual(result.status, "PARTIAL")
                self.assertEqual(result.verdict, "WARN")
                self.assertIn("does not explicitly support", result.reason)

    def test_non_percentage_claim_rejects_delayed_comparative_suffix(self):
        record = PaperRecord(
            doi="10.1000/delayed-comparative",
            title="Hydrogel actuator lifetime",
            authors=["Lee"],
            year=2022,
            abstract="The device lifetime was 5000 cycles, significantly longer after annealing.",
            source="fixture",
        )

        result = check_claim_support(record, "the device lifetime was 5000 cycles")

        self.assertEqual(result.status, "PARTIAL")
        self.assertEqual(result.verdict, "WARN")
        self.assertIn("does not explicitly support", result.reason)

    def test_non_percentage_claim_rejects_scope_qualifier_suffix(self):
        cases = (
            "Before treatment, healthy cells are stiffer than cancer cells.",
            "After annealing, the device lifetime was 5000 cycles.",
            "Under standard conditions, the device lifetime was 5000 cycles.",
            "In saline solution, the device lifetime was 5000 cycles.",
            (
                "The device lifetime was 5000 cycles before annealing and "
                "1000 cycles after annealing."
            ),
            "The device lifetime was 5000 cycles, then dropped to 1000 after annealing.",
            "The device lifetime was 5000 cycles in saline solution.",
            "Healthy cells are stiffer than cancer cells, but only before treatment.",
        )
        claims = (
            "healthy cells are stiffer than cancer cells",
            "the device lifetime was 5000 cycles",
            "the device lifetime was 5000 cycles",
            "the device lifetime was 5000 cycles",
            "the device lifetime was 5000 cycles",
            "the device lifetime was 5000 cycles",
            "the device lifetime was 5000 cycles",
            "healthy cells are stiffer than cancer cells",
        )

        for abstract, claim in zip(cases, claims):
            with self.subTest(abstract=abstract):
                record = PaperRecord(
                    doi="10.1000/scoped",
                    title="Scoped text claim",
                    authors=["Lee"],
                    year=2020,
                    abstract=abstract,
                    source="fixture",
                )

                result = check_claim_support(record, claim)

                self.assertEqual(result.status, "PARTIAL")
                self.assertEqual(result.verdict, "WARN")
                self.assertIn("does not explicitly support", result.reason)

    def test_non_percentage_claim_reversal_is_not_supported_by_same_words(self):
        record = PaperRecord(
            doi="10.1000/reversal",
            title="Cell stiffness reversal",
            authors=["Lee"],
            year=2020,
            abstract="Healthy cells are stiffer than cancer cells.",
            source="fixture",
        )

        result = check_claim_support(record, "cancer cells are stiffer than healthy cells")

        self.assertEqual(result.status, "PARTIAL")
        self.assertEqual(result.verdict, "WARN")
        self.assertIn("does not explicitly support", result.reason)

    def test_non_percentage_claim_negation_is_not_supported_by_same_words(self):
        cases = (
            "The device lifetime was not 5000 cycles.",
            "It is false that the device lifetime was 5000 cycles.",
            "The device lifetime was 5000 cycles in no sample.",
            "No sample had a device lifetime of 5000 cycles.",
            "None of the samples had a device lifetime of 5000 cycles.",
            "None showed the device lifetime was 5000 cycles.",
            "None showed that the device lifetime was 5000 cycles.",
        )

        for abstract in cases:
            with self.subTest(abstract=abstract):
                record = PaperRecord(
                    doi="10.1000/negation",
                    title="Device lifetime negation",
                    authors=["Lee"],
                    year=2020,
                    abstract=abstract,
                    source="fixture",
                )

                result = check_claim_support(record, "the device lifetime was 5000 cycles")

                self.assertEqual(result.status, "PARTIAL")
                self.assertEqual(result.verdict, "WARN")
                self.assertIn("does not explicitly support", result.reason)

    def test_unverifiable_without_abstract(self):
        record = PaperRecord(
            doi="10.1000/noabstract",
            title="Smart material paper",
            authors=["Kim"],
            year=2021,
            abstract=None,
            source="fixture",
        )

        result = check_claim_support(record, "actuation strain above 100%")

        self.assertEqual(result.status, "UNVERIFIABLE")
        self.assertEqual(result.verdict, "WARN")
        self.assertEqual(result.evidence, "")

    def test_absent_claim_is_warn_not_contradiction_without_explicit_conflict(self):
        record = PaperRecord(
            doi="10.1000/unrelated",
            title="Unrelated materials paper",
            authors=["Smith"],
            year=2020,
            abstract="The polymer film was characterized by optical microscopy.",
            source="fixture",
        )

        result = check_claim_support(record, "actuation strain above 100%")

        self.assertEqual(result.status, "PARTIAL")
        self.assertEqual(result.verdict, "WARN")
        self.assertIn("does not explicitly support", result.reason)


if __name__ == "__main__":
    unittest.main()
