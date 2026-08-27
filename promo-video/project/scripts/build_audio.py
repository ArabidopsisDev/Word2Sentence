from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "project" / "config.json"
TIMELINE_PATH = ROOT / "project" / "content" / "timeline.json"
LOUDNESS_JSON = re.compile(r"\{\s*\"input_i\".*?\}", re.DOTALL)


def resolve_tool(config: dict, name: str) -> str:
    explicit = str(config.get("tools", {}).get(name, "") or "")
    env_value = os.environ.get(f"ARABIDOPSIS_{name.upper()}")
    for value in (explicit, env_value, shutil.which(name)):
        if value and Path(value).is_file():
            return str(Path(value).resolve())
    raise FileNotFoundError(f"{name} not found; configure project/config.json tools.{name}")


def source_path(config: dict) -> Path:
    value = str(config["audio"].get("source", "") or "")
    if not value:
        raise ValueError("BGM is missing; ask the user to prepare one before locking timing")
    path = Path(value)
    path = path if path.is_absolute() else ROOT / path
    if not path.is_file():
        raise FileNotFoundError(f"BGM not found: {path}")
    return path.resolve()


def duration_of(ffprobe: str, source: Path) -> float:
    result = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "a:0", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(source)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return float(result.stdout.strip())


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    timeline = json.loads(TIMELINE_PATH.read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    ffmpeg = resolve_tool(config, "ffmpeg")
    ffprobe = resolve_tool(config, "ffprobe")
    bgm = source_path(config)
    source_duration = duration_of(ffprobe, bgm)
    duration = float(timeline["duration"])
    audio = config["audio"]
    loop_mode = str(audio.get("loop_mode", "none"))
    source_start = float(audio.get("source_start", 0.0))

    if loop_mode == "none":
        if source_start < 0 or source_duration + 0.02 < source_start + duration:
            raise ValueError(f"BGM range {source_start:.3f}..{source_start + duration:.3f}s exceeds source duration {source_duration:.3f}s")
        input_args = ["-i", str(bgm)]
        base = f"[0:a:0]aresample=48000,atrim=start={source_start:.6f}:end={source_start + duration:.6f},asetpts=PTS-STARTPTS[base]"
    elif loop_mode == "crossfade_once":
        bpm = audio.get("bpm")
        loop_at = audio.get("loop_at")
        if not bpm or loop_at is None:
            raise ValueError("crossfade_once requires audio.bpm and audio.loop_at")
        crossfade = float(audio.get("crossfade_beats", 4)) * 60.0 / float(bpm)
        head_end = float(loop_at) + crossfade
        if source_duration + 0.02 < head_end:
            raise ValueError("BGM is too short for the requested loop point and crossfade")
        if float(loop_at) + source_duration - 0.02 < duration:
            raise ValueError("one crossfade loop does not cover the full timeline")
        input_args = ["-i", str(bgm), "-i", str(bgm)]
        base = (
            f"[0:a:0]aresample=48000,atrim=start=0:end={head_end:.6f},asetpts=PTS-STARTPTS[head];"
            f"[1:a:0]aresample=48000,asetpts=PTS-STARTPTS[loop];"
            f"[head][loop]acrossfade=d={crossfade:.6f}:c1=tri:c2=tri,"
            f"atrim=start=0:end={duration:.6f},asetpts=N/SR/TB[base]"
        )
    else:
        raise ValueError(f"unsupported audio.loop_mode: {loop_mode}")

    target_i = float(audio.get("target_lufs", -16.0))
    target_tp = float(audio.get("target_true_peak", -1.5))
    target_lra = float(audio.get("target_lra", 11.0))
    measure_graph = f"{base};[base]loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:print_format=json[measure]"
    measure = run([ffmpeg, "-hide_banner", "-nostats", *input_args, "-filter_complex", measure_graph, "-map", "[measure]", "-f", "null", "-"])
    matches = LOUDNESS_JSON.findall(measure.stderr + measure.stdout)
    if measure.returncode or not matches:
        raise RuntimeError(f"loudness measurement failed:\n{measure.stderr}")
    stats = json.loads(matches[-1])
    loudnorm = (
        f"loudnorm=I={target_i}:TP={target_tp}:LRA={target_lra}:"
        f"measured_I={stats['input_i']}:measured_LRA={stats['input_lra']}:"
        f"measured_TP={stats['input_tp']}:measured_thresh={stats['input_thresh']}:"
        f"offset={stats['target_offset']}:linear=true:print_format=summary"
    )
    gain = float(audio.get("post_gain_db", -2.0))
    fade = float(audio.get("fade_seconds", 4.0))
    fade_start = max(0.0, duration - fade)
    final_graph = f"{base};[base]{loudnorm},volume={gain}dB,afade=t=out:st={fade_start:.6f}:d={fade:.6f}[mix]"

    output = (args.output or ROOT / config["output"]["audio"]).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(f"{output.stem}.tmp{output.suffix}")
    result = run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "warning",
            "-y",
            *input_args,
            "-filter_complex",
            final_graph,
            "-map",
            "[mix]",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(temp),
        ]
    )
    if result.returncode:
        temp.unlink(missing_ok=True)
        raise RuntimeError(result.stderr)
    os.replace(temp, output)
    print(json.dumps({"output": str(output), "duration": duration, "measurement": stats}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
