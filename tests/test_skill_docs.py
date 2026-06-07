from pathlib import Path
import os
import subprocess
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


class SkillDocsTests(unittest.TestCase):
    def test_skill_defines_cli_first_fallback_workflow(self):
        skill = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")

        required_phrases = (
            "CLI Availability Check",
            "ref-verify --help",
            "python3 -m ref_verify.cli --help",
            "python3 -m ref_verify.cli verify-doi",
            "python3 -m ref_verify.cli check-claim",
            "CLI-first workflow",
            "verify-doi",
            "check-claim",
            "PASS",
            "ACCEPT",
            "UNVERIFIABLE",
            "manual fallback",
            "Do not build or require MCP",
        )

        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, skill)

    def test_readme_positions_cli_as_skill_execution_engine_not_mcp(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("agent skill for citation verification", readme)
        self.assertIn("skill/plugin-level", readme)
        self.assertIn("skill-level execution engine", readme)
        self.assertIn("No MCP server is required for this workflow", readme)
        self.assertIn("You do not start a server and you do not configure MCP", readme)
        self.assertIn("Still handled by the skill protocol", readme)
        self.assertIn("ref-verify --help", readme)
        self.assertIn("python3 -m ref_verify.cli verify-doi", readme)
        self.assertIn("python3 -m ref_verify.cli check-claim", readme)
        self.assertNotIn("future MCP", readme)

    def test_source_checkout_module_subcommands_are_runnable(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")

        commands = (
            [sys.executable, "-m", "ref_verify.cli", "verify-doi", "--help"],
            [sys.executable, "-m", "ref_verify.cli", "check-claim", "--help"],
        )

        for command in commands:
            with self.subTest(command=" ".join(command)):
                result = subprocess.run(
                    command,
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage: ref-verify", result.stdout)


if __name__ == "__main__":
    unittest.main()
