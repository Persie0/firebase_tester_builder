#!/usr/bin/env python3
import json
import sys
import zipfile
from pathlib import Path

MIN_SCORE = 25.0
# Google Play's February 2027 minimum applies to apps with >10 MB DEX code.
# Keep the 25% gate strictly enforced for apps above this documented size.
APP_DEX_MINIMUM_BYTES = 10_000_000
METADATA = "BUNDLE-METADATA/com.android.tools/r8.json"
DEFAULT_AAB = Path("build/app/outputs/bundle/release/app-release.aab")

DISABLED_KEYS = {
    "Optimization": "noOptimizationPercentage",
    "Obfuscation": "noObfuscationPercentage",
    "Shrinking": "noShrinkingPercentage",
}
ENABLED_KEYS = {
    "Optimization": "isOptimizationsEnabled",
    "Obfuscation": "isObfuscationEnabled",
    "Shrinking": "isShrinkingEnabled",
}


def find_key(node, wanted):
    if isinstance(node, dict):
        if wanted in node:
            return node[wanted]
        for value in node.values():
            found = find_key(value, wanted)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = find_key(value, wanted)
            if found is not None:
                return found
    return None


def fail(message):
    print(f"::error::{message}", file=sys.stderr)
    return 1


def main():
    aab = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_AAB
    if not aab.is_file():
        return fail(f"Release AAB not found: {aab}")

    try:
        with zipfile.ZipFile(aab) as bundle:
            try:
                raw = bundle.read(METADATA)
                dex_bytes = sum(
                    entry.file_size
                    for entry in bundle.infolist()
                    if "/dex/" in entry.filename and entry.filename.endswith(".dex")
                )
            except KeyError:
                return fail(f"Mandatory R8 metadata {METADATA} is missing from {aab}")
    except zipfile.BadZipFile:
        return fail(f"Release bundle is not a valid AAB/ZIP: {aab}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return fail(f"R8 metadata {METADATA} is invalid JSON: {exc}")

    if dex_bytes == 0:
        return fail("Release AAB does not contain measurable DEX code")

    # .dex entries are counted by their uncompressed size, across all modules.
    # This is the actual DEX code footprint, not the size of the AAB or native libs.
    enforce_minimum = dex_bytes > APP_DEX_MINIMUM_BYTES
    print(f"DEX code: {dex_bytes / 1_000_000:.3f} MB ({dex_bytes:,} bytes)")
    if not enforce_minimum:
        print("Small app: below Google Play's >10 MB DEX applicability threshold.")

    metrics_out = Path("build/r8-metrics.json")
    metrics_out.parent.mkdir(parents=True, exist_ok=True)
    metrics_out.write_bytes(raw)

    failures = []
    for name in ("Optimization", "Obfuscation", "Shrinking"):
        enabled = find_key(data, ENABLED_KEYS[name])
        if enabled is not True:
            failures.append(f"{name} is not enabled")

        disabled = find_key(data, DISABLED_KEYS[name])
        if disabled is None:
            failures.append(f"{name} score is unavailable")
            print(f"{name}: unavailable")
            continue

        try:
            score = 100.0 - float(disabled)
        except (TypeError, ValueError):
            failures.append(f"{name} score is invalid: {disabled!r}")
            print(f"{name}: invalid")
            continue

        print(f"{name}: {score:.2f}% available to R8")
        if not 0.0 <= score <= 100.0:
            failures.append(f"{name} score is out of range: {score!r}")
        elif score < MIN_SCORE:
            if enforce_minimum:
                failures.append(f"{name} score {score:.2f}% is below {MIN_SCORE:.2f}%")
            else:
                print(
                    f"::warning::{name} score {score:.2f}% is below {MIN_SCORE:.2f}%, "
                    "but this app's DEX size is below Google's enforcement threshold."
                )

    if failures:
        print(
            "R8 release gate failed. Every Play upload must have optimization, "
            "obfuscation, and shrinking at or above 25.00%.",
            file=sys.stderr,
        )
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    if enforce_minimum:
        print("R8 release gate passed: all three scores are >= 25.00%.")
    else:
        print("R8 release gate passed: all R8 dimensions enabled and metadata valid; "
              "DEX size below 10 MB.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
