from pathlib import Path
import os
import subprocess
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
GITHUB_README_URL = "https://github.com/Moonweave-Research/ref-verify/blob/main/README.md"
GITHUB_KOREAN_README_URL = "https://github.com/Moonweave-Research/ref-verify/blob/main/README.ko.md"


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

        self.assertIn(f"[English]({GITHUB_README_URL})", readme)
        self.assertIn(f"[한국어]({GITHUB_KOREAN_README_URL})", readme)
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

    def test_korean_readme_matches_current_workflow_positioning(self):
        readme_ko = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")

        self.assertIn(f"[한국어]({GITHUB_KOREAN_README_URL})", readme_ko)
        self.assertIn(f"[English]({GITHUB_README_URL})", readme_ko)
        self.assertIn("연구 인용 검증용 에이전트 스킬", readme_ko)
        self.assertIn("스킬/플러그인 수준", readme_ko)
        self.assertIn("MCP 서버가 필요하지 않습니다", readme_ko)
        self.assertIn("ref-verify verify-doi", readme_ko)
        self.assertIn("ref-verify check-claim", readme_ko)
        self.assertIn("README.ko.md", readme_ko)
        self.assertIn("SKILL.md", readme_ko)

    def test_packaged_readme_uses_publish_safe_language_links(self):
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn('readme = "README.md"', pyproject)
        self.assertIn(GITHUB_README_URL, readme)
        self.assertIn(GITHUB_KOREAN_README_URL, readme)
        self.assertNotIn("[English](README.md)", readme)
        self.assertNotIn("[한국어](README.ko.md)", readme)

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
