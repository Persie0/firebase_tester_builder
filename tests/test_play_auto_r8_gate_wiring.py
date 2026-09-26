import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "play_auto.yml"


class PlayAutoR8GateWiringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_global_gate_is_invoked(self):
        self.assertIn("verify_r8_min_scores.py", self.text)

    def test_global_gate_runs_before_play_upload(self):
        gate = self.text.index("verify_r8_min_scores.py")
        upload = self.text.index("r0adkll/upload-google-play")
        self.assertLess(gate, upload)

    def test_missing_app_specific_verifier_does_not_skip_global_gate(self):
        self.assertNotIn(
            "No R8 verification script found; skipping R8 metadata verification.",
            self.text,
        )
        self.assertIn("global 25% gate already passed", self.text)


if __name__ == "__main__":
    unittest.main()
