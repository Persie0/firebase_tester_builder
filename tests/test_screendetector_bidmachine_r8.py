"""Tests for the screendetector-only BidMachine GMS R8 consumer-rule override."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/play_auto.yml"
NAME = "Optimize redundant BidMachine GMS consumer keep rule"


def extract_step_script(workflow):
    lines = workflow.splitlines()
    start = lines.index("      - name: " + NAME)
    run = next(i for i in range(start + 1, len(lines)) if lines[i] == "        run: |")
    end = next(
        (i for i in range(run + 1, len(lines)) if lines[i].startswith("      - ")),
        len(lines),
    )
    return "\n".join(
        line[10:] if line.startswith("          ") else line
        for line in lines[run + 1 : end]
    ) + "\n"


class ScreendetectorBidMachineR8Tests(unittest.TestCase):
    def test_only_screendetector_executes_override(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        i = workflow.index("      - name: " + NAME)
        next_step = workflow.index("      - name: Flutter analyze", i)
        self.assertIn("if: inputs.app == 'screendetector'", workflow[i:next_step])
        self.assertLess(next_step, workflow.index("      - name: Build app bundle"))

    def test_override_preserves_vungle_and_only_targets_named_gms_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root / "git" / "Appodeal-Flutter-Plugin-test" / "android"
            cache.mkdir(parents=True)
            path = cache / "appodeal-r8-optimizer.gradle"
            path.write_text(
                "return input.name.toLowerCase(java.util.Locale.ROOT).contains('vungle')\n"
                "boolean containsVungleRules = original.contains('com.vungle.ads')\n"
                "            if (containsVungleRules &&\n",
                encoding="utf-8",
            )
            script = extract_step_script(WORKFLOW.read_text(encoding="utf-8"))
            result = subprocess.run(
                ["bash", "-c", script], cwd=root,
                env={**os.environ, "PUB_CACHE": str(root)},
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            out = path.read_text(encoding="utf-8")
            self.assertIn("|| input.name == 'ads-3.7.1.aar'", out)
            self.assertIn("containsBidMachineRules", out)
            self.assertIn("-keep class com.google.android.gms.common.** { *; }", out)
            self.assertIn("if (containsVungleRules &&", out)
            self.assertEqual(out.count("if (containsBidMachineRules &&"), 1)
            self.assertIn("return\n", out)

    def test_unknown_fork_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root / "git" / "Appodeal-Flutter-Plugin-test" / "android"
            cache.mkdir(parents=True)
            (cache / "appodeal-r8-optimizer.gradle").write_text(
                "not the expected optimizer", encoding="utf-8",
            )
            script = extract_step_script(WORKFLOW.read_text(encoding="utf-8"))
            result = subprocess.run(
                ["bash", "-c", script], cwd=root,
                env={**os.environ, "PUB_CACHE": str(root)},
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Appodeal fork changed", result.stderr)


if __name__ == "__main__":
    unittest.main()
