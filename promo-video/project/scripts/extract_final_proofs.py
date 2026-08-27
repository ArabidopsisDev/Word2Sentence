from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def resolve_ffmpeg(config: dict) -> str:
    explicit = str(config.get("tools", {}).get("ffmpeg", "") or "")
    for value in (explicit, os.environ.get("ARABIDOPSIS_FFMPEG"), shutil.which("ffmpeg")):
        if value and Path(value).is_file():
            return str(Path(value).resolve())
    raise FileNotFoundError("FFmpeg not found")


def main() -> int:
    config = json.loads((ROOT / "project" / "config.json").read_text(encoding="utf-8"))
    contract = json.loads((ROOT / "project" / "content" / "content-contract.json").read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "renders" / "final-proofs")
    args = parser.parse_args()
    video = (args.video or ROOT / config["output"]["final"]).resolve()
    if not video.is_file():
        raise FileNotFoundError(video)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    ffmpeg = resolve_ffmpeg(config)
    rows = []
    for proof in contract.get("proofs", []):
        proof_id = str(proof["id"])
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", proof_id):
            raise ValueError(f"unsafe proof id: {proof_id!r}")
        timestamp = float(proof["time"])
        target = (output / f"{proof_id}-{timestamp:08.3f}.png").resolve()
        if output not in target.parents:
            raise ValueError(f"proof target escapes output directory: {target}")
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{timestamp:.6f}", "-i", str(video), "-frames:v", "1", str(target)],
            check=False,
        )
        if result.returncode or not target.is_file():
            raise RuntimeError(f"cannot extract proof {proof_id} at {timestamp:.3f}s")
        rows.append(
            {
                "id": proof_id,
                "time": timestamp,
                "claim": proof.get("claim"),
                "expected_visible": list(dict.fromkeys([*proof.get("expected_visible", []), *proof.get("expected_code", [])])),
                "image": str(target),
                "image_sha256": digest(target),
            }
        )
    manifest = {"video": str(video), "video_sha256": digest(video), "proofs": rows}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
