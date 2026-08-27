#!/usr/bin/env python3
"""Validate the final MP4 and report reproducible media evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path


MEAN_VOLUME = re.compile(r"mean_volume:\s*(-?inf|-?\d+(?:\.\d+)?)\s*dB")
LOUDNESS_JSON = re.compile(r"\{\s*\"input_i\".*?\}", re.DOTALL)


def tool(value: str | None, name: str) -> str:
    result = value or os.environ.get(f"ARABIDOPSIS_{name.upper()}") or shutil.which(name)
    if not result:
        raise SystemExit(f"{name} not found; pass --{name}")
    return result


def run(command: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def ratio(value: str) -> float:
    return float(Fraction(value)) if value and value != "0/0" else 0.0


def numeric(value: object) -> float | None:
    try:
        return float(value) if value not in (None, "", "N/A") else None
    except (TypeError, ValueError):
        return None


def stream_end(stream: dict) -> float | None:
    start = numeric(stream.get("start_time")) or 0.0
    duration = numeric(stream.get("duration"))
    if duration is None:
        duration_ts = numeric(stream.get("duration_ts"))
        time_base = stream.get("time_base")
        if duration_ts is not None and time_base:
            duration = duration_ts * ratio(str(time_base))
    return start + duration if duration is not None else None


def volume_window(ffmpeg: str, media: Path, start: float, length: float) -> float | None:
    result = run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostats",
            "-ss",
            f"{start:.3f}",
            "-t",
            f"{length:.3f}",
            "-i",
            str(media),
            "-map",
            "0:a:0",
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ],
        timeout=60,
    )
    match = MEAN_VOLUME.search(result.stderr + result.stdout)
    if not match or match.group(1) == "-inf":
        return None
    return float(match.group(1))


def loudness_stats(ffmpeg: str, media: Path) -> dict | None:
    result = run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostats",
            "-i",
            str(media),
            "-map",
            "0:a:0",
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
            "-f",
            "null",
            "-",
        ],
        timeout=300,
    )
    matches = LOUDNESS_JSON.findall(result.stderr + result.stdout)
    return json.loads(matches[-1]) if result.returncode == 0 and matches else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("media", type=Path)
    parser.add_argument("--ffprobe")
    parser.add_argument("--ffmpeg")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--fps", type=float, default=25.0)
    parser.add_argument("--video-codec", default="h264")
    parser.add_argument("--video-profile", default="High")
    parser.add_argument("--pixel-format", default="yuv420p")
    parser.add_argument("--audio-codec", default="aac")
    parser.add_argument("--expected-frames", type=int)
    parser.add_argument("--min-chapters", type=int, default=1)
    parser.add_argument("--timeline", type=Path)
    parser.add_argument("--expected-duration", type=float)
    parser.add_argument("--duration-tolerance", type=float, default=0.06)
    parser.add_argument("--allow-soft-subtitle", action="store_true")
    parser.add_argument("--decode", action="store_true")
    parser.add_argument("--fade-seconds", type=float, default=4.0)
    parser.add_argument("--skip-loudness", action="store_true")
    parser.add_argument("--lufs-min", type=float, default=-20.0)
    parser.add_argument("--lufs-max", type=float, default=-14.0)
    parser.add_argument("--true-peak-max", type=float, default=-1.0)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--markdown-report", type=Path)
    parser.add_argument("--warnings-as-errors", action="store_true")
    args = parser.parse_args()

    media = args.media.resolve()
    if not media.is_file():
        raise SystemExit(f"media not found: {media}")
    ffprobe = tool(args.ffprobe, "ffprobe")
    ffmpeg = tool(args.ffmpeg, "ffmpeg")
    probe = run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-show_chapters",
            "-of",
            "json",
            str(media),
        ]
    )
    if probe.returncode:
        print(probe.stderr)
        return 2
    data = json.loads(probe.stdout)
    streams = data.get("streams", [])
    videos = [item for item in streams if item.get("codec_type") == "video"]
    audios = [item for item in streams if item.get("codec_type") == "audio"]
    subtitles = [item for item in streams if item.get("codec_type") == "subtitle"]
    errors: list[str] = []
    warnings: list[str] = []
    if len(videos) != 1:
        errors.append(f"expected one video stream, got {len(videos)}")
    if len(audios) != 1:
        errors.append(f"expected one audio stream, got {len(audios)}")
    if subtitles and not args.allow_soft_subtitle:
        errors.append(f"unexpected subtitle streams: {len(subtitles)}")
    if videos:
        video = videos[0]
        if str(video.get("codec_name")) != args.video_codec:
            errors.append(f"unexpected video codec: {video.get('codec_name')}")
        if args.video_profile and str(video.get("profile")) != args.video_profile:
            errors.append(f"unexpected video profile: {video.get('profile')}")
        if str(video.get("pix_fmt")) != args.pixel_format:
            errors.append(f"unexpected pixel format: {video.get('pix_fmt')}")
        if int(video.get("width", 0)) != args.width or int(video.get("height", 0)) != args.height:
            errors.append(f"unexpected dimensions: {video.get('width')}x{video.get('height')}")
        actual_fps = ratio(video.get("avg_frame_rate") or video.get("r_frame_rate", "0/0"))
        if abs(actual_fps - args.fps) > 0.001:
            errors.append(f"unexpected fps: {actual_fps}")
        expected_frames = args.expected_frames
        if expected_frames is None and args.expected_duration is not None:
            expected_frames = round(args.expected_duration * args.fps)
        actual_frames = video.get("nb_frames")
        if expected_frames is not None:
            if actual_frames is None:
                errors.append("video frame count is unavailable")
            elif int(actual_frames) != expected_frames:
                errors.append(f"unexpected frame count: {actual_frames}, expected {expected_frames}")
    if audios:
        audio = audios[0]
        if str(audio.get("codec_name")) != args.audio_codec:
            errors.append(f"unexpected audio codec: {audio.get('codec_name')}")
        if int(audio.get("sample_rate", 0)) != 48000:
            errors.append(f"audio sample rate is {audio.get('sample_rate')}, expected 48000")
        if int(audio.get("channels", 0)) != 2:
            errors.append(f"audio channels is {audio.get('channels')}, expected 2")
    duration = float(data.get("format", {}).get("duration", 0.0))
    if args.expected_duration is not None and abs(duration - args.expected_duration) > args.duration_tolerance:
        errors.append(f"duration {duration:.3f}s differs from expected {args.expected_duration:.3f}s")
    if audios:
        audio_end = stream_end(audios[0])
        if audio_end is None:
            errors.append("audio stream duration/end time is unavailable")
        elif abs(audio_end - duration) > args.duration_tolerance:
            errors.append(f"audio stream ends at {audio_end:.3f}s, media ends at {duration:.3f}s")
    chapters = sorted(data.get("chapters", []), key=lambda item: float(item.get("start_time", 0.0)))
    if len(chapters) < args.min_chapters:
        errors.append(f"expected at least {args.min_chapters} chapters, got {len(chapters)}")
    elif chapters:
        chapter_tolerance = 0.003
        if abs(float(chapters[0].get("start_time", 0.0))) > chapter_tolerance:
            errors.append("chapters do not start at 0")
        previous_end = 0.0
        for index, chapter in enumerate(chapters):
            start_time = float(chapter.get("start_time", 0.0))
            end_time = float(chapter.get("end_time", 0.0))
            if index and abs(start_time - previous_end) > chapter_tolerance:
                errors.append(f"chapter gap/overlap before chapter {index}: {start_time - previous_end:+.6f}s")
            if end_time <= start_time:
                errors.append(f"chapter {index} has non-positive duration")
            previous_end = end_time
        if abs(previous_end - duration) > args.duration_tolerance:
            errors.append(f"chapters end at {previous_end:.3f}s, media ends at {duration:.3f}s")
    if args.timeline:
        timeline = json.loads(args.timeline.resolve().read_text(encoding="utf-8-sig"))
        expected_scenes = [scene for scene in timeline.get("scenes", []) if scene.get("chapter")]
        if len(chapters) != len(expected_scenes):
            errors.append(f"chapter count {len(chapters)} differs from timeline {len(expected_scenes)}")
        else:
            for index, (actual, expected_scene) in enumerate(zip(chapters, expected_scenes)):
                expected_start = 0.0 if index == 0 else float(expected_scene["start"])
                expected_end = float(expected_scenes[index + 1]["start"]) if index + 1 < len(expected_scenes) else float(timeline["duration"])
                expected_title = str(expected_scene.get("chapter_title", expected_scene.get("title", "")))
                actual_title = str(actual.get("tags", {}).get("title", ""))
                if abs(float(actual.get("start_time", 0.0)) - expected_start) > 0.003:
                    errors.append(f"chapter {index} start differs from timeline")
                if abs(float(actual.get("end_time", 0.0)) - expected_end) > args.duration_tolerance:
                    errors.append(f"chapter {index} end differs from timeline")
                if actual_title != expected_title:
                    errors.append(f"chapter {index} title differs: {actual_title!r} != {expected_title!r}")

    decode = None
    if args.decode:
        decoded = run([ffmpeg, "-v", "error", "-i", str(media), "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"])
        decode = {"returncode": decoded.returncode, "message": (decoded.stderr + decoded.stdout).strip()}
        if decoded.returncode:
            errors.append("full decode failed")

    fade: list[dict] = []
    fade_entrance = None
    loudness = None
    if audios and not args.skip_loudness:
        loudness = loudness_stats(ffmpeg, media)
        if loudness is None:
            warnings.append("could not measure final loudness")
        else:
            integrated = float(loudness["input_i"])
            true_peak = float(loudness["input_tp"])
            if not args.lufs_min <= integrated <= args.lufs_max:
                warnings.append(f"integrated loudness {integrated:.2f} LUFS is outside {args.lufs_min}..{args.lufs_max}")
            if true_peak > args.true_peak_max:
                warnings.append(f"true peak {true_peak:.2f} dBTP exceeds {args.true_peak_max:.2f}")
    if not 3.0 <= args.fade_seconds <= 5.0:
        errors.append(f"fade_seconds {args.fade_seconds:.3f} is outside the required 3..5 seconds")
    if audios and args.fade_seconds > 0 and duration > args.fade_seconds + 1:
        start = max(0.0, duration - args.fade_seconds)
        pre = volume_window(ffmpeg, media, max(0.0, start - 1.0), 1.0)
        entrance_window = 0.25
        entrance_before = volume_window(ffmpeg, media, max(0.0, start - entrance_window), entrance_window)
        entrance_after = volume_window(ffmpeg, media, start, entrance_window)
        fade_entrance = {
            "window_seconds": entrance_window,
            "before_db": entrance_before,
            "after_db": entrance_after,
        }
        fade.append({"start": round(start - 1.0, 3), "mean_db": pre, "label": "pre-fade"})
        seconds = max(1, int(round(args.fade_seconds)))
        for index in range(seconds):
            position = start + index
            fade.append({"start": round(position, 3), "mean_db": volume_window(ffmpeg, media, position, 1.0)})
        if pre is None:
            warnings.append("pre-fade audio window is silent or unavailable")
        values = [-120.0 if item["mean_db"] is None else float(item["mean_db"]) for item in fade]
        if len(values) < 4:
            warnings.append("not enough final fade windows were measured")
        elif entrance_before is not None and entrance_after is not None and entrance_after < entrance_before - 9:
            warnings.append("final audio drops too abruptly at the fade entrance")
        elif any(right > left + 4 for left, right in zip(values, values[1:])):
            warnings.append("final fade envelope rises too much between adjacent windows")
        elif values[-1] > values[0] - 8:
            warnings.append("final fade did not reduce mean level by at least 8 dB")
        elif sum(values[-2:]) / 2.0 > sum(values[:2]) / 2.0 - 6:
            warnings.append("final fade tail is not sufficiently below its entrance")

    report = {
        "media": str(media),
        "sha256": sha256(media),
        "size_bytes": media.stat().st_size,
        "duration": duration,
        "streams": streams,
        "chapters": chapters,
        "decode": decode,
        "loudness": loudness,
        "fade_windows": fade,
        "fade_entrance": fade_entrance,
        "errors": errors,
        "warnings": warnings,
    }
    report_targets = [path.resolve() for path in (args.report, args.markdown_report) if path]
    for report_path in report_targets:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        if report_path.suffix.lower() == ".md":
            video_summary = videos[0] if videos else {}
            audio_summary = audios[0] if audios else {}
            lines = [
                "# 最终成片 QA",
                "",
                f"- 文件：`{media}`",
                f"- SHA-256：`{report['sha256']}`",
                f"- 时长：{duration:.3f} 秒",
                f"- 视频：{video_summary.get('codec_name')} / {video_summary.get('profile')} / {video_summary.get('width')}×{video_summary.get('height')} / {video_summary.get('avg_frame_rate')} / {video_summary.get('nb_frames')} 帧",
                f"- 音频：{audio_summary.get('codec_name')} / {audio_summary.get('sample_rate')}Hz / {audio_summary.get('channels')} 声道",
                f"- 章节：{len(data.get('chapters', []))}",
                f"- 软字幕流：{len(subtitles)}",
                f"- 完整解码：{'通过' if decode is None or decode.get('returncode') == 0 else '失败'}",
                f"- 响度：{loudness}",
                f"- 尾部电平：{fade}",
                f"- 错误：{errors or '无'}",
                f"- 告警：{warnings or '无'}",
            ]
            report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors or (warnings and args.warnings_as_errors) else 0


if __name__ == "__main__":
    raise SystemExit(main())
