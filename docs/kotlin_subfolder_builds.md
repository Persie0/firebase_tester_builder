# Android projects in subfolders (Kotlin)

Only three workflows are installed in `.github/workflows`:

- `app_store_auto.yml` — iOS release automation
- `play_auto.yml` — Flutter release automation
- `play_kotlin_auto.yml` — Kotlin debug builds and Android/Google Play releases

The standalone validation/checking workflows and previous cross-repository debug-release workflows have been removed. Native Kotlin debug builds are now available through **Kotlin Play Store Automation** with **build_variant: debug**.

## Supported project layouts

Kotlin builds discover the Gradle root using a settings file (`settings.gradle` or `settings.gradle.kts`) and `app/build.gradle[.kts]`, plus Kotlin sources under `app/src`.

Examples:

- Repository root: `settings.gradle.kts`, `app/build.gradle.kts`
- `android/settings.gradle.kts`, `android/app/build.gradle.kts`
- `kotlin-android/settings.gradle.kts`, `kotlin-android/app/build.gradle.kts` — **SkipSilencePlayer**
- `apps/player/android/settings.gradle.kts` for monorepositories

Root and `android/` keep precedence to preserve existing behavior. If multiple nonstandard Gradle apps are found, pass `project_dir` explicitly to avoid building the wrong one. A committed Gradle wrapper is used when present; otherwise the workflow installs standalone Gradle.

## Building SkipSilencePlayer

In **Actions → Kotlin Play Store Automation → Run workflow**, choose:

| Input | Debug APK | Build-only release AAB |
| --- | --- | --- |
| `app` | `SkipSilencePlayer` | `SkipSilencePlayer` |
| `build_variant` | `debug` | `release` |
| `project_dir` | blank (auto) or `kotlin-android` | blank (auto) or `kotlin-android` |
| `publish_to_play` | Ignored for debug | **false** until Play signing and publishing are configured |
| `build_apk` | Ignored for debug | Only used when publishing a signed release |

Debug builds invoke `:app:testDebugUnitTest :app:assembleDebug` and upload `app-debug.apk` as an Actions artifact.

Release builds invoke `:app:bundleRelease` and upload `app-release.aab`. An artifact-only release is **not automatically signed**; it is a build artifact, not a Play-ready deliverable unless the app itself configures release signing. Set `publish_to_play: true` only for projects with valid Play registration, upload keystore, release configuration, and service account permissions.

For existing Play-managed Kotlin apps, leaving `build_variant: release` and `publish_to_play: true` preserves the EULA refresh, GlitchTip, Play versioning, R8 checks, signing, AAB submission, and optional Firebase Test Lab workflow.

The build action checks out repositories via `PRIVATE_REPO_TOKEN || GH_TOKEN || GH_RELEASE_TOKEN` as before. It does not run separate CI validation workflows.
