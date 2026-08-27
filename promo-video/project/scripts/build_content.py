from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "project" / "config.json"
TIMELINE = ROOT / "project" / "content" / "timeline.json"
CONTENT = ROOT / "project" / "content"


def srt_time(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def clock(seconds: float) -> str:
    total = int(seconds)
    minutes, secs = divmod(total, 60)
    return f"{minutes:02d}:{secs:02d}"


def main() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    timeline = json.loads(TIMELINE.read_text(encoding="utf-8"))
    scenes = sorted(timeline["scenes"], key=lambda item: float(item["start"]))
    cues = sorted(timeline["cues"], key=lambda item: float(item["start"]))
    scene_map = {scene["id"]: scene for scene in scenes}

    blocks = []
    for index, cue in enumerate(cues, 1):
        text = str(cue["text"]).replace("<", "＜").replace(">", "＞")
        blocks.append(f"{index}\n{srt_time(float(cue['start']))} --> {srt_time(float(cue['end']))}\n{text}")
    (CONTENT / "subtitles.srt").write_text("\n\n".join(blocks) + "\n", encoding="utf-8-sig")

    grouped: dict[object, list[dict]] = defaultdict(list)
    for cue in cues:
        grouped[cue["scene_id"]].append(cue)
    script = [
        f"# 《{config['project_name']}》屏幕文案",
        "",
        "- 声音：仅使用用户提供的 BGM，无配音",
        "- 字幕：严格单行；画面承担代码细节，字幕承担阅读主线",
        "",
    ]
    for scene in scenes:
        script.extend([f"## {scene['title']}（{clock(float(scene['start']))}–{clock(float(scene['end']))}）", ""])
        for cue in grouped.get(scene["id"], []):
            script.append(f"- `{clock(float(cue['start']))}–{clock(float(cue['end']))}` {cue['text']}")
        script.append("")
    (CONTENT / "script.md").write_text("\n".join(script).rstrip() + "\n", encoding="utf-8")

    bpm = config["audio"].get("bpm")
    with (CONTENT / "music-cues.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["scene_id", "section", "start", "end", "start_seconds", "end_seconds", "bgm_source_start", "bgm_source_end", "beats", "energy", "edit_note"])
        source_start = float(config["audio"].get("source_start", 0.0))
        for scene in scenes:
            length = float(scene["end"]) - float(scene["start"])
            beats = round(length * float(bpm) / 60) if bpm else ""
            writer.writerow(
                [
                    scene["id"],
                    scene["title"],
                    clock(float(scene["start"])),
                    clock(float(scene["end"])),
                    f"{float(scene['start']):.3f}",
                    f"{float(scene['end']):.3f}",
                    f"{source_start + float(scene['start']):.3f}",
                    f"{source_start + float(scene['end']):.3f}",
                    beats,
                    scene.get("music_energy", ""),
                    scene.get("edit_note", "replace with a topic-specific music cue"),
                ]
            )
    unknown = sorted({cue["scene_id"] for cue in cues} - set(scene_map))
    if unknown:
        raise ValueError(f"cues reference unknown scenes: {unknown}")
    print(f"built {len(cues)} subtitles across {len(scenes)} scenes")


if __name__ == "__main__":
    main()
