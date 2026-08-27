from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "project" / "config.json"
TIMELINE_PATH = ROOT / "project" / "content" / "timeline.json"
CONTRACT_PATH = ROOT / "project" / "content" / "content-contract.json"
STORYBOARD_PATH = ROOT / "project" / "content" / "storyboard.md"


CUE_BEATS = {
    1: (0.2, 3.4), 2: (3.7, 7.8),
    3: (0.4, 4.5), 4: (4.8, 10.0), 5: (10.3, 15.7),
    6: (0.4, 4.6), 7: (4.9, 10.1), 8: (10.4, 15.7),
    9: (0.5, 5.2), 10: (5.5, 10.4), 11: (10.7, 16.0), 12: (16.3, 22.0), 13: (22.3, 30.5),
    14: (0.4, 4.8), 17: (5.1, 10.3), 20: (10.6, 15.7),
    21: (0.4, 4.0), 22: (4.3, 8.0), 24: (8.3, 11.7),
    25: (0.2, 3.8),
}


def clock(seconds: float) -> str:
    minutes = int(seconds // 60)
    remainder = seconds - minutes * 60
    return f"{minutes:02d}:{remainder:04.1f}"


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    timeline = json.loads(TIMELINE_PATH.read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    beat = float(config["audio"]["beat_seconds"])
    section_beats = [int(value) for value in config["audio"]["section_beats"]]
    if len(section_beats) != len(timeline["scenes"]):
        raise ValueError("audio.section_beats must match the scene count")

    old_starts = {int(scene["id"]): float(scene["start"]) for scene in timeline["scenes"]}
    cursor = 0.0
    energies = ["quiet", "building", "building", "rise-to-high", "high", "high-to-outro", "outro"]
    for scene, beats, energy in zip(timeline["scenes"], section_beats, energies):
        old_duration = float(scene["end"]) - float(scene["start"])
        scene.setdefault("design_duration", old_duration)
        for event in scene.get("teaching_events", []):
            event.setdefault("design_at", float(event["at"]))
        duration = beats * beat
        scene["start"] = round(cursor, 6)
        scene["end"] = round(cursor + duration, 6)
        scene["music_energy"] = energy
        scale = duration / float(scene["design_duration"])
        for event in scene.get("teaching_events", []):
            event["at"] = round(float(event["design_at"]) * scale, 6)
        cursor += duration

    fps = float(config["video"]["fps"])
    locked_duration = round(cursor * fps) / fps
    timeline["scenes"][-1]["end"] = locked_duration
    timeline["duration"] = locked_duration
    timeline["timing_status"] = "locked_to_bgm"
    scene_by_id = {int(scene["id"]): scene for scene in timeline["scenes"]}
    for cue in timeline["cues"]:
        cue_id = int(cue["id"])
        scene = scene_by_id[int(cue["scene_id"])]
        start_beat, end_beat = CUE_BEATS[cue_id]
        cue["start"] = round(float(scene["start"]) + start_beat * beat, 6)
        cue["end"] = round(float(scene["start"]) + end_beat * beat, 6)

    for proof in contract["proofs"]:
        scene_id = int(proof["scene_id"])
        old_scene_start = old_starts[scene_id]
        proof.setdefault("design_scene_t", float(proof["time"]) - old_scene_start)
        scene = scene_by_id[scene_id]
        scene_duration = float(scene["end"]) - float(scene["start"])
        scale = scene_duration / float(scene["design_duration"])
        proof["time"] = round(float(scene["start"]) + float(proof["design_scene_t"]) * scale, 6)

    TIMELINE_PATH.write_text(json.dumps(timeline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CONTRACT_PATH.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    storyboard = STORYBOARD_PATH.read_text(encoding="utf-8")
    cue_map = {int(cue["id"]): cue for cue in timeline["cues"]}
    for cue_id, cue in cue_map.items():
        pattern = re.compile(rf"(\|\s*{cue_id:02d}\s*\|\s*)[^|]+(\|)")
        value = f"{clock(float(cue['start']))}–{clock(float(cue['end']))} "
        storyboard = pattern.sub(rf"\g<1>{value}\g<2>", storyboard)
    STORYBOARD_PATH.write_text(storyboard, encoding="utf-8")
    print(json.dumps({
        "duration": locked_duration,
        "bpm": config["audio"]["bpm"],
        "source_start": config["audio"]["source_start"],
        "source_end": round(float(config["audio"]["source_start"]) + locked_duration, 6),
        "scene_boundaries": [scene["start"] for scene in timeline["scenes"]] + [locked_duration],
    }, indent=2))


if __name__ == "__main__":
    main()
