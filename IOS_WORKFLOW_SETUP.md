# iOS App Store workflow setup

The `App Store Automation` workflow handles all selected repositories through the same standard Flutter build path: checkout, `flutter pub get`, CocoaPods, Flutter iOS release build, Xcode archive, signed IPA export, artifact upload, and optional TestFlight upload.

## Repository secrets

Add these secrets to `Persie0/firebase_tester_builder` under **Settings → Secrets and variables → Actions**:

| Secret | Value |
| --- | --- |
| `GH_TOKEN` | Existing token with read access to every selected app repository and `Persie0/Persie0.github.io`. |
| `APPLE_TEAM_ID` | The 10-character Apple Developer team ID. |
| `APP_STORE_CONNECT_KEY_ID` | Key ID of an App Store Connect API key. |
| `APP_STORE_CONNECT_ISSUER_ID` | Issuer ID shown for the App Store Connect API key. |
| `APP_STORE_CONNECT_PRIVATE_KEY_BASE64` | Base64-encoded contents of the downloaded `AuthKey_<KEY_ID>.p8` file. |
| `IOS_DISTRIBUTION_CERTIFICATE_BASE64` | Base64-encoded `.p12` containing an Apple Distribution certificate and its private key. |
| `IOS_DISTRIBUTION_CERTIFICATE_PASSWORD` | Password used when exporting the `.p12`. |
| `SENTRY_AUTH_TOKEN` | Optional; used only by apps containing `sentry_dart_plugin`. |

The API key needs permission to upload builds to App Store Connect and access to Certificates, Identifiers & Profiles so Xcode can obtain provisioning profiles automatically. All selected apps are expected to belong to `APPLE_TEAM_ID`.

## Encode the files

On macOS:

```bash
base64 -i AuthKey_KEYID.p8 | tr -d '\n'
base64 -i AppleDistribution.p12 | tr -d '\n'
```

On Linux:

```bash
base64 -w 0 AuthKey_KEYID.p8
base64 -w 0 AppleDistribution.p12
```

Paste each output into its corresponding GitHub Actions secret. Never commit the `.p8`, `.p12`, or decoded provisioning/signing material.

## Run it

Open **Actions → App Store Automation → Run workflow**, select the Flutter app, and optionally provide:

- a non-default app repository branch;
- a scheme other than `Runner`;
- a custom App Store build number;
- whether the generated IPA should also be uploaded to TestFlight.

When no build number is supplied, the workflow uses a UTC timestamp such as `202608031915`, which prevents duplicate build numbers across runs.

## Signing behavior

The workflow imports one Apple Distribution certificate into a temporary keychain. Xcode uses automatic signing plus the App Store Connect API key to download or create the required App Store provisioning profile for the selected Flutter app and any extensions. The temporary keychain and API key files are removed at the end of the job.

All apps use the same workflow and build commands; selecting a different app only changes which repository is checked out.
