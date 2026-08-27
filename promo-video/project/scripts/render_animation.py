from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

import scenes
from render_common import draw_subtitle, make_context, rgba, smooth, progress


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "project" / "config.json"
TIMELINE_PATH = ROOT / "project" / "content" / "timeline.json"


def load() -> tuple[dict, dict]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    timeline = json.loads(TIMELINE_PATH.read_text(encoding="utf-8"))
    return config, timeline


def resolve_ffmpeg(config: dict) -> str:
    explicit = str(config.get("tools", {}).get("ffmpeg", "") or "")
    candidates = [explicit, os.environ.get("ARABIDOPSIS_FFMPEG"), shutil.which("ffmpeg")]
    for value in candidates:
        if value and Path(value).is_file():
            return str(Path(value).resolve())
    raise FileNotFoundError("FFmpeg not found; set project/config.json tools.ffmpeg or ARABIDOPSIS_FFMPEG")


def active_scene(timeline: dict, t: float) -> dict:
    scenes_data = timeline["scenes"]
    for scene in scenes_data:
        if float(scene["start"]) <= t < float(scene["end"]):
            return scene
    if abs(t - float(timeline["duration"])) < 1e-6:
        return scenes_data[-1]
    raise ValueError(f"no scene at {t:.3f}s")


def active_cue(timeline: dict, t: float) -> dict | None:
    for cue in timeline["cues"]:
        if float(cue["start"]) <= t < float(cue["end"]):
            return cue
    return None


def render_frame(config: dict, timeline: dict, t: float) -> Image.Image:
    scene = dict(active_scene(timeline, t))
    scene["all_scenes"] = timeline["scenes"]
    ctx = make_context(config, t, scene)
    scenes.render_scene(ctx)
    cue = active_cue(timeline, t)
    if cue is not None and bool(config.get("subtitles", {}).get("burn_in", True)):
        start, end = float(cue["start"]), float(cue["end"])
        alpha = smooth(min(progress(t, start, 0.18), 1.0 - progress(t, end - 0.18, 0.18)))
        draw_subtitle(ctx, str(cue["text"]), alpha)
    flattened = Image.alpha_composite(
        Image.new("RGBA", ctx.image.size, rgba(config["video"].get("background", "#000000"))),
        ctx.image,
    )
    return flattened.convert("RGB")


def render_stills(config: dict, timeline: dict, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    previews = []
    for index, scene in enumerate(timeline["scenes"], 1):
        start, end = float(scene["start"]), float(scene["end"])
        t = start + (end - start) * 0.62
        frame = render_frame(config, timeline, t)
        slug = re.sub(r"[^A-Za-z0-9_-]+", "-", str(scene.get("id", index))).strip("-") or f"scene-{index}"
        path = output / f"scene-{index:02d}-{slug}.png"
        frame.save(path)
        previews.append(frame.resize((480, 270), Image.Resampling.LANCZOS))
    cols = 3
    rows = max(1, (len(previews) + cols - 1) // cols)
    sheet = Image.new("RGB", (cols * 480, rows * 270), "black")
    for index, preview in enumerate(previews):
        sheet.paste(preview, ((index % cols) * 480, (index // cols) * 270))
    sheet.save(output / "contact-sheet.png")
    print(f"wrote {len(previews)} stills and contact sheet to {output}")


def render_video(config: dict, timeline: dict, output: Path, start: float, end: float, scale: float = 1.0) -> None:
    ffmpeg = resolve_ffmpeg(config)
    fps = float(config["video"]["fps"])
    if not 0.1 <= scale <= 1.0:
        raise ValueError("scale must be between 0.1 and 1.0")
    source_width = int(config["video"]["width"])
    source_height = int(config["video"]["height"])
    width = max(2, round(source_width * scale / 2) * 2)
    height = max(2, round(source_height * scale / 2) * 2)
    start_frame = round(start * fps)
    end_frame = round(end * fps)
    frame_count = max(0, end_frame - start_frame)
    if frame_count == 0:
        raise ValueError("render range contains no frames")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(f"{output.stem}.tmp{output.suffix}")
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "warning",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s:v",
        f"{width}x{height}",
        "-r",
        str(fps),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        str(config["video"].get("preset", "faster")),
        "-tune",
        "animation",
        "-crf",
        str(config["video"].get("crf", 16)),
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "high",
        "-sc_threshold",
        "0",
        "-movflags",
        "+faststart",
        str(temp),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert process.stdin is not None
    started = time.monotonic()
    try:
        for offset, frame_number in enumerate(range(start_frame, end_frame)):
            frame = render_frame(config, timeline, frame_number / fps)
            if frame.size != (width, height):
                frame = frame.resize((width, height), Image.Resampling.LANCZOS)
            process.stdin.write(frame.tobytes())
            if offset % 250 == 0 or offset + 1 == frame_count:
                elapsed = max(0.001, time.monotonic() - started)
                speed = (offset + 1) / elapsed
                eta = (frame_count - offset - 1) / max(speed, 0.001)
                print(f"[render] {offset + 1:05d}/{frame_count:05d} {speed:4.1f}fps ETA {eta / 60:4.1f}m", flush=True)
    except BrokenPipeError as exc:
        raise RuntimeError("FFmpeg stopped while receiving frames") from exc
    finally:
        try:
            process.stdin.close()
        except BrokenPipeError:
            pass
    return_code = process.wait()
    if return_code:
        temp.unlink(missing_ok=True)
        raise RuntimeError(f"FFmpeg exited with {return_code}")
    os.replace(temp, output)


def main() -> None:
    config, timeline = load()
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--end", type=float)
    parser.add_argument("--frame", type=float)
    parser.add_argument("--stills", action="store_true")
    parser.add_argument("--stills-dir", type=Path, default=ROOT / "renders" / "stills")
    parser.add_argument("--scale", type=float, default=1.0)
    args = parser.parse_args()
    if args.frame is not None:
        output = args.output or ROOT / "renders" / f"frame-{args.frame:.3f}.png"
        output.parent.mkdir(parents=True, exist_ok=True)
        render_frame(config, timeline, args.frame).save(output)
        print(output)
        return
    if args.stills:
        render_stills(config, timeline, args.stills_dir)
        return
    output = args.output or ROOT / config["output"]["silent"]
    end = min(float(timeline["duration"]), args.end if args.end is not None else float(timeline["duration"]))
    render_video(config, timeline, output, max(0.0, args.start), end, args.scale)


if __name__ == "__main__":
    main()
