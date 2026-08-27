from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "project" / "config.json"
TIMELINE_PATH = ROOT / "project" / "content" / "timeline.json"
SCRIPTS = ROOT / "project" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from project_digest import content_digest as canonical_content_digest


def resolved(value: str) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else ROOT / path).resolve()


def run(args: list[str], env: dict[str, str]) -> None:
    print("[run] " + " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, env=env, check=True)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def content_digest() -> str:
    return canonical_content_digest(ROOT)


def write_review_context(preview: Path) -> None:
    contract = json.loads((ROOT / "project" / "content" / "content-contract.json").read_text(encoding="utf-8"))
    value = {
        "content_sha256": content_digest(),
        "preview": str(preview.relative_to(ROOT)).replace("\\", "/"),
        "preview_sha256": digest(preview),
        "audience_level": contract.get("audience_level"),
        "proofs": contract.get("proofs", []),
        "required_roles": ["copy", "first_viewer", "technical", "visual_geometry"],
    }
    path = ROOT / "work" / "review-context.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"review context: {path}")


def environment(config: dict) -> tuple[dict[str, str], str, str]:
    env = os.environ.copy()
    def resolve_tool_value(value: str, name: str) -> str:
        if not value:
            return ""
        candidate = Path(value)
        if candidate.is_absolute() and candidate.is_file():
            return str(candidate.resolve())
        relative = ROOT / candidate
        if relative.is_file():
            return str(relative.resolve())
        command = shutil.which(value)
        if command:
            return str(Path(command).resolve())
        raise FileNotFoundError(f"configured {name} is neither a file nor a command: {value}")

    ffmpeg_value = resolve_tool_value(str(config.get("tools", {}).get("ffmpeg", "") or ""), "ffmpeg")
    ffprobe_value = resolve_tool_value(str(config.get("tools", {}).get("ffprobe", "") or ""), "ffprobe")
    if ffmpeg_value:
        env["ARABIDOPSIS_FFMPEG"] = ffmpeg_value
    if ffprobe_value:
        env["ARABIDOPSIS_FFPROBE"] = ffprobe_value
    return env, ffmpeg_value, ffprobe_value


def preflight(config: dict, env: dict[str, str], ffmpeg_value: str, ffprobe_value: str) -> None:
    bgm_value = str(config["audio"].get("source", "") or "")
    if not bgm_value:
        raise SystemExit("BGM is missing. Ask the user to prepare one before locking the timeline.")
    bgm = resolved(bgm_value)
    command = [sys.executable, "-B", str(SCRIPTS / "preflight.py"), "--project", str(ROOT), "--bgm", str(bgm), "--strict"]
    if ffmpeg_value:
        command.extend(["--ffmpeg", env["ARABIDOPSIS_FFMPEG"]])
    if ffprobe_value:
        command.extend(["--ffprobe", env["ARABIDOPSIS_FFPROBE"]])
    run(command, env)


def validate_content(env: dict[str, str], stage: str) -> dict:
    run([sys.executable, "-B", str(SCRIPTS / "verify_examples.py"), str(ROOT)], env)
    run([sys.executable, "-B", str(SCRIPTS / "build_content.py")], env)
    run([sys.executable, "-B", str(SCRIPTS / "qa_code_colors.py")], env)
    timeline = json.loads(TIMELINE_PATH.read_text(encoding="utf-8"))
    run(
        [
            sys.executable,
            "-B",
            str(SCRIPTS / "validate_timeline.py"),
            str(TIMELINE_PATH),
            "--strict-copy",
            "--strict-structure",
            "--warnings-as-errors",
        ],
        env,
    )
    run(
        [
            sys.executable,
            "-B",
            str(SCRIPTS / "validate_project.py"),
            str(ROOT),
            "--stage",
            stage,
            "--warnings-as-errors",
        ],
        env,
    )
    return timeline


def build_preview(env: dict[str, str]) -> Path:
    run([sys.executable, "-B", str(SCRIPTS / "render_animation.py"), "--stills"], env)
    run([sys.executable, "-B", str(SCRIPTS / "qa_layout.py")], env)
    run([sys.executable, "-B", str(SCRIPTS / "qa_motion.py")], env)
    run([sys.executable, "-B", str(SCRIPTS / "build_audio.py")], env)
    silent = ROOT / "work" / "review-silent.mp4"
    preview = ROOT / "work" / "review-preview.mp4"
    run([sys.executable, "-B", str(SCRIPTS / "render_animation.py"), "--output", str(silent), "--scale", "0.5"], env)
    run(
        [
            sys.executable,
            "-B",
            str(SCRIPTS / "finish_video.py"),
            "--silent",
            str(silent),
            "--audio",
            str(ROOT / json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["output"]["audio"]),
            "--output",
            str(preview),
        ],
        env,
    )
    write_review_context(preview)
    return preview


def build_final(config: dict, timeline: dict, env: dict[str, str], ffmpeg_value: str, ffprobe_value: str) -> Path:
    run([sys.executable, "-B", str(SCRIPTS / "render_animation.py"), "--stills"], env)
    run([sys.executable, "-B", str(SCRIPTS / "qa_layout.py")], env)
    run([sys.executable, "-B", str(SCRIPTS / "qa_motion.py")], env)
    run([sys.executable, "-B", str(SCRIPTS / "build_audio.py")], env)
    run([sys.executable, "-B", str(SCRIPTS / "render_animation.py")], env)

    candidate = ROOT / "work" / "candidate-final.mp4"
    candidate.parent.mkdir(parents=True, exist_ok=True)
    run([sys.executable, "-B", str(SCRIPTS / "finish_video.py"), "--output", str(candidate)], env)
    expected = str(float(timeline["duration"]))
    qa_spec = [
        "--width", str(int(config["video"]["width"])),
        "--height", str(int(config["video"]["height"])),
        "--fps", str(float(config["video"]["fps"])),
        "--fade-seconds", str(float(config["audio"].get("fade_seconds", 4.0))),
        "--timeline", str(TIMELINE_PATH),
    ]
    if ffmpeg_value:
        qa_spec.extend(["--ffmpeg", env["ARABIDOPSIS_FFMPEG"]])
    if ffprobe_value:
        qa_spec.extend(["--ffprobe", env["ARABIDOPSIS_FFPROBE"]])
    candidate_report = ROOT / "work" / "candidate-qa.json"
    run(
        [sys.executable, "-B", str(SCRIPTS / "qa_final.py"), str(candidate), "--decode", "--expected-duration", expected, "--warnings-as-errors", "--report", str(candidate_report), *qa_spec],
        env,
    )

    final = (ROOT / config["output"]["final"]).resolve()
    final.parent.mkdir(parents=True, exist_ok=True)
    previous = final.with_name(f"{final.stem}.previous{final.suffix}")
    if final.exists():
        shutil.copy2(final, previous)
    os.replace(candidate, final)
    final_report = ROOT / "project" / "docs" / "QA_REPORT.json"
    final_markdown = ROOT / "project" / "docs" / "QA_REPORT.md"
    run(
        [sys.executable, "-B", str(SCRIPTS / "qa_final.py"), str(final), "--decode", "--expected-duration", expected, "--warnings-as-errors", "--report", str(final_report), "--markdown-report", str(final_markdown), *qa_spec],
        env,
    )
    run([sys.executable, "-B", str(SCRIPTS / "extract_final_proofs.py"), "--video", str(final)], env)
    print(json.dumps({"final": str(final), "sha256": digest(final), "previous": str(previous) if previous.exists() else None}, ensure_ascii=False, indent=2))
    return final


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("preview", "final", "release"), default="preview")
    args = parser.parse_args()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    env, ffmpeg_value, ffprobe_value = environment(config)
    if args.stage == "release":
        run([sys.executable, "-B", str(SCRIPTS / "validate_project.py"), str(ROOT), "--stage", "release", "--warnings-as-errors"], env)
        return
    preflight(config, env, ffmpeg_value, ffprobe_value)
    timeline = validate_content(env, "content" if args.stage == "preview" else "final")
    if args.stage == "preview":
        preview = build_preview(env)
        print(f"preview ready: {preview}")
        print("complete independent reviews against work/review-context.json, then run: python build.py --stage final")
        return
    build_final(config, timeline, env, ffmpeg_value, ffprobe_value)
    print("final media built; create the cover/mobile preview, close proof reviews, then run: python build.py --stage release")


if __name__ == "__main__":
    main()
