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
        self.assertIn("          - fake_gps_detector\n", self.kotlin)
        self.assertNotIn("          - fake_gps_detector\n", self.flutter)

    def test_video_upscaler_is_native_kotlin_release_target(self):
        self.assertIn("          - video_upscaler_android\n", self.kotlin)
        self.assertNotIn("          - video_upscaler_android\n", self.flutter)
        self.assertIn('"video_upscaler_android": (', self.kotlin)
        self.assertIn('"24", "video_upscaler"', self.kotlin)
        self.assertIn("at.persie0.VideoUpscaler", self.kotlin)

    def test_video_upscaler_reuses_private_audiobooster_keystore(self):
        self.assertIn("Checkout Audiobooster signing identity", self.kotlin)
        self.assertIn("repository: 'Persie0/Audiobooster'", self.kotlin)
        self.assertIn("app/key.jks", self.kotlin)
        self.assertIn("key.properties", self.kotlin)
        self.assertIn("find .audiobooster-signing/app", self.kotlin)
        self.assertIn("-name '*.jks'", self.kotlin)
        self.assertIn("-exec cp -t app/ -- {} +", self.kotlin)
        self.assertIn("cp .audiobooster-signing/key.properties key.properties", self.kotlin)
        self.assertIn("rm -rf .audiobooster-signing", self.kotlin)
        self.assertIn("keytool -list -keystore", self.kotlin)
        self.assertIn("secrets.STORE_PASSWORD", self.kotlin)
        self.assertIn("secrets.KEY_PASSWORD", self.kotlin)
        self.assertLess(
            self.kotlin.index("Install Video Upscaler upload signing files"),
            self.kotlin.index("Configure keystore"),
        )

    def test_project_directory_detection_is_shared(self):
        self.assertIn("--mode native-kotlin", self.kotlin)
        self.assertIn("detect_android_project.py", self.kotlin)
        self.assertIn("inputs.project_dir", self.kotlin)
        self.assertIn("PROJECT_ROOT", self.kotlin)

    def test_nested_player_is_available(self):
        self.assertIn("          - SkipSilencePlayer", self.kotlin)
        self.assertIn("          - release", self.kotlin)
        self.assertIn("          - debug", self.kotlin)
        self.assertIn("inputs.build_variant == 'debug'", self.kotlin)
        self.assertIn(":app:assembleDebug", self.kotlin)
        self.assertIn("inputs.publish_to_play", self.kotlin)
        self.assertIn("AAB_PATH=$AAB_PATH", self.kotlin)

    def test_kotlin_sources_are_required(self):
        detector = (REPO_ROOT / ".github" / "scripts" / "detect_android_project.py").read_text()
        self.assertIn('root / "app" / "src"', detector)
        self.assertIn('rglob("*.kt")', detector)

    def test_native_gradle_release_and_debug_are_used(self):
        self.assertIn(":app:testDebugUnitTest :app:lintRelease", self.kotlin)
        self.assertIn(":app:bundleRelease", self.kotlin)
        self.assertIn(":app:assembleDebug", self.kotlin)
        self.assertIn("Upload Kotlin debug APK", self.kotlin)
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
        self.assertIn(r"release\s*\(\s*\K[0-9]+", self.kotlin)

    def test_release_only_steps_are_guarded(self):
        for step in (
            "Resolve next Play versionCode", "Configure keystore",
            "Sentry / GlitchTip R8 mapping upload", "Upload Android release to Play Store",
        ):
            self.assertIn(
                f"- name: {step}\n        if: inputs.build_variant == 'release' && inputs.publish_to_play",
                self.kotlin,
            )

    def test_only_release_and_build_workflows_remain(self):
        workflows = sorted(path.name for path in (REPO_ROOT / ".github" / "workflows").glob("*.yml"))
        self.assertEqual(
            workflows, ["app_store_auto.yml", "play_auto.yml", "play_kotlin_auto.yml"]
        )

    def test_version_code_is_resolved_and_verified(self):
        self.assertIn("Resolve next Play versionCode", self.kotlin)
        self.assertIn("Verify built versionCode", self.kotlin)
        self.assertIn("bundletool.jar dump manifest", self.kotlin)


if __name__ == "__main__":
    unittest.main()
