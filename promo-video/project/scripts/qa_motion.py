from __future__ import annotations

import json
from pathlib import Path

from PIL import ImageChops, ImageStat

from project_digest import content_digest
from qa_layout import render_base_trace
from render_animation import load


ROOT = Path(__file__).resolve().parents[2]


def difference(left, right) -> tuple[float, int]:
    diff = ImageChops.difference(left.convert("RGB"), right.convert("RGB"))
    mean = sum(ImageStat.Stat(diff).mean) / 3.0
    grayscale = diff.convert("L")
    changed = sum(1 for value in grayscale.getdata() if value >= 8)
    return mean, changed


def tracked(trace: list[dict], trace_id: str) -> list[dict]:
    return [item for item in trace if str(item.get("trace_id", "")) == trace_id and float(item.get("alpha", 0)) > 0]


def state(items: list[dict]) -> list[tuple]:
    return sorted(
        (
            str(item.get("type")),
            str(item.get("value", "")),
            tuple(round(float(value), 2) for value in item.get("bbox", [])),
            round(float(item.get("alpha", 0)), 2),
            json.dumps(item.get("style"), sort_keys=True),
        )
        for item in items
    )


def union_bbox(items: list[dict], width: int, height: int, bottom_limit: int) -> tuple[int, int, int, int] | None:
    boxes = [item.get("bbox") for item in items if isinstance(item.get("bbox"), list) and len(item["bbox"]) == 4]
    if not boxes:
        return None
    left = max(0, int(min(float(box[0]) for box in boxes)) - 8)
    top = max(105, int(min(float(box[1]) for box in boxes)) - 8)
    right = min(width, int(max(float(box[2]) for box in boxes)) + 8)
    bottom = min(bottom_limit, int(max(float(box[3]) for box in boxes)) + 8)
    return (left, top, right, bottom) if right > left and bottom > top else None


def main() -> int:
    config, timeline = load()
    fps = float(config["video"]["fps"])
    bottom_limit = 825 if bool(config.get("subtitles", {}).get("burn_in", True)) else int(config["video"]["height"]) - 24
    frame = 1.0 / fps
    errors: list[dict] = []
    events: list[dict] = []
    for scene in timeline["scenes"]:
        if str(scene.get("role", "")) in {"opening", "summary", "endcard"}:
            continue
        start, end = float(scene["start"]), float(scene["end"])
        for index, event in enumerate(scene.get("teaching_events", [])):
            at = float(event["at"])
            trace_id = str(event["trace_id"])
            mode = str(event["mode"])
            timestamp = start + at
            before_time = max(start + frame, timestamp - 0.12)
            before_image, before_trace = render_base_trace(config, timeline, before_time)
            before_items = tracked(before_trace, trace_id)
            candidates: list[dict] = []
            for offset in (0.12, 0.28, 0.45, 0.65):
                after_time = min(end - frame, timestamp + offset)
                after_image, after_trace = render_base_trace(config, timeline, after_time)
                after_items = tracked(after_trace, trace_id)
                box = union_bbox(before_items + after_items, before_image.width, before_image.height, bottom_limit)
                if box is None:
                    mean, changed, threshold = 0.0, 0, 40
                else:
                    mean, changed = difference(before_image.crop(box), after_image.crop(box))
                    area = max(1, (box[2] - box[0]) * (box[3] - box[1]))
                    threshold = max(40, round(area * 0.003))
                state_changed = state(before_items) != state(after_items)
                candidates.append(
                    {
                        "after": after_time,
                        "mean_difference": round(mean, 6),
                        "changed_pixels": changed,
                        "minimum_changed_pixels": threshold,
                        "trace_before": state(before_items),
                        "trace_after": state(after_items),
                        "trace_changed": state_changed,
                        "passed": state_changed and changed >= threshold and mean >= 0.05,
                    }
                )
            selected = candidates[-1] if mode == "persistent" else max(candidates, key=lambda item: (item["passed"], item["changed_pixels"], item["mean_difference"]))
            passed = bool(selected["passed"])
            row = {
                "scene": scene.get("id"),
                "event": index,
                "job": event.get("job"),
                "trace_id": trace_id,
                "mode": mode,
                "at": at,
                "before": before_time,
                "after": selected["after"],
                "mean_difference": selected["mean_difference"],
                "changed_pixels": selected["changed_pixels"],
                "minimum_changed_pixels": selected["minimum_changed_pixels"],
                "trace_changed": selected["trace_changed"],
                "status": "pass" if passed else "fail",
            }
            events.append(row)
            if not passed:
                errors.append({"kind": "motion-no-visible-change", "message": "declared teaching event did not create a visible content-area change", **row})
    report = {
        "content_sha256": content_digest(ROOT),
        "events": events,
        "errors": errors,
        "warnings": [],
    }
    docs = ROOT / "project" / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    json_path = docs / "QA_MOTION_REPORT.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# 动画状态 QA",
        "",
        f"- 内容 SHA-256：`{report['content_sha256']}`",
        f"- 教学事件：{len(events)}",
        f"- 错误：{len(errors)}",
        "",
        "## 事件",
        "",
        *(f"- scene {item['scene']} / event {item['event']} / {item['at']:.2f}s：{item['status']}，changed={item['changed_pixels']}，mean={item['mean_difference']}" for item in events),
    ]
    (docs / "QA_MOTION_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
