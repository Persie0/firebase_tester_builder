# Android projects in subfolders (Kotlin)

Kotlin **debug** and **release** builds use separate workflows again.

| Workflow | Purpose |
| --- | --- |
| `debug_create_app.yml` | Build a debug APK for any chosen GitHub repository; upload an Actions artifact and target-repository prerelease |
| `debug_build_release_reusable.yml` | Reusable debug APK/release publisher for caller repositories |
| `play_kotlin_auto.yml` | Kotlin **release only**: AAB artifact and optional Google Play upload |
| `play_auto.yml` | Flutter releases |
| `app_store_auto.yml` | iOS releases |

Standalone project-validation/checking workflows remain removed.

## Kotlin subfolder support

All Kotlin Gradle workflows use `.github/scripts/detect_android_project.py` to find `settings.gradle[.kts]` and `app/build.gradle[.kts]`, plus Kotlin source files in `app/src` for the Kotlin Play release workflow.

Supported layouts include:

- Gradle project at the repository root
- `android/`
- `kotlin-android/` — used by `Persie0/SkipSilencePlayer`
- `apps/player/android/` and similar deeper layouts

The project wrapper is used if available; otherwise standalone Gradle is configured. Root and `android/` take priority when more than one Gradle app exists; otherwise, pass `project_dir` to explicitly select one.

## SkipSilencePlayer

**Debug APK:** Actions → **Debug Create App**, set `app=SkipSilencePlayer`, `owner=Persie0`, and leave `project_dir` blank or set `kotlin-android`. The workflow builds `:app:testDebugUnitTest :app:assembleDebug` and publishes a debug APK artifact/prerelease.

**Release AAB:** Actions → **Kotlin Play Store Automation**, choose `app=SkipSilencePlayer`, leave `project_dir` blank or set `kotlin-android`, and set `publish_to_play=false` until signing and a Play listing are configured. The workflow builds `:app:bundleRelease` and uploads the AAB artifact. An artifact-only AAB is not necessarily Play-signed.

Existing configured Kotlin apps use the previous release signing, Play version selection, EULA refresh, R8 verification, GlitchTip mapping uploads, and optional Firebase Test Lab when `publish_to_play=true`.

No debug APK build is performed by the Kotlin Play release workflow. No separate validation/checking Actions have been restored.
