import unittest
from pathlib import Path

from checker import (
    ABSTRACT_LEVEL_ONLY,
    CONTRADICTED,
    PARTIAL,
    SUPPORTED_ABSTRACT_LEVEL,
    SUPPORTED_FULL_TEXT,
    TIER_1,
    TIER_2,
    audit_claim,
    classify_claim_depth,
)


IONENE_ABSTRACT = """
Multifunctional ionene liquid crystal elastomers combine imidazolium backbones,
ionic liquid dopants, thermotropic actuation near 40 C, nascent electronic
conductivity, and self-sensing behavior.
"""

IONENE_FULL_TEXT = (Path(__file__).parent / "fixtures" / "ionene_lce_pmc.txt").read_text(
    encoding="utf-8"
)


class ClaimDepthTests(unittest.TestCase):
    def test_topic_claim_is_tier_1(self) -> None:
        claim = "This paper discusses ionene LCE actuation and self-sensing."

        self.assertEqual(classify_claim_depth(claim), TIER_1)

    def test_bulk_joule_heating_claim_is_tier_2(self) -> None:
        claim = "The LCE bulk itself Joule-heats by current through the bulk."

        self.assertEqual(classify_claim_depth(claim), TIER_2)


class ClaimAuditTests(unittest.TestCase):
    def test_tier_1_topic_claim_can_be_supported_by_abstract(self) -> None:
        result = audit_claim(
            "This paper discusses ionene LCE actuation and self-sensing.",
            abstract_text=IONENE_ABSTRACT,
        )

        self.assertEqual(result["depth"], TIER_1)
        self.assertEqual(result["content_status"], SUPPORTED_ABSTRACT_LEVEL)
        self.assertEqual(result["verdict"], "ACCEPT")

    def test_tier_2_claim_without_full_text_is_abstract_level_only(self) -> None:
        result = audit_claim(
            "The LCE bulk itself Joule-heats by current through the bulk.",
            abstract_text=IONENE_ABSTRACT,
        )

        self.assertEqual(result["depth"], TIER_2)
        self.assertEqual(result["content_status"], ABSTRACT_LEVEL_ONLY)
        self.assertEqual(result["verdict"], "WARN")

    def test_ionene_bulk_joule_heating_claim_is_contradicted_by_full_text(self) -> None:
        result = audit_claim(
            "The LCE bulk itself Joule-heats by current through the bulk.",
            abstract_text=IONENE_ABSTRACT,
            full_text=IONENE_FULL_TEXT,
        )

        self.assertEqual(result["depth"], TIER_2)
        self.assertEqual(result["content_status"], CONTRADICTED)
        self.assertEqual(result["verdict"], "REJECT")
        self.assertIn("LM layer served as a flexible Joule heater", result["evidence"])

    def test_adjacent_keywords_are_not_full_text_support(self) -> None:
        result = audit_claim(
            "The LCE bulk itself Joule-heats by current through the bulk.",
            full_text="The LCE showed conductivity. Joule heating was discussed in related soft actuators.",
        )

        self.assertEqual(result["content_status"], PARTIAL)
        self.assertEqual(result["verdict"], "WARN")

    def test_condition_bearing_mechanism_claim_requires_matching_full_text_sentence(self) -> None:
        result = audit_claim(
            "The LM electrode powered actuation at less than 3 V.",
            full_text="The controller modulated actuation by supplying a low voltage (<3 V) to the LM electrode.",
        )

        self.assertEqual(result["content_status"], SUPPORTED_FULL_TEXT)
        self.assertEqual(result["verdict"], "ACCEPT")


if __name__ == "__main__":
    unittest.main()
