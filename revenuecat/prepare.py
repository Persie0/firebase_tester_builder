#!/usr/bin/env python3
"""Prepare a checked-out Flutter app for the RevenueCat Test Store CI harness."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import NoReturn

MIN_FLUTTER_SDK = (9, 8, 0)


def github_env(name: str, value: str) -> None:
    env_path = os.environ.get("GITHUB_ENV")
    if env_path:
        with open(env_path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")
    else:
        print(f"export {name}={value!r}")


def github_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def github_notice(message: str) -> None:
    print(f"::notice::{message}")


def github_warning(message: str) -> None:
    print(f"::warning::{message}")


def fail(message: str) -> NoReturn:
    print(f"::error::{message}", file=sys.stderr)
    raise SystemExit(1)


def parse_version(pubspec: str) -> tuple[int, int, int] | None:
    match = re.search(
        r"(?m)^\s*purchases_flutter\s*:\s*[^\n]*?([0-9]+)\.([0-9]+)\.([0-9]+)",
        pubspec,
    )
    if not match:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", required=True)
    parser.add_argument("--platform", required=True, choices=("android", "ios"))
    parser.add_argument("--workspace", default=".")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    workspace = Path(args.workspace).resolve()
    config = json.loads((script_dir / "apps.json").read_text(encoding="utf-8"))
    app_config = config.get(args.app)

    github_env("RC_CI_ENABLED", "false")
    github_output("enabled", "false")
    if app_config is None:
        github_notice(
            f"{args.app} has no RevenueCat CI configuration; purchase test is skipped."
        )
        return
    if not bool(app_config.get(args.platform)):
        note = app_config.get("note", "platform is not configured for RevenueCat")
        github_notice(
            f"RevenueCat CI skipped for {args.app}/{args.platform}: {note}."
        )
        return

    pubspec_path = workspace / "pubspec.yaml"
    if not pubspec_path.is_file():
        fail("pubspec.yaml is missing from the selected app")
    pubspec = pubspec_path.read_text(encoding="utf-8")
    version = parse_version(pubspec)
    if version is None:
        fail(f"{args.app} is configured for RevenueCat CI but purchases_flutter is missing")
    if version < MIN_FLUTTER_SDK:
        fail(
            f"{args.app} uses purchases_flutter {'.'.join(map(str, version))}; "
            "RevenueCat Test Store requires >= 9.8.0"
        )

    entitlement = str(app_config["entitlement"])
    dart_sources = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in (workspace / "lib").rglob("*.dart")
    )
    if entitlement not in dart_sources:
        fail(
            f"Configured entitlement {entitlement!r} was not found in {args.app} source. "
            "Update revenuecat/apps.json when the app entitlement changes."
        )
    if "restorePurchases" not in dart_sources:
        github_warning(
            f"{args.app} does not expose a restorePurchases path in Dart source. "
            "The CI harness will still verify RevenueCat restore behavior, but the app UI should add restore support."
        )
    if "getCustomerInfo" not in dart_sources:
        github_warning(
            f"{args.app} does not call getCustomerInfo directly; verify that its entitlement state is refreshed on launch."
        )

    raw_keys = os.environ.get("REVENUECAT_TEST_STORE_KEYS_JSON", "").strip()
    if not raw_keys:
        fail(
            "REVENUECAT_TEST_STORE_KEYS_JSON secret is missing. Store a JSON object mapping app name to its test_ API key."
        )
    try:
        keys = json.loads(raw_keys)
    except json.JSONDecodeError as exc:
        fail(f"REVENUECAT_TEST_STORE_KEYS_JSON is not valid JSON: {exc}")
    test_key = str(keys.get(args.app, "")).strip()
    if not test_key.startswith("test_"):
        fail(
            f"No valid test_ RevenueCat Test Store key is configured for {args.app}. "
            "Production appl_/goog_ keys are deliberately rejected."
        )

    # Mask the extracted key separately because GitHub otherwise only knows the
    # whole JSON secret value, not necessarily each individual key inside it.
    print(f"::add-mask::{test_key}")

    user_id = (
        f"ci-{args.app}-{args.platform}-"
        f"{os.environ.get('GITHUB_RUN_ID', 'local')}-"
        f"{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}"
    )

    target = workspace / "lib" / "revenuecat_ci_main.dart"
    shutil.copyfile(script_dir / "ci_main.dart", target)

    github_env("RC_CI_ENABLED", "true")
    github_env("RC_CI_ENTITLEMENT", entitlement)
    github_env("RC_CI_USER_ID", user_id)
    github_env("REVENUECAT_TEST_STORE_API_KEY", test_key)
    github_output("enabled", "true")
    github_notice(
        f"RevenueCat CI prepared for {args.app}/{args.platform}; "
        f"purchases_flutter={'.'.join(map(str, version))}, entitlement={entitlement!r}."
    )


if __name__ == "__main__":
    main()
