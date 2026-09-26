import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / ".github" / "scripts" / "verify_r8_min_scores.py"
METADATA = "BUNDLE-METADATA/com.android.tools/r8.json"


def write_aab(path: Path, *, optimization=25.0, obfuscation=25.0, shrinking=25.0,
              omit=None, enabled=True, full_mode=True):
    omit = set(omit or ())
    data = {
        "build": {
            "isOptimizationsEnabled": enabled,
            "isObfuscationEnabled": enabled,
            "isShrinkingEnabled": enabled,
            "isProGuardCompatibilityModeEnabled": not full_mode,
        }
    }
    scores = {
        "Optimization": optimization,
        "Obfuscation": obfuscation,
        "Shrinking": shrinking,
    }
    keys = {
        "Optimization": "noOptimizationPercentage",
        "Obfuscation": "noObfuscationPercentage",
        "Shrinking": "noShrinkingPercentage",
    }
    for name, score in scores.items():
        if name not in omit:
            data["build"][keys[name]] = 100.0 - score

    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr(METADATA, json.dumps(data))
        bundle.writestr("base/dex/classes.dex", b"dex\n035\x00")


def run_gate(aab: Path):
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(aab)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class VerifyR8MinScoresTest(unittest.TestCase):
    def test_exactly_25_percent_for_all_three_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            aab = Path(tmp) / "app.aab"
            write_aab(aab)
            result = run_gate(aab)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_any_single_metric_below_25_percent_fails(self):
        for metric in ("optimization", "obfuscation", "shrinking"):
            with self.subTest(metric=metric), tempfile.TemporaryDirectory() as tmp:
                aab = Path(tmp) / "app.aab"
                values = dict(optimization=25.0, obfuscation=25.0, shrinking=25.0)
                values[metric] = 24.99
                write_aab(aab, **values)
                result = run_gate(aab)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("below 25.00%", result.stderr)

    def test_missing_score_is_a_hard_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            aab = Path(tmp) / "app.aab"
            write_aab(aab, omit={"Obfuscation"})
            result = run_gate(aab)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Obfuscation score is unavailable", result.stderr)

    def test_disabled_r8_dimension_is_a_hard_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            aab = Path(tmp) / "app.aab"
            write_aab(aab, enabled=False)
            result = run_gate(aab)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Optimization is not enabled", result.stderr)

    def test_missing_r8_metadata_is_a_hard_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            aab = Path(tmp) / "app.aab"
            with zipfile.ZipFile(aab, "w") as bundle:
                bundle.writestr("base/dex/classes.dex", b"dex\n035\x00")
            result = run_gate(aab)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("r8.json", result.stderr)


if __name__ == "__main__":
    unittest.main()
