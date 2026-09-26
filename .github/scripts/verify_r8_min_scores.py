#!/usr/bin/env python3
import json
import sys
import zipfile
from pathlib import Path

MIN_SCORE = 25.0
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
            except KeyError:
                return fail(f"Mandatory R8 metadata {METADATA} is missing from {aab}")
    except zipfile.BadZipFile:
        return fail(f"Release bundle is not a valid AAB/ZIP: {aab}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return fail(f"R8 metadata {METADATA} is invalid JSON: {exc}")

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
        if score < MIN_SCORE:
            failures.append(f"{name} score {score:.2f}% is below {MIN_SCORE:.2f}%")

    if failures:
        print(
            "R8 release gate failed. Every Play upload must have optimization, "
            "obfuscation, and shrinking at or above 25.00%.",
            file=sys.stderr,
        )
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("R8 release gate passed: all three scores are >= 25.00%.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
