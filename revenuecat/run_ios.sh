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

# Pick an available iPhone simulator from the runner and boot it.
SIMULATOR_UDID="$(python3 - <<'PY'
import json
import subprocess

data = json.loads(subprocess.check_output(['xcrun', 'simctl', 'list', 'devices', 'available', '-j']))
for runtime in sorted(data.get('devices', {}), reverse=True):
    for device in data['devices'][runtime]:
        if device.get('isAvailable') and device.get('name', '').startswith('iPhone'):
            print(device['udid'])
            raise SystemExit
raise SystemExit('No available iPhone simulator found')
PY
)"

xcrun simctl boot "$SIMULATOR_UDID" 2>/dev/null || true
open -a Simulator || true
xcrun simctl bootstatus "$SIMULATOR_UDID" -b

flutter build ios \
  --simulator \
  --debug \
  -t lib/revenuecat_ci_main.dart \
  --dart-define="REVENUECAT_TEST_STORE_API_KEY=$REVENUECAT_TEST_STORE_API_KEY" \
  --dart-define="REVENUECAT_CI_ENTITLEMENT=$RC_CI_ENTITLEMENT" \
  --dart-define="REVENUECAT_CI_USER_ID=$RC_CI_USER_ID"

APP_PATH="$(find build/ios/iphonesimulator -maxdepth 1 -name '*.app' -print -quit)"
if [[ -z "$APP_PATH" ]]; then
  echo "::error::RevenueCat CI iOS simulator app was not produced."
  exit 1
fi

APP_ID="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$APP_PATH/Info.plist")"
if [[ -z "$APP_ID" ]]; then
  echo "::error::Could not determine iOS bundle identifier."
  exit 1
fi

echo "RevenueCat CI iOS app id: $APP_ID"
xcrun simctl install "$SIMULATOR_UDID" "$APP_PATH"

FLOW="$RUNNER_TEMP/revenuecat-ios.yaml"
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
echo "RevenueCat iOS purchase persistence checks passed."
