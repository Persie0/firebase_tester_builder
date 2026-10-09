# Native Kotlin GlitchTip reporting and R8 symbols

The Kotlin Play Store Automation (`.github/workflows/play_kotlin_auto.yml`)
mirrors the Flutter builder's use of the **GlitchTip CLI**, but uploads
`app/build/outputs/mapping/release/mapping.txt` instead of Dart split-debug
symbols (`app.android-*.symbols`). Do not attempt to upload Dart symbol files
for Kotlin apps.

## Existing GlitchTip projects

| Release selection | GlitchTip organization | Existing project |
| --- | --- | --- |
| `root_detection_app` | `personal` | `rootdetect` |
| `fake_gps_detector` | `personal` | `fake-gps` |
| `resistor-scanner-android` | `personal` | `resistor_scanner` |
| `Audiobooster` | `personal` | `audiobooster` (app DSN project ID 20) |

All configurations point to `https://persie0.duckdns.org`. Every app has
its **own hardcoded GlitchTip DSN** in its native Kotlin Sentry initializer;
no DSN GitHub Actions secret is needed.

| App | Hardcoded DSN project ID |
| --- | --- |
| `Audiobooster` | `20` |
| `root_detection_app` | `16` |
| `fake_gps_detector` | `15` |
| `resistor-scanner-android` | `14` |

Before building, the Kotlin workflow reads the selected app's initializer,
validates the hardcoded DSN host and numeric project ID, and resolves the
corresponding `SENTRY_URL`, `SENTRY_ORG`, and `SENTRY_PROJECT` for CLI
uploads. Missing or mismatched DSNs fail early instead of silently uploading
mappings to the wrong GlitchTip project. Do not reuse another app's DSN.

## Secrets required in the public release builder

- `GLITCHTIP_AUTH_TOKEN`: the **CLI auth token**, required for symbol uploads;
  use the same secret as the Flutter workflow. Never commit or put this
  value in Gradle, Kotlin, an APK, or an AAB.
**No per-app DSN secrets are required.** All four project DSNs are already
in Kotlin source. The builder needs the auth token only for symbol uploads;
app-side DSNs are not CLI credentials.

## How mapping uploads work

Each Kotlin repository applies `io.sentry.android.gradle` with
`includeProguardMapping = true` and `autoUploadProguardMapping = false`.
The Gradle plugin packages a matching ProGuard UUID with the release, but it
does **not** attempt a Sentry SaaS upload. After `:app:bundleRelease`, the
public builder confirms that both `mapping.txt` and the metadata exist,
installs the official `glitchtip-cli`, and executes

```bash
glitchtip-cli debug-files upload app/build/outputs/mapping/release/mapping.txt
```

with `SENTRY_URL`, `SENTRY_ORG`, `SENTRY_PROJECT`, and
`SENTRY_AUTH_TOKEN` set for that app. As in the Flutter workflow,
the upload step has `continue-on-error: true`; check that step's output
before treating a Play release as symbolicated.

App-side Sentry only starts in release mode, with tracing, sessions, screenshots,
view-hierarchy attachments, and default PII off; events remove user, server,
request, tags, and device/OS/GPU/culture context, as the Flutter apps did.
The Sentry auto-init provider is disabled. Root Detection and Fake GPS start
monitoring only after their existing EULA flow, while the native Audiobooster
and Resistor Scanner initialize at app startup.

## Security

The prior Flutter `old/pubspec.yaml` files for Root Detection and Fake GPS
contained a plaintext CLI auth token. The lines have been removed from the
current checkout; **the token remains in Git history and must be rotated** in
GlitchTip. Replace the builder's `GLITCHTIP_AUTH_TOKEN` secret with the rotated
value. Never recover the old value into this documentation.
