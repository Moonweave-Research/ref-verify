from pathlib import Path
import os
import subprocess
import tempfile
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
GITHUB_README_URL = "https://github.com/Moonweave-Research/ref-verify/blob/main/README.md"
GITHUB_KOREAN_README_URL = "https://github.com/Moonweave-Research/ref-verify/blob/main/README.ko.md"
GITHUB_AGENT_USAGE_URL = "https://github.com/Moonweave-Research/ref-verify/blob/main/AGENT_USAGE.md"
RAW_MARK_URL = (
    "https://raw.githubusercontent.com/Moonweave-Research/ref-verify/"
    "main/.github/assets/ref-verify-mark-512.png"
)
CHECK_CLAIM_ERROR_CODES = (
    "CLAIM_SUPPORTED",
    "CLAIM_NOT_EXPLICIT",
    "CLAIM_AMBIGUOUS",
    "NO_ABSTRACT",
    "DOI_NOT_FOUND",
    "DOI_MISMATCH",
    "SOURCE_API_ERROR",
    "SOURCE_TIMEOUT",
    "SOURCE_RATE_LIMITED",
    "SOURCE_UNSUPPORTED",
    "PAPER_RETRACTED",
)
CHECK_BIB_ERROR_CODES = ("REFERENCE_RESOLVED", "REFERENCE_UNMATCHED", "DOI_NOT_IN_CROSSREF")
AGENT_USAGE_ERROR_CODES = CHECK_CLAIM_ERROR_CODES + ("ROW_CHECK_ERROR",) + CHECK_BIB_ERROR_CODES
GITHUB_REFERENCE_URL = "https://github.com/Moonweave-Research/ref-verify/blob/main/docs/REFERENCE.md"
GITHUB_KOREAN_REFERENCE_URL = "https://github.com/Moonweave-Research/ref-verify/blob/main/docs/REFERENCE.ko.md"


def _user_docs(korean=False):
    # The README keeps the story; commands, modes, error codes, cache, and scope live in
    # docs/REFERENCE*.md. Facts the README used to carry must still be in one of the two.
    readme = "README.ko.md" if korean else "README.md"
    reference = "REFERENCE.ko.md" if korean else "REFERENCE.md"
    return (REPO_ROOT / readme).read_text(encoding="utf-8") + "\n" + (REPO_ROOT / "docs" / reference).read_text(
        encoding="utf-8"
    )


class SkillDocsTests(unittest.TestCase):
    def assertInOrder(self, text, phrases):
        last_index = -1
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                index = text.find(phrase)
                self.assertNotEqual(index, -1, f"{phrase!r} not found")
                self.assertGreater(index, last_index, f"{phrase!r} is out of order")
                last_index = index

    def test_skill_defines_cli_first_fallback_workflow(self):
        skill = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")

        required_phrases = (
            "CLI Availability Check",
            "ref-verify --help",
            "python3 -m ref_verify.cli --help",
            "npx skills add does not pip-install the Python CLI",
            "python3 -m ref_verify.cli verify-doi",
            "python3 -m ref_verify.cli check-claim",
            "CLI-first workflow",
            "verify-doi",
            "check-claim",
            "DOI-bound abstract claim checks",
            "OpenAlex, Semantic Scholar, and PubMed fallback",
            "abstract_source",
            "source_attempts",
            "error_code",
            "PASS",
            "ACCEPT",
            "UNVERIFIABLE",
            "manual fallback",
            "Do not build or require MCP",
        )

        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, skill)

        self.assertNotIn("CrossRef-abstract claim checks", skill)
        self.assertNotIn("CrossRef did not expose enough abstract evidence", skill)
        self.assertIn("CrossRef/OpenAlex/S2/Unpaywall/arXiv/PubMed", skill)
        for code in CHECK_CLAIM_ERROR_CODES + CHECK_BIB_ERROR_CODES:
            with self.subTest(error_code=code):
                self.assertIn(code, skill)
        self.assertIn('PYTHONPATH="$SKILL_DIR/src" python3 -m ref_verify.cli check-bib', skill)

    def test_skill_requires_source_depth_for_mechanism_claims(self):
        skill = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")

        required_skill_phrases = (
            "mechanism/implementation/procedural claims",
            "CLI `ACCEPT` is abstract-level evidence only",
            "Full-Text Confirmation",
            "content supported at the required source depth",
            "fetched source text at the required depth",
            "CONTENT: ABSTRACT-ONLY",
        )
        for phrase in required_skill_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, skill)

        self.assertNotIn("/Users/", skill)
        self.assertNotIn("verify@ref-verify.local", skill)
        self.assertIn("manual Full Audit protocol", _user_docs())
        self.assertIn("수동 Full Audit 프로토콜", _user_docs(korean=True))

    def test_readme_positions_cli_as_skill_execution_engine_not_mcp(self):
        front = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme = _user_docs()

        self.assertIn(f"[English]({GITHUB_README_URL})", front)
        self.assertIn(f"[한국어]({GITHUB_KOREAN_README_URL})", front)
        self.assertIn(RAW_MARK_URL, front)
        self.assertIn("agent skill for citation verification", front)
        self.assertIn("--skill ref-verify", front)
        self.assertIn("--agent claude-code cursor codex", front)
        self.assertIn(f"[AGENT_USAGE.md]({GITHUB_AGENT_USAGE_URL})", front)
        self.assertIn(f"]({GITHUB_REFERENCE_URL}", front)
        self.assertIn("ref-verify check-bib", front)
        self.assertIn("--report report.html", front)
        self.assertIn("skill/plugin-level", readme)
        self.assertIn("skill-level execution engine", readme)
        self.assertIn("No MCP server is required for this workflow", readme)
        self.assertIn("You do not start a server and you do not configure MCP", readme)
        self.assertIn("DOI-bound abstract claim check", readme)
        self.assertIn("OpenAlex, Semantic Scholar, and PubMed fallback", readme)
        self.assertIn("Current `check-claim` error codes", readme)
        self.assertIn("CLAIM_NOT_EXPLICIT", readme)
        self.assertIn("SOURCE_TIMEOUT", readme)
        for code in CHECK_CLAIM_ERROR_CODES + CHECK_BIB_ERROR_CODES:
            with self.subTest(error_code=code):
                self.assertIn(code, readme)
        self.assertIn("ref-verify check-bib", readme)
        self.assertIn("--report report.html", readme)
        self.assertIn("literal text claims", readme)
        self.assertIn("subject-matched percentage claims", readme)
        self.assertIn("simple unit/count claims", readme)
        self.assertIn("p-values, AUC/AUROC, F1 score", readme)
        self.assertIn("ref-verify --help", readme)
        self.assertIn("python3 -m ref_verify.cli verify-doi", readme)
        self.assertIn("python3 -m ref_verify.cli check-claim", readme)
        self.assertNotIn("future MCP", readme)

    def test_korean_readme_matches_current_workflow_positioning(self):
        front_ko = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        readme_ko = _user_docs(korean=True)

        self.assertIn(f"[한국어]({GITHUB_KOREAN_README_URL})", front_ko)
        self.assertIn(f"[English]({GITHUB_README_URL})", front_ko)
        self.assertIn(RAW_MARK_URL, front_ko)
        self.assertIn("연구 인용 검증용 에이전트 스킬", front_ko)
        self.assertIn("--skill ref-verify", front_ko)
        self.assertIn("--agent claude-code cursor codex", front_ko)
        self.assertIn(f"[AGENT_USAGE.md]({GITHUB_AGENT_USAGE_URL})", front_ko)
        self.assertIn(f"]({GITHUB_KOREAN_REFERENCE_URL}", front_ko)
        self.assertIn("ref-verify check-bib", front_ko)
        self.assertIn("--report report.html", front_ko)
        self.assertIn("README.ko.md", front_ko)
        self.assertIn("SKILL.md", front_ko)
        self.assertIn("스킬/플러그인 수준", readme_ko)
        self.assertIn("MCP 서버가 필요하지 않습니다", readme_ko)
        self.assertIn("문장 그대로 드러나는 text claim", readme_ko)
        self.assertIn("subject가 일치하는 percentage claim", readme_ko)
        self.assertIn("단순 unit/count claim", readme_ko)
        self.assertIn("AUC/AUROC, F1 score", readme_ko)
        self.assertIn("현재 `check-claim` error code", readme_ko)
        self.assertIn("CLAIM_NOT_EXPLICIT", readme_ko)
        self.assertIn("SOURCE_TIMEOUT", readme_ko)
        for code in CHECK_CLAIM_ERROR_CODES + CHECK_BIB_ERROR_CODES:
            with self.subTest(error_code=code):
                self.assertIn(code, readme_ko)
        self.assertIn("ref-verify check-bib", readme_ko)
        self.assertIn("--report report.html", readme_ko)
        self.assertIn("ref-verify verify-doi", readme_ko)
        self.assertIn("ref-verify check-claim", readme_ko)

    def test_packaged_readme_uses_publish_safe_language_links(self):
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")

        self.assertIn('readme = "README.md"', pyproject)
        self.assertIn('requires = ["setuptools>=77"]', pyproject)
        self.assertIn('license = "MIT"', pyproject)
        self.assertIn(GITHUB_README_URL, readme)
        self.assertIn(GITHUB_KOREAN_README_URL, readme)
        self.assertNotIn("[English](README.md)", readme)
        self.assertNotIn("[한국어](README.ko.md)", readme)
        self.assertNotIn('src=".github/', readme)
        self.assertNotIn('src=".github/', readme_ko)

    def test_python_package_is_documented_as_cli_only(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")

        self.assertIn("The Python package is CLI-only", readme)
        self.assertIn("does not install `SKILL.md`", readme)
        self.assertIn("install the agent skill from GitHub", readme)
        self.assertIn("Python 패키지는 CLI 전용", readme_ko)
        self.assertIn("`SKILL.md`를 설치하지 않습니다", readme_ko)
        self.assertIn("GitHub에서 설치합니다", readme_ko)

    def test_agent_usage_contract_defines_routing_rules(self):
        usage = (REPO_ROOT / "AGENT_USAGE.md").read_text(encoding="utf-8")

        required_phrases = (
            "`ref-verify` is a verifier, not a claim extractor",
            "ref-verify check-file claims.jsonl --json",
            "Treat only `verdict == \"ACCEPT\"` as verified",
            "Exit `0`: command completed and every row was `ACCEPT`",
            "Exit `2`: command completed, but one or more rows were not accepted",
            "Exit `1`: input or runtime failure prevented normal batch processing",
            "Agents must inspect JSON output even when the exit code is non-zero",
            "Summary categories are diagnostic counts, not mutually exclusive buckets",
            "Do not use `ref-verify` to judge paper quality",
            "Do not fill missing abstract evidence from memory",
            "CSV is supported for user-created files, but agents should prefer JSONL",
            "ROW_CHECK_ERROR",
            "failed > 0",
            "ref-verify check-bib references.bib --json",
            "never call it fabricated",
        )

        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, usage)
        for code in AGENT_USAGE_ERROR_CODES:
            with self.subTest(error_code=code):
                self.assertIn(code, usage)

    def test_cli_network_requirement_is_explicit(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

        self.assertIn("zero third-party Python runtime dependencies", readme)
        self.assertIn("outbound HTTPS access", readme)
        self.assertIn("CrossRef, OpenAlex, Semantic Scholar, and PubMed", readme)
        self.assertIn("third-party Python runtime dependency", readme_ko)
        self.assertIn("outbound HTTPS", readme_ko)
        self.assertIn("CrossRef, OpenAlex, Semantic Scholar, PubMed", readme_ko)
        self.assertIn("zero third-party Python packages", changelog)
        self.assertIn("outbound HTTPS access", changelog)

    def test_package_version_matches_module_version(self):
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        init = (REPO_ROOT / "src" / "ref_verify" / "__init__.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('version = "1.3.2"', pyproject)
        self.assertIn('__version__ = "1.3.2"', init)

    def test_skill_runs_bundled_engine_by_absolute_path(self):
        # npx skills add copies src/ next to SKILL.md but installs no console script, and the
        # agent's working directory is the user's project, so a relative PYTHONPATH=src fails.
        skill = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")

        self.assertNotIn("PYTHONPATH=src ", skill)
        self.assertIn('PYTHONPATH="$SKILL_DIR/src" python3 -m ref_verify.cli --help', skill)
        self.assertIn('PYTHONPATH="$SKILL_DIR/src" python3 -m ref_verify.cli verify-doi', skill)
        self.assertIn('PYTHONPATH="$SKILL_DIR/src" python3 -m ref_verify.cli check-claim', skill)
        self.assertInOrder(skill, ("$SKILL_DIR/src", "ref-verify --help", "uvx --from 'ref-verify>=1.3.2'"))

    def test_bundled_engine_runs_from_another_working_directory(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        with tempfile.TemporaryDirectory() as project:
            result = subprocess.run(
                [sys.executable, "-m", "ref_verify.cli", "--help"],
                cwd=project,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("verify-doi", result.stdout)

    def test_readmes_prioritize_user_workflow_before_architecture_details(self):
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ko = (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8")
        reference = (REPO_ROOT / "docs" / "REFERENCE.md").read_text(encoding="utf-8")
        reference_ko = (REPO_ROOT / "docs" / "REFERENCE.ko.md").read_text(encoding="utf-8")

        self.assertInOrder(
            readme,
            (
                "## Try it in 30 seconds",
                "## How to read a result",
                "## Three ways to use it",
                "## Scorecard",
                "## What it checks and what it does not",
                "## Privacy and network use",
                "## For AI agents",
                "## More documentation",
                "## Contributing, license, and related projects",
            ),
        )
        self.assertInOrder(
            readme_ko,
            (
                "## 30초 만에 써 보기",
                "## 결과 읽는 법",
                "## 세 가지 사용 방법",
                "## 채점표",
                "## 확인하는 것과 확인하지 않는 것",
                "## 개인정보와 네트워크",
                "## AI 에이전트를 위한 안내",
                "## 더 자세한 문서",
                "## 기여, 라이선스, 관련 프로젝트",
            ),
        )
        # Reference material stays in the reference documents, in the same order in both languages.
        self.assertInOrder(
            reference,
            ("## Agent skill", "## Checking a reference list", "## Command-line engine", "## Modes",
             "## Error codes", "## Saved reports", "## Cache", "## Scope", "## What it catches", "## Examples"),
        )
        self.assertInOrder(
            reference_ko,
            ("## 에이전트 스킬", "## 참고문헌 목록 점검", "## 명령줄 엔진", "## 모드",
             "## 오류 코드", "## 저장한 보고서", "## 캐시", "## 범위", "## 잡아내는 문제", "## 예시"),
        )
        # Both languages keep the same section structure so a reader can switch.
        for english, korean in ((readme, readme_ko), (reference, reference_ko)):
            self.assertEqual(
                [line.split()[0] for line in english.splitlines() if line.startswith("#")],
                [line.split()[0] for line in korean.splitlines() if line.startswith("#")],
            )

    def test_readmes_avoid_cli_scope_contradictions_and_internal_first_language(self):
        readme = _user_docs()
        readme_ko = _user_docs(korean=True)

        self.assertIn("No server setup is required", (REPO_ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn("서버를 시작하거나 MCP를 설정할 필요가 없습니다", (REPO_ROOT / "README.ko.md").read_text(encoding="utf-8"))
        self.assertIn("CrossRef metadata check", readme)
        self.assertIn("DOI-bound abstract claim check", readme)
        self.assertIn("CrossRef 메타데이터 확인", readme_ko)
        self.assertIn("DOI에 묶인 abstract 기반 주장 확인", readme_ko)
        self.assertIn("DOI landing-page checks still use the skill protocol", readme)
        self.assertIn("DOI landing page 확인은 스킬 프로토콜을 따릅니다", readme_ko)
        self.assertNotIn("Hits CrossRef, confirms title + author match, verifies DOI resolves", readme)
        self.assertNotIn("현재 구현은 의도적으로", readme_ko)
        self.assertNotIn("논문이 실제로 말하지 않은 내용을 인용하지 않게 막습니다", readme_ko)

    def test_korean_readme_localizes_user_facing_examples(self):
        reference_ko = (REPO_ROOT / "docs" / "REFERENCE.ko.md").read_text(encoding="utf-8")
        examples = reference_ko.split("## 예시", 1)[1]

        self.assertIn("사용자:", examples)
        self.assertIn("내용: 뒷받침됨", examples)
        self.assertIn("출처:", examples)
        self.assertIn("Near-miss 인용", examples)
        self.assertNotIn("User:", examples)
        self.assertNotIn("CONTENT:", examples)
        self.assertNotIn("[Source:", examples)
        self.assertNotIn("**Near-miss citation**", examples)

    def test_source_checkout_module_subcommands_are_runnable(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")

        commands = (
            [sys.executable, "-m", "ref_verify.cli", "verify-doi", "--help"],
            [sys.executable, "-m", "ref_verify.cli", "check-claim", "--help"],
            [sys.executable, "-m", "ref_verify.cli", "check-bib", "--help"],
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
