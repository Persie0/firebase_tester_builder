# RevenueCat purchase persistence CI

`play_auto.yml` and `app_store_auto.yml` expose an optional **Run RevenueCat Test Store purchase persistence checks** input.

The test is intentionally separate from the production release build. It creates a temporary Flutter entry point, uses only a RevenueCat Test Store `test_` API key, runs the purchase flow on an Android emulator or iOS simulator, removes the temporary entry point, and then continues with the normal Play/TestFlight release build.

## Required GitHub secret

Create one repository Actions secret on `Persie0/firebase_tester_builder` named:

`REVENUECAT_TEST_STORE_KEYS_JSON`

Its value is a JSON object mapping each app repository name to the RevenueCat Test Store public SDK key for that RevenueCat project:

```json
{
  "noise_remover": "test_...",
  "vitamindtracker": "test_...",
  "image_enhancer": "test_...",
  "face_scanner": "test_...",
  "resistor_scanner": "test_..."
}
```

Only `test_` keys are accepted. The preparation script rejects `appl_` and `goog_` production keys. The selected `test_` key is separately masked in GitHub Actions logs.

Each RevenueCat project must have at least one Test Store product attached to an offering, and that product must activate the entitlement configured in `revenuecat/apps.json`.

## What the automated test verifies

For every enabled app/platform combination the harness:

1. Generates a unique RevenueCat App User ID for the GitHub Actions run.
2. Starts with a fresh local application state.
3. Loads RevenueCat offerings and starts a Test Store purchase.
4. Selects **Test valid Purchase** in RevenueCat's native Test Store dialog.
5. Requires the app-specific entitlement to be active in the purchase result.
6. Invalidates RevenueCat's `CustomerInfo` cache and fetches state again.
7. Requires the entitlement to still be active after the fresh fetch.
8. Stops and relaunches the app with the same App User ID.
9. Requires the entitlement to still be active after restart.
10. Calls `restorePurchases()` and requires the entitlement to remain active after another cache invalidation/fresh fetch.

Any failed assertion stops the workflow before the production Play/TestFlight release build.

## Supported apps

| App | Android | iOS | Entitlement |
| --- | --- | --- | --- |
| `noise_remover` | yes | yes | `noisecancel Pro` |
| `vitamindtracker` | yes | yes | `vitamind Pro` |
| `image_enhancer` | yes | yes | `imageEnhancer Pro` |
| `face_scanner` | yes | no | `facemesh Pro` |
| `resistor_scanner` | yes | no | `resistor scanner Pro` |

`face_scanner` iOS is disabled because its current iOS RevenueCat production key is still a placeholder. `resistor_scanner` iOS is disabled because its current `RevenueCatService` explicitly supports Android only. Selecting the RevenueCat test option for either unsupported iOS combination produces a notice and skips the RevenueCat stage; it does not block the normal release.

Apps not present in `revenuecat/apps.json` are also skipped cleanly.

## Scope

The shared harness deliberately standardizes the CI contract rather than rewriting every app's paywall UI. This checks the app's installed RevenueCat SDK, RevenueCat project/offering configuration, exact entitlement mapping, remote persistence, restart persistence, and restore behavior without depending on translated button text or each app's changing paywall layout.

Normal app unit/widget tests and Firebase Test Lab remain responsible for app-specific UI/business logic. If an app needs its production paywall itself exercised end-to-end, add a thin app-specific Maestro adapter rather than duplicating the RevenueCat persistence logic.

Appodeal is not part of this purchase test. Appodeal controls advertising; RevenueCat controls purchase/entitlement state. They should share the app's final `isPro` decision, but the RevenueCat CI layer should not initialize or mutate advertising state.
