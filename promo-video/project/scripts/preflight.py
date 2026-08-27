#!/usr/bin/env python3
"""Probe the preferred video environment without mutating the target project."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


SKIP_DIRS = {".git", ".svn", "node_modules", "renders", "work", "cache", "tools", "__pycache__"}
PROJECT_MARKERS = {
    ".prproj": "premiere",
    ".aep": "after-effects",
    ".aepx": "after-effects",
    ".drp": "resolve",
    ".dra": "resolve",
    ".blend": "blender",
    ".kdenlive": "kdenlive",
    ".mlt": "mlt",
    ".fcpxml": "final-cut",
    ".otio": "opentimelineio",
}


def run_text(command: list[str], timeout: int = 12) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return result.returncode, (result.stdout + result.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)


def resolve_tool(explicit: str | None, env_name: str, default_name: str) -> str | None:
    candidates = [explicit, os.environ.get(env_name), shutil.which(default_name)]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate).resolve())
    return None


def probe_python(path: Path) -> dict:
    rc, output = run_text(
        [
            str(path),
            "-c",
            "import json,sys; import PIL; print(json.dumps({'version':sys.version.split()[0],'pillow':getattr(PIL,'__version__',None)}))",
        ]
    )
    value = {"path": str(path), "available": rc == 0}
    if rc == 0:
        try:
            value.update(json.loads(output.splitlines()[-1]))
        except (json.JSONDecodeError, IndexError):
            value["output"] = output
    else:
        value["error"] = output
    return value


def python_candidates() -> list[dict]:
    values: list[Path] = [Path(sys.executable)]
    for item in (
        os.environ.get("ARABIDOPSIS_PYTHON"),
        shutil.which("python"),
        shutil.which("python3"),
        "D:/Anaconda/python.exe",
        "C:/ProgramData/Anaconda3/python.exe",
        str(Path.home() / "anaconda3" / "python.exe"),
        str(Path.home() / "miniconda3" / "python.exe"),
    ):
        if item:
            values.append(Path(item))
    if os.name == "nt" and shutil.which("py"):
        rc, output = run_text(["py", "-0p"])
        if rc == 0:
            for line in output.splitlines():
                match = re.search(r"([A-Za-z]:\\.*?python(?:\.exe)?)\s*$", line.strip(), re.IGNORECASE)
                if match:
                    values.append(Path(match.group(1)))
    unique: list[Path] = []
    seen: set[str] = set()
    for value in values:
        try:
            resolved = value.resolve()
        except OSError:
            continue
        key = str(resolved).lower()
        if key not in seen and resolved.is_file():
            seen.add(key)
            unique.append(resolved)
    return [probe_python(path) for path in unique]


def scan_project(root: Path, limit: int = 5000) -> dict:
    stacks: set[str] = set()
    runtime_markers: set[str] = set()
    markers: list[str] = []
    files_seen = 0
    if not root.exists():
        return {"exists": False, "files_scanned": 0, "stacks": [], "runtime_markers": [], "markers": []}
    for current, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if name.lower() not in SKIP_DIRS]
        for name in files:
            files_seen += 1
            path = Path(current, name)
            suffix = path.suffix.lower()
            if suffix in PROJECT_MARKERS:
                stacks.add(PROJECT_MARKERS[suffix])
                markers.append(str(path))
            if name == "package.json":
                runtime_markers.add("node")
                markers.append(str(path))
                try:
                    package = path.read_text(encoding="utf-8", errors="replace").lower()
                except OSError:
                    package = ""
                if "remotion" in package:
                    stacks.add("remotion")
                if "motion-canvas" in package or "@motion-canvas" in package:
                    stacks.add("motion-canvas")
            elif name in {"pyproject.toml", "requirements.txt"}:
                runtime_markers.add("python")
                markers.append(str(path))
                try:
                    python_project = path.read_text(encoding="utf-8", errors="replace").lower()
                except OSError:
                    python_project = ""
                if re.search(r"(^|[^a-z])manim([^a-z]|$)", python_project):
                    stacks.add("manim")
            if files_seen >= limit:
                return {
                    "exists": True,
                    "files_scanned": files_seen,
                    "truncated": True,
                    "stacks": sorted(stacks),
                    "runtime_markers": sorted(runtime_markers),
                    "markers": markers[:40],
                }
    return {
        "exists": True,
        "files_scanned": files_seen,
        "truncated": False,
        "stacks": sorted(stacks),
        "runtime_markers": sorted(runtime_markers),
        "markers": markers[:40],
    }


def probe_ffmpeg(path: str | None) -> dict:
    if not path:
        return {"available": False}
    rc_v, version = run_text([path, "-hide_banner", "-version"])
    rc_e, encoders = run_text([path, "-hide_banner", "-encoders"])
    rc_f, filters = run_text([path, "-hide_banner", "-filters"])
    return {
        "available": rc_v == 0,
        "path": path,
        "version": version.splitlines()[0] if version else None,
        "libx264": "libx264" in encoders if rc_e == 0 else False,
        "aac": " aac " in f" {encoders} " if rc_e == 0 else False,
        "filters": {
            name: name in filters if rc_f == 0 else False
            for name in ("acrossfade", "loudnorm", "afade", "subtitles")
        },
    }


def probe_bgm(path: Path | None, ffprobe: str | None) -> dict:
    if path is None:
        return {"provided": False}
    info = {"provided": True, "path": str(path), "exists": path.exists()}
    if not path.exists() or not ffprobe:
        return info
    rc, output = run_text(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name,sample_rate,channels:format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    if rc == 0:
        try:
            info["probe"] = json.loads(output)
        except json.JSONDecodeError:
            info["probe_error"] = output
    else:
        info["probe_error"] = output
    return info


def font_candidates(project: Path) -> dict[str, list[str]]:
    config_path = project / "project" / "config.json"
    config: dict = {}
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, OSError):
            config = {}
    roots = [
        project / "assets" / "fonts",
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts",
        Path.home() / ".fonts",
        Path("/usr/share/fonts"),
        Path("/Library/Fonts"),
        Path.home() / "Library/Fonts",
    ]
    names = {
        "cjk": ("AliMama", "SourceHanSans", "NotoSansCJK", "msyh", "simhei"),
        "mono": ("JetBrainsMono", "CascadiaMono", "Consola", "NotoSansMono"),
    }
    found: dict[str, list[str]] = {"cjk": [], "mono": []}
    configured = config.get("fonts", {}) if isinstance(config.get("fonts"), dict) else {}
    for key, value in configured.items():
        if not value:
            continue
        path = Path(str(value))
        path = path if path.is_absolute() else project / path
        if path.is_file():
            kind = "mono" if str(key).startswith("code") else "cjk"
            found[kind].append(str(path.resolve()))
    for root in roots:
        if not root.exists():
            continue
        try:
            paths = []
            for suffix in ("*.ttf", "*.otf", "*.ttc", "*.otc"):
                paths.extend(root.rglob(suffix))
        except OSError:
            continue
        for path in paths:
            compact = path.name.replace(" ", "").lower()
            for kind, hints in names.items():
                if any(hint.lower() in compact for hint in hints):
                    found[kind].append(str(path))
    return {kind: values[:20] for kind, values in found.items()}


def configured_font_coverage(project: Path) -> dict[str, dict]:
    """Reject Latin-only font subsets configured for Chinese audience text."""
    try:
        from PIL import ImageFont
    except ImportError:
        return {}
    config_path = project / "project" / "config.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return {}
    configured = config.get("fonts", {}) if isinstance(config.get("fonts"), dict) else {}
    report: dict[str, dict] = {}
    for key in ("sans", "sans_bold"):
        value = str(configured.get(key, "") or "")
        path = Path(value)
        path = path if path.is_absolute() else project / path
        item = {"path": str(path.resolve()), "loaded": False, "supports_cjk": False, "distinct_cjk_glyphs": 0}
        try:
            font = ImageFont.truetype(str(path), 32)
            signatures = set()
            for character in "表达式树中文测试读取":
                mask = font.getmask(character)
                signatures.add((mask.size, bytes(mask)))
            item.update({"loaded": True, "distinct_cjk_glyphs": len(signatures), "supports_cjk": len(signatures) >= 4})
        except (OSError, ValueError):
            pass
        report[key] = item
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--bgm", type=Path)
    parser.add_argument("--ffmpeg")
    parser.add_argument("--ffprobe")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    project = args.project.resolve()
    ffmpeg = resolve_tool(args.ffmpeg, "ARABIDOPSIS_FFMPEG", "ffmpeg")
    ffprobe = resolve_tool(args.ffprobe, "ARABIDOPSIS_FFPROBE", "ffprobe")
    candidates = python_candidates()
    current_python = next((item for item in candidates if Path(item["path"]).resolve() == Path(sys.executable).resolve()), None)
    pillow = (
        {"available": True, "version": current_python.get("pillow")}
        if current_python and current_python.get("available")
        else {"available": False, "error": (current_python or {}).get("error", "Pillow unavailable in current Python")}
    )
    alternate_python = next((item for item in candidates if item.get("available") and Path(item["path"]).resolve() != Path(sys.executable).resolve()), None)

    disk_anchor = project
    while not disk_anchor.exists() and disk_anchor.parent != disk_anchor:
        disk_anchor = disk_anchor.parent
    if not disk_anchor.exists():
        raise FileNotFoundError(f"no existing ancestor for project path: {project}")
    disk = shutil.disk_usage(disk_anchor)
    dotnet = shutil.which("dotnet")
    node = shutil.which("node")
    blender = shutil.which("blender")
    fonts = font_candidates(project)
    coverage = configured_font_coverage(project)
    report = {
        "project": str(project),
        "python": {"path": sys.executable, "version": sys.version.split()[0]},
        "python_candidates": candidates,
        "alternate_preferred_python": alternate_python,
        "pillow": pillow,
        "ffmpeg": probe_ffmpeg(ffmpeg),
        "ffprobe": {"available": bool(ffprobe), "path": ffprobe},
        "bgm": probe_bgm(args.bgm.resolve() if args.bgm else None, ffprobe),
        "disk": {"path": str(disk_anchor), "free_gib": round(disk.free / 2**30, 2)},
        "project_scan": scan_project(project),
        "tools": {"dotnet": dotnet, "node": node, "blender": blender},
        "fonts": fonts,
        "configured_font_coverage": coverage,
    }
    filters = report["ffmpeg"].get("filters", {})
    preferred_ready = bool(
        pillow.get("available")
        and report["ffmpeg"].get("available")
        and report["ffmpeg"].get("libx264")
        and report["ffmpeg"].get("aac")
        and all(filters.get(name) for name in ("acrossfade", "loudnorm", "afade"))
        and ffprobe
        and bool(fonts["cjk"])
        and bool(fonts["mono"])
        and all(coverage.get(key, {}).get("supports_cjk") for key in ("sans", "sans_bold"))
    )
    bgm_ready = bool(report["bgm"].get("exists"))
    report["preferred_pipeline_ready"] = preferred_ready
    report["timing_can_be_locked"] = preferred_ready and bgm_ready
    if preferred_ready and bgm_ready:
        report["next_action"] = "use-pillow-ffmpeg"
    elif preferred_ready:
        report["next_action"] = "request-bgm-then-lock-timing"
    elif not pillow.get("available") and alternate_python:
        report["next_action"] = f"relaunch-with-python:{alternate_python['path']}"
    elif report["project_scan"].get("stacks"):
        report["next_action"] = "adapt-detected-stack-and-request-bgm-if-needed"
    else:
        report["next_action"] = "ask-once-for-editing-stack-and-bgm"

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.strict and not report["timing_can_be_locked"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
