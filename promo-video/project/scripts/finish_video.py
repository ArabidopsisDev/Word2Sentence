from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "project" / "config.json"
TIMELINE_PATH = ROOT / "project" / "content" / "timeline.json"


def resolve_ffmpeg(config: dict) -> str:
    explicit = str(config.get("tools", {}).get("ffmpeg", "") or "")
    for value in (explicit, os.environ.get("ARABIDOPSIS_FFMPEG"), shutil.which("ffmpeg")):
        if value and Path(value).is_file():
            return str(Path(value).resolve())
    raise FileNotFoundError("FFmpeg not found")


def meta_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("=", "\\=").replace(";", "\\;").replace("#", "\\#").replace("\n", " ")


def write_chapters(timeline: dict) -> Path:
    chapters = [scene for scene in timeline["scenes"] if scene.get("chapter")]
    path = ROOT / "work" / "chapters.ffmeta"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [";FFMETADATA1"]
    for index, scene in enumerate(chapters):
        # The first published chapter also covers the opening so media chapters remain continuous from t=0.
        start = 0.0 if index == 0 else float(scene["start"])
        end = float(chapters[index + 1]["start"]) if index + 1 < len(chapters) else float(timeline["duration"])
        rows.extend(
            [
                "[CHAPTER]",
                "TIMEBASE=1/1000",
                f"START={round(start * 1000)}",
                f"END={round(end * 1000)}",
                f"title={meta_escape(str(scene.get('chapter_title', scene.get('title', ''))))}",
            ]
        )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def concat_parts(ffmpeg: str, parts: list[Path], silent: Path) -> None:
    if not parts:
        return
    for part in parts:
        if not part.is_file():
            raise FileNotFoundError(part)
    listing = ROOT / "work" / "render-parts.txt"
    listing.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for part in parts:
        escaped = part.resolve().as_posix().replace("'", "'\\''")
        rows.append(f"file '{escaped}'")
    listing.write_text("\n".join(rows) + "\n", encoding="utf-8")
    silent.parent.mkdir(parents=True, exist_ok=True)
    temp = silent.with_name(f"{silent.stem}.tmp{silent.suffix}")
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "warning", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(temp)],
        check=False,
    )
    if result.returncode:
        temp.unlink(missing_ok=True)
        raise RuntimeError(f"concat failed with {result.returncode}")
    os.replace(temp, silent)


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    timeline = json.loads(TIMELINE_PATH.read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser()
    parser.add_argument("--silent", type=Path)
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--parts", type=Path, nargs="*")
    args = parser.parse_args()
    ffmpeg = resolve_ffmpeg(config)
    silent = (args.silent or ROOT / config["output"]["silent"]).resolve()
    audio = (args.audio or ROOT / config["output"]["audio"]).resolve()
    output = (args.output or ROOT / config["output"]["final"]).resolve()
    if args.parts:
        concat_parts(ffmpeg, [path.resolve() for path in args.parts], silent)
    for path in (silent, audio):
        if not path.is_file():
            raise FileNotFoundError(path)
    chapters = write_chapters(timeline)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(f"{output.stem}.tmp{output.suffix}")
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "warning",
        "-y",
        "-i",
        str(silent),
        "-i",
        str(audio),
        "-f",
        "ffmetadata",
        "-i",
        str(chapters),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-map_metadata",
        "2",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "320k",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-metadata",
        "comment=BGM only, no narration; no burned-in subtitles; optional external SRT is included with the project.",
        "-t",
        f"{float(timeline['duration']):.6f}",
        "-movflags",
        "+faststart",
        str(temp),
    ]
    result = subprocess.run(command, check=False)
    if result.returncode:
        temp.unlink(missing_ok=True)
        raise RuntimeError(f"FFmpeg exited with {result.returncode}")
    os.replace(temp, output)
    print(output)


if __name__ == "__main__":
    main()
