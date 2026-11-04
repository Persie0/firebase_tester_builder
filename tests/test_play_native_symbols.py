"""Regression tests for native-symbol configuration in Android Play workflows."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = (
    (REPO / ".github/workflows/play_auto.yml", "Build app bundle"),
    (REPO / ".github/workflows/play_kotlin_auto.yml", "Build Kotlin release app bundle"),
)
CONFIGURE = "Configure Play native debug symbols"
INSPECT = "Inspect native debug symbols in Play bundle"


def step_script(workflow: str, name: str) -> str:
    lines = workflow.splitlines()
    start = lines.index("      - name: " + name)
    run = next(i for i in range(start + 1, len(lines)) if lines[i] == "        run: |")
    end = next(
        (i for i in range(run + 1, len(lines)) if lines[i].startswith("      - ")),
        len(lines),
    )
    return "\n".join(
        line[10:] if line.startswith("          ") else line
        for line in lines[run + 1 : end]
    )


def run_script(script: str, cwd: Path, **extra_env: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "-c", script],
        cwd=cwd,
        env={**os.environ, **extra_env},
        text=True,
        capture_output=True,
        check=False,
    )


class PlayNativeSymbolsTests(unittest.TestCase):
    def test_steps_are_wired_before_release_upload(self):
        for workflow_path, build_name in WORKFLOWS:
            with self.subTest(workflow=workflow_path.name):
                text = workflow_path.read_text(encoding="utf-8")
                self.assertLess(text.index("name: " + CONFIGURE), text.index("name: " + build_name))
                self.assertLess(text.index("name: " + INSPECT), text.index("r0adkll/upload-google-play"))
                self.assertLess(text.index("name: " + build_name), text.index("name: " + INSPECT))

    def test_groovy_and_kotlin_are_configured_idempotently(self):
        for workflow_path, _ in WORKFLOWS:
            script = step_script(workflow_path.read_text(encoding="utf-8"), CONFIGURE)
            for suffix in (".gradle", ".gradle.kts"):
                with self.subTest(workflow=workflow_path.name, suffix=suffix):
                    with tempfile.TemporaryDirectory() as temp:
                        root = Path(temp)
                        path = root / "android/app" / ("build" + suffix)
                        path.parent.mkdir(parents=True)
                        path.write_text("android { }\n", encoding="utf-8")
                        env = {"BUILD_FILE": str(path)} if "kotlin" in workflow_path.name else {}
                        for _ in range(2):
                            result = run_script(script, root, **env)
                            self.assertEqual(result.returncode, 0, result.stderr)
                        modified = path.read_text(encoding="utf-8")
                        self.assertEqual(modified.count("debugSymbolLevel"), 1)
                        self.assertIn("SYMBOL_TABLE", modified)
                        if suffix == ".gradle.kts":
                            self.assertIn('getByName("release")', modified)
                        else:
                            self.assertIn("getByName('release')", modified)

    def test_preserves_existing_full_symbols(self):
        for workflow_path, _ in WORKFLOWS:
            script = step_script(workflow_path.read_text(encoding="utf-8"), CONFIGURE)
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                path = root / "android/app/build.gradle"
                path.parent.mkdir(parents=True)
                original = "android { defaultConfig { ndk { debugSymbolLevel 'FULL' } } }\n"
                path.write_text(original, encoding="utf-8")
                env = {"BUILD_FILE": str(path)} if "kotlin" in workflow_path.name else {}
                result = run_script(script, root, **env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_bundle_symbol_check_detects_symbols_and_missing_metadata(self):
        for workflow_path, _ in WORKFLOWS:
            script = step_script(workflow_path.read_text(encoding="utf-8"), INSPECT)
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                path = root / "release.aab"
                for with_symbols in (True, False):
                    with ZipFile(path, "w") as archive:
                        archive.writestr("base/lib/arm64-v8a/libexample.so", b"ELF")
                        if with_symbols:
                            archive.writestr(
                                "BUNDLE-METADATA/com.android.tools.build.debugsymbols/"
                                "arm64-v8a/libexample.so.dbg",
                                b"symbols",
                            )
                    result = run_script(script, root, AAB_PATH=str(path))
                    self.assertEqual(result.returncode, 0, result.stderr)
                    if with_symbols:
                        self.assertIn("includes 1 native debug symbol", result.stdout)
                    else:
                        self.assertIn("::warning::", result.stdout)


if __name__ == "__main__":
    unittest.main()
