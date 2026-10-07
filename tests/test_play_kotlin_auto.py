import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
KOTLIN_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "play_kotlin_auto.yml"
FLUTTER_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "play_auto.yml"


class KotlinPlayAutoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kotlin = KOTLIN_WORKFLOW.read_text(encoding="utf-8")
        cls.flutter = FLUTTER_WORKFLOW.read_text(encoding="utf-8")

    def test_audiobooster_is_only_in_kotlin_release_workflow(self):
        self.assertIn("          - Audiobooster\n", self.kotlin)
        self.assertNotIn("          - Audiobooster\n", self.flutter)

    def test_fake_gps_detector_is_routed_to_kotlin(self):
        self.assertIn("          - fake_gps_detector\\n", self.kotlin)
        self.assertNotIn("          - fake_gps_detector\\n", self.flutter)

    def test_flutter_projects_are_rejected(self):
        self.assertIn("if [ -f pubspec.yaml ]; then", self.kotlin)
        self.assertIn("native Kotlin/Gradle Android apps only", self.kotlin)

    def test_root_and_android_gradle_layouts_are_detected(self):
        self.assertIn("[ -f settings.gradle.kts ]", self.kotlin)
        self.assertIn("[ -f app/build.gradle.kts ]", self.kotlin)
        self.assertIn("[ -f android/settings.gradle.kts ]", self.kotlin)
        self.assertIn("[ -f android/app/build.gradle.kts ]", self.kotlin)

    def test_kotlin_sources_are_required(self):
        self.assertIn("-name '*.kt'", self.kotlin)

    def test_native_gradle_release_is_used(self):
        self.assertIn(":app:testDebugUnitTest :app:lintRelease", self.kotlin)
        self.assertIn(":app:bundleRelease", self.kotlin)
        self.assertNotIn("flutter build appbundle", self.kotlin)
        self.assertNotIn("subosito/flutter-action", self.kotlin)

    def test_private_checkout_uses_token_fallback(self):
        self.assertIn(
            "secrets.PRIVATE_REPO_TOKEN || secrets.GH_TOKEN || secrets.GH_RELEASE_TOKEN",
            self.kotlin,
        )

    def test_release_policy_and_play_upload_are_preserved(self):
        gate = self.kotlin.index("verify_r8_min_scores.py")
        upload = self.kotlin.index("r0adkll/upload-google-play")
        self.assertLess(gate, upload)
        self.assertIn("retention-days: 3", self.kotlin)

    def test_preview_compile_sdks_are_supported(self):
        self.assertIn("sdkmanager --channel=3", self.kotlin)

    def test_version_code_is_resolved_and_verified(self):
        self.assertIn("Resolve next Play versionCode", self.kotlin)
        self.assertIn("Verify built versionCode", self.kotlin)
        self.assertIn("bundletool.jar dump manifest", self.kotlin)


if __name__ == "__main__":
    unittest.main()
