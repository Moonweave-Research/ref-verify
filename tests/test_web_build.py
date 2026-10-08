import ast
import importlib
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = REPO_ROOT / "web"


class WebBuildTests(unittest.TestCase):
    def test_build_copies_page_and_packages_every_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / "build_web.py"), "--out", str(out)],
                check=True,
                capture_output=True,
            )
            for name in ("index.html", "app.js", "app.css", "worker.js", "engine.py", "ref_verify.zip"):
                with self.subTest(name=name):
                    self.assertTrue((out / name).is_file())
            with zipfile.ZipFile(out / "ref_verify.zip") as archive:
                packaged = set(archive.namelist())

        modules = {f"ref_verify/{path.name}" for path in (REPO_ROOT / "src" / "ref_verify").glob("*.py")}
        self.assertEqual(packaged, modules)

    def test_browser_glue_imports_names_the_engine_still_has(self):
        # web/engine.py only runs inside Pyodide, so check its ref_verify imports here.
        tree = ast.parse((WEB_DIR / "engine.py").read_text(encoding="utf-8"))
        imports = [
            (node.module, alias.name)
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("ref_verify")
            for alias in node.names
        ]
        self.assertTrue(imports)
        for module, name in imports:
            with self.subTest(module=module, name=name):
                parent = importlib.import_module(module)
                if not hasattr(parent, name):
                    importlib.import_module(f"{module}.{name}")

    def test_worker_pins_one_exact_pyodide_version(self):
        worker = (WEB_DIR / "worker.js").read_text(encoding="utf-8")
        versions = set(re.findall(r"cdn\.jsdelivr\.net/pyodide/(v[^/]+)/full/", worker))
        self.assertEqual(len(versions), 1, versions)
        self.assertRegex(versions.pop(), r"^v\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
