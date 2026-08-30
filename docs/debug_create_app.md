# Debug Create App

`Debug Create App` builds a debug APK for a selected GitHub repository and publishes it as a prerelease on that repository's GitHub Releases page.

Workflow: `.github/workflows/debug_create_app.yml`

## Inputs

- `app` — repository name, for example `3dimageapp`
- `owner` — repository owner, defaults to `Persie0`
- `branch` — optional branch, tag, or SHA; empty uses the target repository default branch

## Supported Android project layouts

The workflow detects and builds:

- Flutter projects (`pubspec.yaml`)
- Android projects with an `android/gradlew` wrapper
- Android projects with a root `gradlew` wrapper
- Android projects without a committed wrapper but with Gradle settings under `android/`
- Android projects without a committed wrapper but with Gradle settings at repository root

Native/CMake projects automatically install an NDK. The default native fallback is NDK `28.2.13676358` when a project does not declare an NDK version.

## Release credentials

For private target repositories and cross-repository Release publishing, configure one of these Actions secrets in `firebase_tester_builder`:

1. `GH_RELEASE_TOKEN` — preferred. A fine-grained token scoped only to the repositories that may be built, with **Contents: Read and write**.
2. `GH_TOKEN` — fallback. It must have the same Contents write permission if Releases should be published.

A token with repository read access only can checkout and build an app, but GitHub will return HTTP 403 when the workflow attempts to create the target Release.

## Output

For target commit `<sha>` the workflow:

1. builds the debug APK;
2. uploads an Actions artifact named `<app>-debug-<short-sha>` for 14 days;
3. creates or updates target-repository prerelease `debug-<short-sha>`;
4. uploads `<app>-debug.apk` to that Release.

The APK is a debug/test build and is intentionally marked as a prerelease.

## Safer per-repository alternative

`debug_build_release_reusable.yml` is a reusable version of the same pipeline. A target repository can call it with its own `GITHUB_TOKEN` and `permissions: contents: write`, avoiding any cross-repository write token. This requires GitHub-hosted Actions runners to be available for the target repository.
