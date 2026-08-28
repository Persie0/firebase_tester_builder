#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/apps.json"
HARNESS_FILE="$SCRIPT_DIR/local_main.dart"

APP_PATH=""
PLATFORM=""
ENTITLEMENT_OVERRIDE=""
TEST_KEY="${REVENUECAT_TEST_STORE_API_KEY:-}"
FORCE_PLATFORM=false

usage() {
  cat <<'EOF'
Usage:
  ./revenuecat/test_local.sh --app-path /path/to/flutter_app --platform ios
  ./revenuecat/test_local.sh --app-path /path/to/flutter_app --platform android

Options:
  --app-path PATH          Flutter application to test. Prompts if omitted.
  --platform ios|android   Platform to test. Prompts if omitted.
  --entitlement ID         Override/inject the RevenueCat entitlement ID.
  --test-key test_...      RevenueCat Test Store public SDK key. If omitted,
                           the script securely prompts for it.
  --force-platform         Ignore apps.json platform-disable flag.
  -h, --help               Show this help.

The script never modifies your production purchase implementation. It copies a
small temporary Flutter entry point into the selected app, runs a RevenueCat
Test Store purchase, checks a fresh CustomerInfo fetch, restarts the app, then
checks restorePurchases(). The temporary Dart file is removed on exit.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --app-path)
      APP_PATH="${2:-}"
      shift 2
      ;;
    --platform)
      PLATFORM="${2:-}"
      shift 2
      ;;
    --entitlement)
      ENTITLEMENT_OVERRIDE="${2:-}"
      shift 2
      ;;
    --test-key)
      TEST_KEY="${2:-}"
      shift 2
      ;;
    --force-platform)
      FORCE_PLATFORM=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This local runner is intended for macOS." >&2
  exit 1
fi

for command in flutter python3 curl; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Missing required command: $command" >&2
    exit 1
  fi
done

if [[ -z "$APP_PATH" ]]; then
  read -r -p "Flutter app path: " APP_PATH
fi
if [[ -z "$APP_PATH" || ! -f "$APP_PATH/pubspec.yaml" ]]; then
  echo "Not a Flutter app: $APP_PATH (pubspec.yaml not found)" >&2
  exit 1
fi
APP_PATH="$(cd "$APP_PATH" && pwd)"

if [[ -z "$PLATFORM" ]]; then
  echo "Choose platform:"
  echo "  1) iOS Simulator"
  echo "  2) Android device/emulator"
  read -r -p "Selection [1/2]: " selection
  case "$selection" in
    1) PLATFORM="ios" ;;
    2) PLATFORM="android" ;;
    *) echo "Invalid selection." >&2; exit 2 ;;
  esac
fi
if [[ "$PLATFORM" != "ios" && "$PLATFORM" != "android" ]]; then
  echo "--platform must be ios or android" >&2
  exit 2
fi
if [[ ! -d "$APP_PATH/$PLATFORM" ]]; then
  echo "$APP_PATH does not contain a $PLATFORM platform directory." >&2
  exit 1
fi

APP_NAME="$(awk -F: '/^name:[[:space:]]*/ {gsub(/[[:space:]"'\'']/, "", $2); print $2; exit}' "$APP_PATH/pubspec.yaml")"
if [[ -z "$APP_NAME" ]]; then
  APP_NAME="$(basename "$APP_PATH")"
fi

CONFIG_RESULT="$(python3 - "$CONFIG_FILE" "$APP_NAME" "$PLATFORM" <<'PY'
import json
import sys

path, app, platform = sys.argv[1:]
with open(path, encoding='utf-8') as handle:
    config = json.load(handle)
entry = config.get(app)
if entry is None:
    print('\t\t')
else:
    entitlement = str(entry.get('entitlement', ''))
    supported = 'true' if bool(entry.get(platform)) else 'false'
    note = str(entry.get('note', '')).replace('\t', ' ').replace('\n', ' ')
    print(f'{entitlement}\t{supported}\t{note}')
PY
)"
IFS=$'\t' read -r CONFIG_ENTITLEMENT CONFIG_SUPPORTED CONFIG_NOTE <<< "$CONFIG_RESULT"

ENTITLEMENT="$ENTITLEMENT_OVERRIDE"
if [[ -z "$ENTITLEMENT" ]]; then
  ENTITLEMENT="$CONFIG_ENTITLEMENT"
fi
if [[ -z "$ENTITLEMENT" ]]; then
  read -r -p "RevenueCat entitlement ID for $APP_NAME: " ENTITLEMENT
fi
if [[ -z "$ENTITLEMENT" ]]; then
  echo "RevenueCat entitlement ID is required." >&2
  exit 1
fi

if [[ "$CONFIG_SUPPORTED" == "false" && "$FORCE_PLATFORM" != "true" ]]; then
  echo "$APP_NAME/$PLATFORM is disabled in revenuecat/apps.json." >&2
  if [[ -n "$CONFIG_NOTE" ]]; then
    echo "Reason: $CONFIG_NOTE" >&2
  fi
  echo "Use --force-platform only if you intentionally want to test it anyway." >&2
  exit 1
fi

python3 - "$APP_PATH/pubspec.yaml" <<'PY'
import re
import sys

text = open(sys.argv[1], encoding='utf-8').read()
match = re.search(r'(?m)^\s*purchases_flutter\s*:\s*[^\n]*?([0-9]+)\.([0-9]+)\.([0-9]+)', text)
if not match:
    raise SystemExit('purchases_flutter was not found in pubspec.yaml')
version = tuple(map(int, match.groups()))
if version < (9, 8, 0):
    raise SystemExit(
        f'purchases_flutter {".".join(map(str, version))} is too old; RevenueCat Test Store requires >= 9.8.0'
    )
print('purchases_flutter=' + '.'.join(map(str, version)))
PY

if [[ -z "$TEST_KEY" ]]; then
  read -r -s -p "RevenueCat Test Store key (test_...): " TEST_KEY
  echo
fi
if [[ "$TEST_KEY" != test_* ]]; then
  echo "Refusing to use a non-Test-Store key. Expected a key beginning with test_." >&2
  exit 1
fi

if ! command -v maestro >/dev/null 2>&1; then
  echo "Maestro not found; installing it for the current macOS user..."
  curl -Ls "https://get.maestro.mobile.dev" | bash
  export PATH="$HOME/.maestro/bin:$PATH"
fi
if ! command -v maestro >/dev/null 2>&1; then
  echo "Maestro installation did not put maestro on PATH." >&2
  echo "Expected location: $HOME/.maestro/bin/maestro" >&2
  exit 1
fi

TEMP_ENTRY="$APP_PATH/lib/revenuecat_local_main.dart"
FLOW=""
if [[ -e "$TEMP_ENTRY" ]]; then
  echo "Refusing to overwrite existing $TEMP_ENTRY" >&2
  exit 1
fi

cleanup() {
  rm -f "$TEMP_ENTRY"
  if [[ -n "$FLOW" ]]; then
    rm -f "$FLOW"
  fi
}
trap cleanup EXIT INT TERM

cp "$HARNESS_FILE" "$TEMP_ENTRY"

TEST_USER_ID="local-${APP_NAME}-${PLATFORM}-$(date +%s)-$$"
echo "Testing app:         $APP_NAME"
echo "Platform:            $PLATFORM"
echo "Entitlement:         $ENTITLEMENT"
echo "RevenueCat user ID:  $TEST_USER_ID"
echo

pushd "$APP_PATH" >/dev/null
flutter pub get

DART_DEFINES=(
  "--dart-define=REVENUECAT_TEST_STORE_API_KEY=$TEST_KEY"
  "--dart-define=REVENUECAT_TEST_ENTITLEMENT=$ENTITLEMENT"
  "--dart-define=REVENUECAT_TEST_USER_ID=$TEST_USER_ID"
)

new_flow_file() {
  local base
  base="$(mktemp -t revenuecat-local)"
  rm -f "$base"
  FLOW="${base}.yaml"
}

run_ios() {
  if ! command -v xcrun >/dev/null 2>&1; then
    echo "xcrun is missing. Install/select Xcode first." >&2
    exit 1
  fi

  local simulator_udid app_path app_id
  simulator_udid="$(python3 - <<'PY'
import json
import subprocess

data = json.loads(subprocess.check_output(['xcrun', 'simctl', 'list', 'devices', 'available', '-j']))
for devices in data.get('devices', {}).values():
    for device in devices:
        if device.get('isAvailable') and device.get('name', '').startswith('iPhone'):
            print(device['udid'])
            raise SystemExit
raise SystemExit('No available iPhone simulator found. Install an iOS Simulator runtime in Xcode.')
PY
)"

  xcrun simctl boot "$simulator_udid" >/dev/null 2>&1 || true
  open -a Simulator >/dev/null 2>&1 || true
  xcrun simctl bootstatus "$simulator_udid" -b

  flutter build ios \
    --simulator \
    --debug \
    -t lib/revenuecat_local_main.dart \
    "${DART_DEFINES[@]}"

  app_path="$(find build/ios/iphonesimulator -maxdepth 1 -name '*.app' -print -quit)"
  if [[ -z "$app_path" ]]; then
    echo "iOS simulator app was not produced." >&2
    exit 1
  fi

  app_id="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$app_path/Info.plist")"
  if [[ -z "$app_id" ]]; then
    echo "Could not determine the iOS bundle identifier." >&2
    exit 1
  fi

  xcrun simctl install "$simulator_udid" "$app_path"
  new_flow_file
  cat > "$FLOW" <<EOF
appId: $app_id
---
- launchApp:
    clearState: true
- extendedWaitUntil:
    visible: "REVENUECAT_LOCAL_READY"
    timeout: 60000
- tapOn: "Start test purchase"
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
}

run_android() {
  local sdk_root adb emulator device avd apk_path aapt app_id
  sdk_root="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$HOME/Library/Android/sdk}}"
  adb="$sdk_root/platform-tools/adb"
  emulator="$sdk_root/emulator/emulator"

  if [[ ! -x "$adb" ]]; then
    echo "Android adb not found at $adb" >&2
    echo "Set ANDROID_SDK_ROOT if your SDK is elsewhere." >&2
    exit 1
  fi

  device="$($adb devices | awk 'NR > 1 && $2 == "device" {print $1; exit}')"
  if [[ -z "$device" ]]; then
    if [[ ! -x "$emulator" ]]; then
      echo "No Android device is connected and emulator was not found at $emulator" >&2
      exit 1
    fi
    avd="$($emulator -list-avds | head -n 1)"
    if [[ -z "$avd" ]]; then
      echo "No Android device is connected and no Android Virtual Device exists." >&2
      echo "Create an AVD in Android Studio Device Manager, then rerun this script." >&2
      exit 1
    fi

    echo "Starting Android emulator: $avd"
    "$emulator" -avd "$avd" -no-snapshot-save >/tmp/revenuecat-local-emulator.log 2>&1 &
    "$adb" wait-for-device
    for _ in {1..120}; do
      if [[ "$($adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == "1" ]]; then
        break
      fi
      sleep 1
    done
    device="$($adb devices | awk 'NR > 1 && $2 == "device" {print $1; exit}')"
  fi

  if [[ -z "$device" ]]; then
    echo "Android device/emulator failed to become ready." >&2
    exit 1
  fi
  echo "Using Android device: $device"

  flutter build apk \
    --debug \
    -t lib/revenuecat_local_main.dart \
    "${DART_DEFINES[@]}"

  apk_path="$(find build/app/outputs/flutter-apk -maxdepth 1 -name '*debug*.apk' -print -quit)"
  if [[ -z "$apk_path" ]]; then
    echo "Debug APK was not produced." >&2
    exit 1
  fi

  aapt="$(find "$sdk_root/build-tools" -type f -name aapt 2>/dev/null | sort | tail -n 1)"
  if [[ -z "$aapt" ]]; then
    echo "aapt was not found under $sdk_root/build-tools" >&2
    exit 1
  fi
  app_id="$($aapt dump badging "$apk_path" | sed -n "s/^package: name='\([^']*\)'.*/\1/p" | head -n 1)"
  if [[ -z "$app_id" ]]; then
    echo "Could not determine Android application ID." >&2
    exit 1
  fi

  "$adb" -s "$device" install -r "$apk_path" >/dev/null
  new_flow_file
  cat > "$FLOW" <<EOF
appId: $app_id
---
- launchApp:
    clearState: true
- extendedWaitUntil:
    visible: "REVENUECAT_LOCAL_READY"
    timeout: 60000
- tapOn: "Start test purchase"
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

  maestro --device "$device" test "$FLOW"
}

case "$PLATFORM" in
  ios) run_ios ;;
  android) run_android ;;
esac

popd >/dev/null

echo
echo "RevenueCat local purchase persistence test PASSED for $APP_NAME/$PLATFORM."
