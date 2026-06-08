from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install a built ref-verify wheel and smoke-test the CLI.",
    )
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--expected-version", required=True)
    args = parser.parse_args()

    wheel = args.wheel.resolve()
    if not wheel.exists():
        print(f"wheel not found: {wheel}", file=sys.stderr)
        return 2
    if wheel.suffix != ".whl":
        print(f"expected a .whl file: {wheel}", file=sys.stderr)
        return 2

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    if _contains_skill_file(names):
        print("SKILL.md must not be packaged in the CLI-only wheel", file=sys.stderr)
        return 1
    if not any(name.endswith(".dist-info/entry_points.txt") for name in names):
        print("wheel is missing console-script entry point metadata", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="ref-verify-wheel-smoke-") as temp_dir:
        venv_dir = Path(temp_dir) / "venv"
        _run([sys.executable, "-m", "venv", str(venv_dir)])
        python = _venv_bin(venv_dir, "python")
        pip = _venv_bin(venv_dir, "pip")
        ref_verify = _venv_bin(venv_dir, "ref-verify")

        _run([str(pip), "install", str(wheel)])
        for command in _cli_smoke_commands(str(ref_verify)):
            _run(command)
        completed = _run(
            [
                str(python),
                "-c",
                "import ref_verify; print(ref_verify.__version__)",
            ],
            capture_output=True,
        )
        actual_version = completed.stdout.strip()
        if actual_version != args.expected_version:
            print(
                f"version mismatch: expected {args.expected_version}, got {actual_version}",
                file=sys.stderr,
            )
            return 1

    return 0


def _venv_bin(venv_dir: Path, name: str) -> Path:
    return venv_dir / ("Scripts" if sys.platform == "win32" else "bin") / name


def _contains_skill_file(names: set[str]) -> bool:
    return any(Path(name).name == "SKILL.md" for name in names)


def _cli_smoke_commands(ref_verify: str) -> list[list[str]]:
    return [
        [ref_verify, "--help"],
        [ref_verify, "check-claim", "--help"],
        [ref_verify, "check-file", "--help"],
    ]


def _run(
    command: list[str],
    *,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=capture_output,
    )


if __name__ == "__main__":
    raise SystemExit(main())
