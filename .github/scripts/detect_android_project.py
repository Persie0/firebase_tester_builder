#!/usr/bin/env python3
"""Locate an Android Gradle application within a mono-repository checkout."""

import argparse
import os
from pathlib import Path

SKIP_DIRS = {
    ".git", ".gradle", ".github", "build", ".dart_tool", "node_modules",
    ".firebase_builder", ".firebase_builder_detector", ".firebase_builder_helpers",
    "vendor", ".idea", "old", "out",
}


def is_gradle_app(root: Path, require_kotlin: bool) -> bool:
    if not any((root / name).is_file() for name in ("settings.gradle", "settings.gradle.kts")):
        return False
    if not any((root / "app" / name).is_file() for name in ("build.gradle", "build.gradle.kts")):
        return False
    if require_kotlin and not any((root / "app" / "src").rglob("*.kt")):
        return False
    return True


def detect(workspace: Path, project_dir: str = "", mode: str = "auto") -> dict[str, str]:
    workspace = workspace.resolve()
    if mode == "auto" and not project_dir and (workspace / "pubspec.yaml").is_file():
        return {"type": "flutter", "root": ".", "has_wrapper": "false", "build_file": ""}
    if mode == "native-kotlin" and (workspace / "pubspec.yaml").is_file():
        raise ValueError("Flutter projects must use the Flutter workflow, not Kotlin Play automation")

    require_kotlin = mode == "native-kotlin"
    candidates = []
    if project_dir:
        project = (workspace / project_dir).resolve()
        if not project.is_relative_to(workspace) or project == workspace and project_dir not in (".", "./"):
            raise ValueError("project_dir must stay within the checkout")
        if not is_gradle_app(project, require_kotlin):
            raise ValueError(f"No supported {'Kotlin ' if require_kotlin else ''}Android app at {project_dir!r}")
        candidates = [project]
    else:
        for current, dirs, _ in os.walk(workspace):
            root = Path(current)
            depth = len(root.relative_to(workspace).parts)
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")) if depth < 3 else []
            if is_gradle_app(root, require_kotlin):
                candidates.append(root)
        # Preserve existing repo-root and android/ behavior when a mono-repo has
        # additional sample apps. All other multiple-app layouts are ambiguous.
        preferred = [workspace, workspace / "android"]
        for path in preferred:
            if path in candidates:
                candidates = [path]
                break

    if not candidates:
        raise ValueError("No Android Gradle app detected (settings.gradle[.kts] and app/build.gradle[.kts] required)")
    if len(candidates) > 1:
        names = ", ".join(str(p.relative_to(workspace)) for p in candidates)
        raise ValueError(f"Multiple Android projects found ({names}); set project_dir explicitly")

    root = candidates[0]
    build_file = next(root / "app" / name for name in ("build.gradle.kts", "build.gradle") if (root / "app" / name).is_file())
    wrapper = (root / "gradlew").is_file()
    return {
        "type": "gradle-wrapper" if wrapper else "gradle-system",
        "root": str(root.relative_to(workspace)) or ".",
        "has_wrapper": str(wrapper).lower(),
        "build_file": str(build_file.relative_to(workspace)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", default="", help="Optional relative Gradle project directory")
    parser.add_argument("--mode", choices=("auto", "native-kotlin"), default="auto")
    parser.add_argument("--github-output", help="Path to GITHUB_OUTPUT")
    parser.add_argument("--github-env", help="Path to GITHUB_ENV")
    args = parser.parse_args()
    try:
        result = detect(Path.cwd(), args.project_dir, args.mode)
    except ValueError as exc:
        parser.exit(1, f"::error::{exc}\n")

    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as out:
            for key, value in result.items():
                out.write(f"{key}={value}\n")
    if args.github_env:
        with open(args.github_env, "a", encoding="utf-8") as out:
            out.write(f"PROJECT_ROOT={result['root']}\n")
            if result["build_file"]:
                out.write(f"BUILD_FILE={result['build_file']}\n")
            out.write(f"HAS_WRAPPER={result['has_wrapper']}\n")
    print(f"Detected {result['type']} Android project at {result['root']}")


if __name__ == "__main__":
    main()
