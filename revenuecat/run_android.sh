#!/usr/bin/env bash
set -euo pipefail

if [[ "${RC_CI_ENABLED:-false}" != "true" ]]; then
  echo "RevenueCat CI is disabled for this app/platform; skipping."
  exit 0
fi

: "${REVENUECAT_TEST_STORE_API_KEY:?missing RevenueCat Test Store key}"
: "${RC_CI_ENTITLEMENT:?missing RevenueCat entitlement}"
: "${RC_CI_USER_ID:?missing RevenueCat CI user id}"

if [[ "$REVENUECAT_TEST_STORE_API_KEY" != test_* ]]; then
  echo "::error::Refusing to run RevenueCat CI with a non-Test-Store key."
  exit 1
fi

if ! command -v maestro >/dev/null 2>&1; then
  curl -Ls "https://get.maestro.mobile.dev" | bash
  export PATH="$HOME/.maestro/bin:$PATH"
fi

flutter build apk \
  --debug \
  -t lib/revenuecat_ci_main.dart \
  --dart-define="REVENUECAT_TEST_STORE_API_KEY=$REVENUECAT_TEST_STORE_API_KEY" \
  --dart-define="REVENUECAT_CI_ENTITLEMENT=$RC_CI_ENTITLEMENT" \
  --dart-define="REVENUECAT_CI_USER_ID=$RC_CI_USER_ID"

APK_PATH="$(find build/app/outputs/flutter-apk -maxdepth 1 -name '*debug*.apk' -print -quit)"
if [[ -z "$APK_PATH" ]]; then
  echo "::error::RevenueCat CI debug APK was not produced."
  exit 1
fi

AAPT="$(find "$ANDROID_SDK_ROOT/build-tools" -type f -name aapt | sort -V | tail -n 1)"
if [[ -z "$AAPT" ]]; then
  echo "::error::aapt was not found in the Android SDK."
  exit 1
fi
APP_ID="$($AAPT dump badging "$APK_PATH" | sed -n "s/^package: name='\([^']*\)'.*/\1/p" | head -n 1)"
if [[ -z "$APP_ID" ]]; then
  echo "::error::Could not determine application id from $APK_PATH."
  exit 1
fi

echo "RevenueCat CI Android app id: $APP_ID"
adb install -r "$APK_PATH"

FLOW="$RUNNER_TEMP/revenuecat-android.yaml"
cat > "$FLOW" <<EOF
appId: $APP_ID
---
- launchApp:
    clearState: true
- extendedWaitUntil:
    visible: "REVENUECAT_CI_READY"
    timeout: 60000
- tapOn: "Start RevenueCat CI purchase"
- tapOn: "Test valid Purchase"
- extendedWaitUntil:
    visible: "PURCHASE_REMOTE_ACTIVE"
    timeout: 60000
- stopApp
- launchApp
- extendedWaitUntil:
    visible: "PERSISTED_AFTER_RESTART"
    timeout: 60000
- tapOn: "Restore and verify purchase"
- extendedWaitUntil:
    visible: "ALL_REVENUECAT_CHECKS_PASSED"
    timeout: 60000
EOF

maestro test "$FLOW"
rm -f lib/revenuecat_ci_main.dart "$FLOW"
echo "RevenueCat Android purchase persistence checks passed."
