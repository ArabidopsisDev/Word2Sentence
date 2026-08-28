#!/usr/bin/env python3
"""Validate audience copy, structure, and timing before an Arabidopsis render."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


NOT_BUT = re.compile(r"不是.{0,32}而是")
LABEL_COLON = re.compile(r"^[^，。！？]{1,12}：")
PLACEHOLDER = re.compile(r"\[\s*(?:REPLACE|TODO)[^\]]*\]|__REPLACE__|TBD|待替换|待填写", re.IGNORECASE)
STOCK_PATTERNS = {
    "section-label": re.compile(r"^(规则[一二三四五六七八九十\d]+|第.+部分|解决方案|知识点|定义)[：:]"),
    "next-part": re.compile(r"下一部分.*看看|接下来进入(?:第|下一个|第二|第三|第四|第五)"),
    "say-clear": re.compile(r"先把.*说清楚|先把.*讲清楚"),
    "ready": re.compile(r"准备好了吗"),
    "smart-viewer": re.compile(r"聪明的观众"),
    "simple-reason": re.compile(r"其实原因很简单"),
    "obvious": re.compile(r"显而易见"),
    "of-course-answer": re.compile(r"答案当然"),
    "solved": re.compile(r"迎刃而解"),
    "powerful": re.compile(r"非常强大|最为强大"),
    "urgent": re.compile(r"迫切需要"),
    "natural-law": re.compile(r"天经地义"),
    "fragment": re.compile(r"^(但是|所以|然后|当然|对吧)[，。！…]*$"),
    "roughly-understand": re.compile(r"大致明白即可"),
    "creator-selection": re.compile(r"(?:这次|本期|本视频).{0,12}(?:不逐条|只选|筛选|挑选|略过|不展开|不赘述)"),
    "creator-depth": re.compile(r"(?:小更新|重点|这一部分|这一节|本章).{0,16}(?:讲清|讲透|细讲|详讲|只讲|展开)"),
    "creator-visual": re.compile(r"(?:先|再|最后)?让观众|当前行保持稳定|其余信息逐步补全|保留不变部分.{0,8}关键语法|最后用.{0,12}收束|画面(?:保留|出现|切换)"),
    "creator-process": re.compile(r"创作|剪辑|分镜|字幕(?:放|写|承担)|镜头(?:切|安排)|制作流程|讲解策略"),
    "metaphor-magic": re.compile(r"真正的魔法|别把.+当魔法|一切.+魔法"),
}

ALLOWED_CUE_ROLES = {
    "opening",
    "setup",
    "problem",
    "question",
    "transition",
    "inference",
    "explanation",
    "proof",
    "boundary",
    "summary",
    "endcard",
}


def visual_units(text: str) -> float:
    return sum(0.55 if ord(char) < 128 else 1.0 for char in text if not char.isspace())


def add(items: list[dict], kind: str, message: str, **context: object) -> None:
    items.append({"kind": kind, "message": message, **context})


def strings(value: Any, path: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from strings(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from strings(item, f"{path}.{key}" if path else str(key))


def copy_findings(text: str) -> Iterable[tuple[str, str]]:
    if NOT_BUT.search(text):
        yield "not-but", "stock 不是……而是…… pattern"
    if LABEL_COLON.search(text):
        yield "label-colon", "label-style full-width colon"
    if PLACEHOLDER.search(text):
        yield "placeholder", "visible placeholder text"
    for name, pattern in STOCK_PATTERNS.items():
        if pattern.search(text):
            yield name, "stock, creator-facing, or legacy copy pattern"


def chapter_number(scene: dict) -> int | None:
    value = scene.get("chapter_index")
    return int(value) if value is not None else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("timeline", type=Path)
    parser.add_argument("--strict-copy", action="store_true")
    parser.add_argument("--strict-structure", action="store_true")
    parser.add_argument("--warnings-as-errors", action="store_true")
    parser.add_argument("--max-units", type=float, default=32.0)
    parser.add_argument("--min-duration", type=float, default=1.5)
    parser.add_argument("--max-cps", type=float, default=8.0)
    args = parser.parse_args()

    data = json.loads(args.timeline.read_text(encoding="utf-8-sig"))
    duration = float(data["duration"])
    scenes = sorted(data.get("scenes", []), key=lambda item: float(item["start"]))
    cues = sorted(data.get("cues", []), key=lambda item: float(item["start"]))
    errors: list[dict] = []
    warnings: list[dict] = []

    if duration <= 0:
        add(errors, "duration", "duration must be positive", duration=duration)
    if not scenes:
        add(errors, "scenes", "timeline has no scenes")
    if not cues:
        add(errors, "cues", "timeline has no audience cues")

    previous = 0.0
    scene_ids: set[object] = set()
    for index, scene in enumerate(scenes):
        start, end = float(scene["start"]), float(scene["end"])
        scene_id = scene.get("id", index + 1)
        if scene_id in scene_ids:
            add(errors, "scene-id-duplicate", "scene id must be unique", scene=scene_id)
        scene_ids.add(scene_id)
        if abs(start - previous) > 0.002:
            add(errors, "scene-gap", "scene gap or overlap", scene=scene_id, delta=start - previous)
        if end <= start:
            add(errors, "scene-duration", "scene duration must be positive", scene=scene_id)
        if args.strict_structure and end - start < 8.0 and str(scene.get("role", "")) not in {"opening", "summary", "endcard"} and not bool(scene.get("allow_short_scene")):
            add(warnings, "short-full-scene", "short full-scene page may create slide cadence", scene=scene_id, duration=round(end - start, 3))
        previous = end
    if scenes and abs(previous - duration) > 0.002:
        add(errors, "scene-end", "scenes do not cover full duration", last_end=previous, duration=duration)

    previous_end = -1.0
    cue_ids: set[object] = set()
    for index, cue in enumerate(cues, 1):
        start, end = float(cue["start"]), float(cue["end"])
        text = str(cue.get("text", ""))
        cue_id = cue.get("id", cue.get("global_index", index))
        if args.strict_structure and (not isinstance(cue_id, int) or isinstance(cue_id, bool) or cue_id <= 0):
            add(warnings, "cue-id-type", "cue ids must be positive integers so storyboard coverage remains exact", cue=cue_id)
        if cue_id in cue_ids:
            add(errors, "cue-id-duplicate", "cue id must be unique", cue=cue_id)
        cue_ids.add(cue_id)
        if not text.strip():
            add(errors, "empty", "empty subtitle", cue=cue_id)
        if "\n" in text or "\r" in text:
            add(errors, "newline", "subtitle must be one line", cue=cue_id, text=text)
        if "�" in text:
            add(errors, "replacement-char", "replacement character found", cue=cue_id, text=text)
        if start < previous_end - 0.001:
            add(errors, "overlap", "subtitle overlaps previous cue", cue=cue_id, start=start)
        if start < 0 or end > duration + 0.002 or end <= start:
            add(errors, "cue-range", "invalid cue range", cue=cue_id, start=start, end=end)
        cue_duration = end - start
        if cue_duration < args.min_duration:
            add(warnings, "short", "subtitle duration is too short", cue=cue_id, duration=round(cue_duration, 3), blocking=True)
        elif cue_duration < 3.0 and not bool(data.get("allow_brief_cues")):
            add(warnings, "brief", "short cue needs a reading/animation review but is not automatically invalid", cue=cue_id, duration=round(cue_duration, 3), blocking=False)
        units = visual_units(text)
        if units > args.max_units:
            add(warnings, "width", "subtitle may exceed safe width", cue=cue_id, units=round(units, 2), text=text)
        cps = units / max(0.001, cue_duration)
        if cps > args.max_cps:
            add(warnings, "speed", "subtitle reading speed is high", cue=cue_id, cps=round(cps, 2), text=text)
        if cue.get("scene_id") not in scene_ids:
            add(errors, "scene-id", "cue refers to an unknown scene", cue=cue_id, scene_id=cue.get("scene_id"))
        if args.strict_copy:
            for name, message in copy_findings(text):
                blocking = name in {"placeholder", "label-colon", "section-label", "next-part", "say-clear", "creator-selection", "creator-depth", "creator-visual", "creator-process"}
                add(warnings, name, message, surface="subtitle", cue=cue_id, text=text, blocking=blocking)
        if args.strict_structure:
            role = str(cue.get("role", ""))
            if role not in ALLOWED_CUE_ROLES:
                add(warnings, "cue-role", "cue must declare a valid cognitive role", cue=cue_id, role=role or None)
        previous_end = max(previous_end, end)

    if args.strict_copy:
        for scene in scenes:
            scene_id = scene.get("id")
            surfaces = {
                "title": scene.get("title", ""),
                "chapter_title": scene.get("chapter_title", ""),
                "visual": scene.get("visual", {}),
            }
            for path, text in strings(surfaces):
                for name, message in copy_findings(text):
                    blocking = name in {"placeholder", "label-colon", "section-label", "next-part", "say-clear", "creator-selection", "creator-depth", "creator-visual", "creator-process"}
                    add(warnings, name, message, surface=f"scene[{scene_id}].{path}", text=text, blocking=blocking)

    if args.strict_structure and scenes:
        chapter_scenes = [scene for scene in scenes if bool(scene.get("chapter"))]
        chapter_indices = [chapter_number(scene) for scene in chapter_scenes]
        if not 4 <= len(chapter_scenes) <= 6:
            add(warnings, "chapter-count", "expected 4-6 unique main chapter entrances", count=len(chapter_scenes))
        if any(value is None for value in chapter_indices):
            add(warnings, "chapter-index", "main chapter entrance is missing chapter_index")
        else:
            expected = list(range(1, len(chapter_scenes) + 1))
            if chapter_indices != expected:
                add(warnings, "chapter-sequence", "chapter indices must be unique and consecutive", actual=chapter_indices, expected=expected)
        chapter_titles = [str(scene.get("chapter_title", scene.get("title", ""))).strip() for scene in chapter_scenes]
        for scene in chapter_scenes:
            try:
                chapter_total = int(scene.get("chapter_total"))
            except (TypeError, ValueError):
                chapter_total = -1
            if chapter_total != len(chapter_scenes):
                add(warnings, "chapter-total", "chapter_total must equal the number of main chapters", scene=scene.get("id"), actual=scene.get("chapter_total"), expected=len(chapter_scenes))
        duplicates = sorted(name for name, count in Counter(chapter_titles).items() if name and count > 1)
        if duplicates:
            add(warnings, "chapter-title-duplicate", "main chapter titles must be unique", titles=duplicates)

        scene_titles = [str(scene.get("title", "")).strip() for scene in scenes]
        repeated_scene_titles = sorted(name for name, count in Counter(scene_titles).items() if name and count > 1)
        if repeated_scene_titles:
            add(warnings, "scene-title-duplicate", "repeated full-page titles indicate chapter/shot confusion", titles=repeated_scene_titles)

        slide_limit = max(8, len(chapter_scenes) * 2 + 2)
        if len(scenes) > slide_limit:
            add(warnings, "scene-count", "too many full-page scenes for the chapter count; preserve master compositions", scenes=len(scenes), limit=slide_limit)

        for scene in scenes:
            if not scene.get("master_id"):
                add(warnings, "master-id", "scene must identify its persistent master composition", scene=scene.get("id"))
            if str(scene.get("role", "")) not in {"opening", "summary", "endcard"}:
                events = scene.get("teaching_events")
                if not isinstance(events, list) or not events:
                    add(warnings, "teaching-events", "content scene must declare meaningful local teaching events", scene=scene.get("id"))
                else:
                    times: list[float] = []
                    for event_index, event in enumerate(events):
                        if not isinstance(event, dict):
                            add(warnings, "teaching-event-type", "teaching event must be an object", scene=scene.get("id"), event=event_index)
                            continue
                        try:
                            event_time = float(event.get("at"))
                            times.append(event_time)
                        except (TypeError, ValueError):
                            add(warnings, "teaching-event-time", "teaching event needs a numeric relative time", scene=scene.get("id"), event=event_index)
                        job = str(event.get("job", "")).strip()
                        if len(job) < 3 or PLACEHOLDER.search(job):
                            add(warnings, "teaching-event-job", "teaching event needs a concrete production-only purpose", scene=scene.get("id"), event=event_index)
                        trace_id = str(event.get("trace_id", "")).strip()
                        if len(trace_id) < 2 or PLACEHOLDER.search(trace_id):
                            add(warnings, "teaching-event-trace", "teaching event must name the renderer trace it changes", scene=scene.get("id"), event=event_index)
                        if str(event.get("mode", "")) not in {"persistent", "transient"}:
                            add(warnings, "teaching-event-mode", "teaching event mode must be persistent or transient", scene=scene.get("id"), event=event_index, mode=event.get("mode"))
                    scene_duration = float(scene["end"]) - float(scene["start"])
                    if times:
                        ordered = sorted(times)
                        if ordered != times or ordered[0] < 0 or ordered[-1] > scene_duration:
                            add(warnings, "teaching-event-order", "teaching event times must be ordered and inside the scene", scene=scene.get("id"), times=times)
                        checkpoints = [0.0, *ordered, scene_duration]
                        largest_gap = max((right - left for left, right in zip(checkpoints, checkpoints[1:])), default=scene_duration)
                        event_gap_limit = float(data.get("event_gap_limit", 3.2))
                        if largest_gap > event_gap_limit:
                            add(warnings, "teaching-event-gap", f"more than {event_gap_limit:.1f}s passes without a declared teaching state change", scene=scene.get("id"), gap=round(largest_gap, 3))

        opening_visual = dict(scenes[0].get("visual", {}))
        directory = opening_visual.get("directory")
        if not isinstance(directory, list):
            add(warnings, "directory-missing", "opening visual must provide an explicit unique directory list")
        else:
            if not all(isinstance(item, str) for item in directory):
                add(warnings, "directory-type", "directory entries must be plain strings", types=[type(item).__name__ for item in directory])
            directory_text = [str(item).strip() for item in directory]
            if len(directory_text) != len(chapter_scenes):
                add(warnings, "directory-count", "directory count must equal main chapter count", directory=len(directory_text), chapters=len(chapter_scenes))
            if len(set(directory_text)) != len(directory_text):
                add(warnings, "directory-duplicate", "directory entries must be unique", directory=directory_text)
            if chapter_titles and directory_text != chapter_titles:
                add(warnings, "directory-mismatch", "directory must match main chapter titles in order", directory=directory_text, chapters=chapter_titles)

        if cues and str(cues[0].get("role", "")) != "opening":
            add(warnings, "opening-role", "first audience cue must be an opening invitation", cue=cues[0].get("id"))
        if cues and not re.search(r"大家好|欢迎(?:回来|来到|收看)?|这(?:一)?期.{0,16}(?:看|聊|讲|解释|拆|认识)|本期.{0,16}(?:看|聊|讲|解释|拆|认识)|今天.{0,12}(?:一起|看看|聊聊|来)|我们.{0,8}(?:一起|看看|来)", str(cues[0].get("text", ""))):
            add(warnings, "opening-copy", "opening should naturally invite the viewer into the actual topic", cue=cues[0].get("id"), text=cues[0].get("text"))
        for chapter in chapter_scenes:
            start, end = float(chapter["start"]), float(chapter["end"])
            first = next((cue for cue in cues if start <= float(cue["start"]) < end), None)
            if first is None:
                add(warnings, "chapter-cue", "chapter entrance has no audience cue", scene=chapter.get("id"))
            elif str(first.get("role", "")) not in {"transition", "setup", "question"}:
                add(warnings, "chapter-transition", "first cue at a chapter entrance must reset context in audience copy", scene=chapter.get("id"), cue=first.get("id"), role=first.get("role"))

    report = {
        "timeline": str(args.timeline.resolve()),
        "duration": duration,
        "scenes": len(scenes),
        "cues": len(cues),
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    blocking_warnings = [item for item in warnings if item.get("blocking", True)]
    if errors or (blocking_warnings and args.warnings_as_errors):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
