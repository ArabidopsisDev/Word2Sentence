#!/usr/bin/env python3
"""Canonical material digest shared by preview generation and review validation."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable


SKIP_DIRS = {".git", ".svn", "__pycache__", "bin", "obj", "work", "renders", "node_modules"}


def nested_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from nested_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from nested_strings(item)


def tree_files(path: Path) -> Iterable[Path]:
    if not path.is_dir():
        return
    for current, dirs, files in os.walk(path):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        for name in files:
            candidate = Path(current, name)
            if candidate.is_file() and candidate.suffix.lower() not in {".pyc", ".pyo"}:
                yield candidate.resolve()


def resolve_material(root: Path, value: Any) -> Path | None:
    text = str(value or "").strip()
    if not text or len(text) > 1024 or "\n" in text or "\r" in text:
        return None
    try:
        candidate = Path(text)
        candidate = candidate if candidate.is_absolute() else root / candidate
        candidate = candidate.resolve()
    except (OSError, ValueError):
        return None
    return candidate if candidate.is_file() else None


def material_files(root: Path) -> list[Path]:
    root = root.resolve()
    config_path = root / "project" / "config.json"
    timeline_path = root / "project" / "content" / "timeline.json"
    fixed = [
        root / "build.py",
        root / "build.ps1",
        root / "requirements.txt",
        config_path,
        root / "project" / "content" / "content-contract.json",
        timeline_path,
        root / "project" / "content" / "script.md",
        root / "project" / "content" / "storyboard.md",
        root / "project" / "content" / "code-color-fixture.json",
    ]
    config: dict = {}
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, OSError):
            config = {}
    candidates: list[Path] = [path.resolve() for path in fixed if path.is_file()]
    candidates.extend(tree_files(root / "project" / "scripts"))
    candidates.extend(tree_files(root / "project" / "examples"))
    candidates.extend(tree_files(root / "assets" / "fonts"))
    candidates.extend(tree_files(root / "assets" / "images"))
    explicit_values: list[Any] = []
    if isinstance(config.get("audio"), dict):
        explicit_values.append(config["audio"].get("source"))
    if isinstance(config.get("fonts"), dict):
        explicit_values.extend(config["fonts"].values())
    if isinstance(config.get("material_inputs"), list):
        explicit_values.extend(config["material_inputs"])
    for value in explicit_values:
        material = resolve_material(root, value)
        if material is not None:
            candidates.append(material)
    unique: dict[str, Path] = {}
    for path in candidates:
        key = str(path).lower() if os.name == "nt" else str(path)
        unique[key] = path
    return sorted(unique.values(), key=lambda item: str(item).lower())


def logical_name(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return "external::" + str(path.resolve()).replace("\\", "/")


def content_digest(root: Path) -> str:
    root = root.resolve()
    value = hashlib.sha256()
    for path in material_files(root):
        value.update(logical_name(path, root).encode("utf-8"))
        value.update(b"\0")
        value.update(hashlib.sha256(path.read_bytes()).digest())
        value.update(b"\0")
    return value.hexdigest().upper()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("project_root", type=Path)
    args = parser.parse_args()
    root = args.project_root.resolve()
    print(json.dumps({"project": str(root), "sha256": content_digest(root), "files": [logical_name(path, root) for path in material_files(root)]}, ensure_ascii=False, indent=2))
