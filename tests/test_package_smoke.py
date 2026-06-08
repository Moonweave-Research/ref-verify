import unittest

from scripts.package_smoke import _cli_smoke_commands, _contains_skill_file


class PackageSmokeTests(unittest.TestCase):
    def test_detects_top_level_skill_file(self):
        self.assertTrue(_contains_skill_file({"SKILL.md"}))

    def test_detects_nested_skill_file(self):
        cases = (
            {"ref_verify/SKILL.md"},
            {"ref_verify-1.1.1.data/data/SKILL.md"},
            {"nested/path/SKILL.md"},
        )

        for names in cases:
            with self.subTest(names=names):
                self.assertTrue(_contains_skill_file(names))

    def test_allows_non_skill_files(self):
        self.assertFalse(
            _contains_skill_file(
                {
                    "ref_verify/cli.py",
                    "ref_verify-1.1.1.dist-info/METADATA",
                    "docs/SKILL_NOTES.md",
                }
            )
        )

    def test_cli_smoke_commands_cover_batch_subcommand(self):
        commands = _cli_smoke_commands("ref-verify")

        self.assertIn(["ref-verify", "check-file", "--help"], commands)


if __name__ == "__main__":
    unittest.main()
