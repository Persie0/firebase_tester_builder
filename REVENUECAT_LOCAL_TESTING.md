# Local RevenueCat purchase persistence test (macOS)

RevenueCat purchase testing is **not** part of the Android or iOS GitHub Actions release workflows.

Use `revenuecat/test_local.sh` on your Mac when you want to verify that a purchase activates the expected entitlement and stays active after a fresh RevenueCat fetch, app restart, and `restorePurchases()`.

## Requirements

- macOS
- Flutter installed and on `PATH`
- RevenueCat Test Store configured for the RevenueCat project
- `purchases_flutter >= 9.8.0`
- At least one Test Store product attached to an offering and mapped to the app's Pro entitlement
- For iOS: Xcode with an iPhone Simulator runtime
- For Android: Android SDK and either a connected device or an Android Virtual Device

The script installs Maestro for your macOS user automatically if `maestro` is not already available.

## Run it

From a clone of `firebase_tester_builder`:

```bash
bash revenuecat/test_local.sh --app-path ../noise_remover --platform ios
```

or:

```bash
bash revenuecat/test_local.sh --app-path ../noise_remover --platform android
```

If you omit the path or platform, the script prompts you:

```bash
bash revenuecat/test_local.sh
```

The script securely asks for the RevenueCat Test Store public SDK key (`test_...`) unless you pass one through `REVENUECAT_TEST_STORE_API_KEY` or `--test-key`.

Example without putting the key into shell history:

```bash
bash revenuecat/test_local.sh --app-path ../image_enhancer --platform ios
```

Then paste the `test_...` key at the hidden prompt.

## What it verifies

For each run the script creates a unique RevenueCat App User ID and performs:

1. Fresh app state.
2. Load RevenueCat offerings.
3. Start a Test Store purchase.
4. Automatically select **Test valid Purchase**.
5. Verify the configured entitlement is active in the purchase result.
6. Invalidate the RevenueCat `CustomerInfo` cache.
7. Fetch `CustomerInfo` again and verify the entitlement is still active.
8. Stop and relaunch the app with the same RevenueCat App User ID.
9. Verify the entitlement is still active after restart.
10. Call `restorePurchases()`.
11. Invalidate/fetch `CustomerInfo` once more and require the entitlement to remain active.

Any failed step exits non-zero and Maestro shows the failing UI step.

## App configuration

Known entitlement IDs and supported platforms are stored in `revenuecat/apps.json`.

Current configuration:

| App | Android | iOS | Entitlement |
| --- | --- | --- | --- |
| `noise_remover` | yes | yes | `noisecancel Pro` |
| `vitamindtracker` | yes | yes | `vitamind Pro` |
| `image_enhancer` | yes | yes | `imageEnhancer Pro` |
| `face_scanner` | yes | no | `facemesh Pro` |
| `resistor_scanner` | yes | no | `resistor scanner Pro` |

For an app not in `apps.json`, the script asks for the entitlement ID. You can also explicitly provide it:

```bash
bash revenuecat/test_local.sh \
  --app-path ../some_flutter_app \
  --platform ios \
  --entitlement 'my Pro entitlement'
```

A platform marked disabled in `apps.json` is blocked by default because testing a temporary RevenueCat harness could otherwise give false confidence about a production integration that is not actually configured. Use `--force-platform` only when you intentionally want to bypass that guard.

## Safety

The script refuses `goog_...` and `appl_...` production SDK keys and accepts only RevenueCat Test Store keys beginning with `test_`.

It temporarily copies `revenuecat/local_main.dart` to the selected app as `lib/revenuecat_local_main.dart`. A shell trap removes that file when the script exits, including on failure or Ctrl-C. Your app's production `main.dart`, purchase service, release workflow, AAB, and IPA configuration are not modified.

This test verifies the RevenueCat purchase/entitlement persistence path using the selected app's Flutter/RevenueCat SDK. It does not replace app-specific unit/widget tests for whether every Pro UI feature correctly reacts to the entitlement.