from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = REPO_ROOT / "web"
PACKAGE_DIR = REPO_ROOT / "src" / "ref_verify"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the static browser page: web/ plus the ref_verify package as a zip.",
    )
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "_site")
    args = parser.parse_args()

    out = args.out.resolve()
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(WEB_DIR, out, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    with zipfile.ZipFile(out / "ref_verify.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for source in sorted(PACKAGE_DIR.glob("*.py")):
            archive.write(source, f"ref_verify/{source.name}")
    print(f"Built {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
