import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "detect_android_project.py"
spec = importlib.util.spec_from_file_location("detect_android_project", SCRIPT)
detector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(detector)


def create_project(base: Path, relative: str, *, kotlin: bool = True, wrapper: bool = True):
    root = base / relative
    (root / "app" / "src" / "main" / "java").mkdir(parents=True)
    (root / "settings.gradle.kts").write_text('include(":app")')
    (root / "app" / "build.gradle.kts").write_text('plugins { id("com.android.application") }')
    if kotlin:
        (root / "app" / "src" / "main" / "java" / "MainActivity.kt").write_text(
            "class MainActivity"
        )
    if wrapper:
        (root / "gradlew").write_text("#!/bin/sh\n")
    return root


class AndroidProjectDetectorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_root_project(self):
        create_project(self.root, ".")
        result = detector.detect(self.root, mode="native-kotlin")
        self.assertEqual(result["root"], ".")
        self.assertEqual(result["type"], "gradle-wrapper")
        self.assertEqual(result["build_file"], "app/build.gradle.kts")

    def test_android_project_without_wrapper(self):
        create_project(self.root, "android", wrapper=False)
        result = detector.detect(self.root, mode="native-kotlin")
        self.assertEqual(result["root"], "android")
        self.assertEqual(result["has_wrapper"], "false")
        self.assertEqual(result["type"], "gradle-system")

    def test_skip_silence_player_layout(self):
        create_project(self.root, "kotlin-android")
        (self.root / "swift-ios").mkdir()
        result = detector.detect(self.root, mode="native-kotlin")
        self.assertEqual(result["root"], "kotlin-android")
        self.assertEqual(result["build_file"], "kotlin-android/app/build.gradle.kts")
        self.assertEqual(result["has_wrapper"], "true")

    def test_nested_directory_is_supported(self):
        create_project(self.root, "apps/player/android")
        result = detector.detect(self.root, mode="native-kotlin")
        self.assertEqual(result["root"], "apps/player/android")

    def test_fails_on_ambiguous_nested_projects(self):
        create_project(self.root, "kotlin-android")
        create_project(self.root, "samples/demo")
        with self.assertRaisesRegex(ValueError, "Multiple Android projects"):
            detector.detect(self.root, mode="native-kotlin")
        result = detector.detect(self.root, "kotlin-android", mode="native-kotlin")
        self.assertEqual(result["root"], "kotlin-android")

    def test_prefers_existing_root_layout(self):
        create_project(self.root, ".")
        create_project(self.root, "samples/demo")
        self.assertEqual(detector.detect(self.root, mode="native-kotlin")["root"], ".")

    def test_rejects_flutter_in_kotlin_mode(self):
        (self.root / "pubspec.yaml").write_text("name: demo")
        create_project(self.root, "android")
        self.assertEqual(detector.detect(self.root)["type"], "flutter")
        with self.assertRaisesRegex(ValueError, "Flutter"):
            detector.detect(self.root, mode="native-kotlin")

    def test_filters_non_kotlin_gradle_projects(self):
        create_project(self.root, "kotlin-android", kotlin=False)
        with self.assertRaisesRegex(ValueError, "No Android Gradle app"):
            detector.detect(self.root, mode="native-kotlin")

    def test_rejects_path_outside_checkout(self):
        create_project(self.root, "kotlin-android")
        with self.assertRaisesRegex(ValueError, "within the checkout"):
            detector.detect(self.root, "../", mode="native-kotlin")

    def test_does_not_scan_embedded_checkout(self):
        create_project(self.root, ".firebase_builder_detector/sample")
        create_project(self.root, "kotlin-android")
        self.assertEqual(
            detector.detect(self.root, mode="native-kotlin")["root"], "kotlin-android"
        )


if __name__ == "__main__":
    unittest.main()
