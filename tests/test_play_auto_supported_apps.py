import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "play_auto.yml"


class PlayAutoSupportedAppsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_audiobooster_is_selectable(self):
        self.assertIn("          - Audiobooster\n", self.text)

    def test_selected_app_uses_generic_repository_checkout(self):
        self.assertIn("repository: 'Persie0/${{ inputs.app }}'", self.text)


if __name__ == "__main__":
    unittest.main()
