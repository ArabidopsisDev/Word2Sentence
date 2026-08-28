#!/usr/bin/env python3
"""Cross-file content and release gates for an Arabidopsis video project."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import tokenize
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from project_digest import content_digest as canonical_content_digest
from project_digest import material_files


ALLOWED_FORMATS = {"mechanism", "release-overview", "diagnosis", "comparison"}
REQUIRED_REVIEW_ROLES = {"copy", "first_viewer", "technical", "visual_geometry"}
PLACEHOLDER = re.compile(
    r"\[\s*(?:REPLACE|TODO)[^\]]*\]|__REPLACE__|TBD|待替换|待填写|"
    r"replace with a topic-specific|模板场景只用于|逐轮记录反馈原意",
    re.IGNORECASE,
)
CJK = re.compile(r"[\u3400-\u9fff]")
TIMECODE = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})(?::(\d{2}))?(?!\d)")
CUE_ID = re.compile(r"\bCUE[-_ ]?(\d+)\b", re.IGNORECASE)
CUE_RANGE = re.compile(r"\bCUE[-_ ]?(\d+)\s*(?:\.\.|-|—|–|至)\s*(?:CUE[-_ ]?)?(\d+)\b", re.IGNORECASE)
PROOF_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

CREATOR_PATTERNS = {
    "creator-selection": re.compile(r"(?:这次|本期|本视频).{0,12}(?:不逐条|只选|筛选|挑选|略过|不展开|不赘述)"),
    "creator-depth": re.compile(r"(?:小更新|重点|这一部分|这一节|本章).{0,16}(?:讲清|讲透|细讲|详讲|只讲|展开)"),
    "creator-visual": re.compile(r"(?:先|再|最后)?让观众|当前行保持稳定|其余信息逐步补全|保留不变部分.{0,8}关键语法|最后用.{0,12}收束|画面(?:保留|出现|切换)"),
    "creator-process": re.compile(r"创作|剪辑|分镜|字幕(?:放|写|承担)|镜头(?:切|安排)|制作流程|讲解策略"),
}


def digest_file(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest().upper()


def png_dimensions(path: Path) -> tuple[int, int] | None:
    try:
        data = path.read_bytes()[:24]
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
            return None
        return struct.unpack(">II", data[16:24])
    except OSError:
        return None


def digest_content(paths: Iterable[Path], root: Path) -> str:
    value = hashlib.sha256()
    for path in sorted((item.resolve() for item in paths if item.is_file()), key=lambda item: str(item).lower()):
        try:
            name = path.relative_to(root.resolve()).as_posix()
        except ValueError:
            name = str(path)
        value.update(name.encode("utf-8"))
        value.update(b"\0")
        value.update(path.read_bytes())
        value.update(b"\0")
    return value.hexdigest().upper()


def add(items: list[dict], kind: str, message: str, **context: object) -> None:
    items.append({"kind": kind, "message": message, **context})


def load_json(path: Path, errors: list[dict]) -> dict:
    if not path.is_file():
        add(errors, "missing", "required JSON file is missing", path=str(path))
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        add(errors, "json", "cannot parse JSON", path=str(path), error=str(exc))
        return {}
    if not isinstance(value, dict):
        add(errors, "json-type", "top-level JSON value must be an object", path=str(path))
        return {}
    return value


def strings(value: Any, path: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from strings(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from strings(item, f"{path}.{key}" if path else str(key))


def require_text(value: Any, path: str, errors: list[dict], minimum: int = 2) -> str:
    text = str(value or "").strip()
    if len(text) < minimum or PLACEHOLDER.search(text):
        add(errors, "contract-field", "content contract field is empty or placeholder", field=path, value=text)
    return text


def max_timecode(text: str) -> float | None:
    values: list[float] = []
    for match in TIMECODE.finditer(text):
        first, second, third = match.groups()
        if third is None:
            values.append(int(first) * 60 + int(second))
        else:
            values.append(int(first) * 3600 + int(second) * 60 + int(third))
    return max(values) if values else None


def storyboard_coverage(text: str) -> set[int]:
    values = {int(match.group(1)) for match in CUE_ID.finditer(text)}
    for match in CUE_RANGE.finditer(text):
        start, end = int(match.group(1)), int(match.group(2))
        if end >= start and end - start <= 500:
            values.update(range(start, end + 1))
    return values


def python_cjk_literals(path: Path) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    try:
        with tokenize.open(path) as handle:
            for token in tokenize.generate_tokens(handle.readline):
                if token.type == tokenize.STRING and CJK.search(token.string):
                    findings.append((token.start[0], token.string[:160]))
    except (SyntaxError, tokenize.TokenError, UnicodeError) as exc:
        findings.append((0, f"cannot tokenize: {exc}"))
    return findings


def hardcoded_draw_literals(path: Path) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    except (SyntaxError, OSError, UnicodeError) as exc:
        return [(0, f"cannot parse: {exc}")]
    positions = {"draw_text": 2, "draw_code": 1}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
        if name not in positions or len(node.args) <= positions[name]:
            continue
        value = node.args[positions[name]]
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            findings.append((node.lineno, value.value[:160]))
        elif isinstance(value, ast.JoinedStr):
            literal = "".join(item.value for item in value.values if isinstance(item, ast.Constant) and isinstance(item.value, str))
            if re.search(r"[A-Za-z0-9\u3400-\u9fff]", literal):
                findings.append((node.lineno, literal[:160]))
    return findings


def project_content_files(root: Path) -> list[Path]:
    return material_files(root)


def digest_content(paths: Iterable[Path], root: Path) -> str:
    # Keep the old call shape for project validators while using one canonical manifest.
    _ = paths
    return canonical_content_digest(root)


def validate_contract(contract: dict, timeline: dict, errors: list[dict], warnings: list[dict]) -> None:
    status = str(contract.get("status", ""))
    if status != "content_locked":
        add(errors, "content-lock", "content contract must be content_locked before preview/final render", status=status or None)
    format_name = str(contract.get("format", ""))
    if format_name not in ALLOWED_FORMATS:
        add(errors, "format", "unknown narrative format", value=format_name, allowed=sorted(ALLOWED_FORMATS))
    require_text(contract.get("format_reason"), "format_reason", errors, 12)
    require_text(contract.get("topic"), "topic", errors)
    require_text(contract.get("audience_level"), "audience_level", errors)
    code_language = require_text(contract.get("code_language"), "code_language", errors)

    opening = contract.get("opening")
    if not isinstance(opening, dict):
        add(errors, "opening", "content contract opening must be an object")
        opening = {}
    for key in ("greeting_or_invitation", "topic_promise", "reason_to_continue"):
        require_text(opening.get(key), f"opening.{key}", errors)
    if opening.get("directory_visual_only") is not True:
        add(errors, "directory-speech", "directory must remain visual-only in the content contract")

    parts = contract.get("parts")
    if not isinstance(parts, list):
        add(errors, "parts", "content contract parts must be a list")
        parts = []
    if not 4 <= len(parts) <= 6:
        add(errors, "part-count", "content contract must contain 4-6 main parts", count=len(parts))
    indices: list[int] = []
    titles: list[str] = []
    proof_references: set[str] = set()
    for offset, part in enumerate(parts, 1):
        if not isinstance(part, dict):
            add(errors, "part-type", "part must be an object", part=offset)
            continue
        try:
            indices.append(int(part.get("index")))
        except (TypeError, ValueError):
            add(errors, "part-index", "part index must be an integer", part=offset, value=part.get("index"))
        titles.append(require_text(part.get("title"), f"parts[{offset}].title", errors))
        require_text(part.get("viewer_question"), f"parts[{offset}].viewer_question", errors, 4)
        require_text(part.get("bridge_from_previous"), f"parts[{offset}].bridge_from_previous", errors, 4)
        require_text(part.get("exit_answer"), f"parts[{offset}].exit_answer", errors, 4)
        for key in ("known_before", "new_information", "proof_ids"):
            values = part.get(key)
            if not isinstance(values, list) or not values:
                add(errors, "part-list", "part field must be a non-empty list", part=offset, field=key)
                continue
            for index, value in enumerate(values):
                text = require_text(value, f"parts[{offset}].{key}[{index}]", errors)
                if key == "proof_ids" and text:
                    proof_references.add(text)
    expected_indices = list(range(1, len(parts) + 1))
    if indices != expected_indices:
        add(errors, "part-sequence", "part indices must be unique and consecutive", actual=indices, expected=expected_indices)
    duplicate_titles = sorted(name for name, count in Counter(titles).items() if name and count > 1)
    if duplicate_titles:
        add(errors, "part-title-duplicate", "part titles must be unique", titles=duplicate_titles)

    scenes = timeline.get("scenes", []) if isinstance(timeline.get("scenes"), list) else []
    cues = timeline.get("cues", []) if isinstance(timeline.get("cues"), list) else []
    duration = float(timeline.get("duration", 0) or 0)
    scene_map = {scene.get("id"): scene for scene in scenes if isinstance(scene, dict)}
    chapter_scenes = [scene for scene in scenes if isinstance(scene, dict) and bool(scene.get("chapter"))]
    chapter_titles = [str(scene.get("chapter_title", scene.get("title", ""))).strip() for scene in chapter_scenes]
    if chapter_titles != titles:
        add(errors, "contract-chapters", "timeline main chapters must match contract parts exactly", contract=titles, timeline=chapter_titles)

    directory = []
    if scenes and isinstance(scenes[0], dict):
        visual = scenes[0].get("visual", {})
        if isinstance(visual, dict) and isinstance(visual.get("directory"), list):
            if not all(isinstance(item, str) for item in visual["directory"]):
                add(errors, "directory-type", "directory entries must be plain strings")
            directory = [str(item).strip() for item in visual["directory"]]
    if directory != titles:
        add(errors, "contract-directory", "opening directory must match content contract parts exactly", contract=titles, directory=directory)

    proofs = contract.get("proofs")
    if not isinstance(proofs, list) or not proofs:
        add(errors, "proofs", "content contract must contain core proof definitions")
        proofs = []
    proof_ids: set[str] = set()
    for offset, proof in enumerate(proofs, 1):
        if not isinstance(proof, dict):
            add(errors, "proof-type", "proof must be an object", proof=offset)
            continue
        proof_id = require_text(proof.get("id"), f"proofs[{offset}].id", errors)
        if proof_id and not PROOF_ID.fullmatch(proof_id):
            add(errors, "proof-id-format", "proof id must be a short lowercase slug", proof=proof_id)
        if proof_id in proof_ids:
            add(errors, "proof-id-duplicate", "proof id must be unique", proof=proof_id)
        proof_ids.add(proof_id)
        require_text(proof.get("claim"), f"proofs[{offset}].claim", errors, 4)
        scene_id = proof.get("scene_id")
        if scene_id not in scene_map:
            add(errors, "proof-scene", "proof refers to an unknown scene", proof=proof_id, scene_id=scene_id)
            continue
        try:
            timestamp = float(proof.get("time"))
        except (TypeError, ValueError):
            add(errors, "proof-time", "proof time must be numeric", proof=proof_id, value=proof.get("time"))
            continue
        scene = scene_map[scene_id]
        if not float(scene["start"]) <= timestamp < float(scene["end"]) or not 0 <= timestamp <= duration:
            add(errors, "proof-time-range", "proof time must fall inside its scene", proof=proof_id, time=timestamp, scene=[scene.get("start"), scene.get("end")])
        expected = proof.get("expected_visible")
        if not isinstance(expected, list) or not expected:
            add(errors, "proof-visible", "proof expected_visible must be a non-empty list", proof=proof_id)
            continue
        for index, value in enumerate(expected):
            token = require_text(value, f"proofs[{offset}].expected_visible[{index}]", errors)
        product_ui_proof = str(contract.get("proof_visual_mode", "")).lower() == "product-ui"
        expected_code = proof.get("expected_code", [])
        if not product_ui_proof and (not isinstance(expected_code, list) or not expected_code):
            add(errors, "proof-code", "each core proof must name at least one exact code string", proof=proof_id)
        elif not isinstance(expected_code, list):
            add(errors, "proof-code-type", "proof expected_code must be a list", proof=proof_id)
        else:
            for index, value in enumerate(expected_code):
                require_text(value, f"proofs[{offset}].expected_code[{index}]", errors)
        color_checks = proof.get("color_checks", [])
        if not product_ui_proof and (not isinstance(color_checks, list) or not color_checks):
            add(errors, "proof-colors", "each core proof must declare at least one actual-scene semantic color check", proof=proof_id)
        elif not isinstance(color_checks, list):
            add(errors, "proof-color-type", "proof color_checks must be a list", proof=proof_id)
        else:
            for check_index, check in enumerate(color_checks):
                if not isinstance(check, dict):
                    add(errors, "proof-color-type", "proof color check must be an object", proof=proof_id, check=check_index)
                    continue
                require_text(check.get("token"), f"proofs[{offset}].color_checks[{check_index}].token", errors)
                if str(check.get("kind", "")) not in {"keyword", "type", "method", "number", "string", "comment"}:
                    add(errors, "proof-color-kind", "unknown proof color semantic kind", proof=proof_id, check=check_index, kind=check.get("kind"))
        try:
            stable = float(proof.get("min_stable_seconds", 0))
        except (TypeError, ValueError):
            stable = 0
        if stable < 0.8:
            add(warnings, "proof-hold", "core proof should remain stable for at least 0.8s", proof=proof_id, seconds=stable)
        elif timestamp - stable / 2.0 < float(scene["start"]) or timestamp + stable / 2.0 >= float(scene["end"]):
            add(errors, "proof-hold-range", "proof stability window must remain inside its scene", proof=proof_id, time=timestamp, stable=stable)
    missing_proofs = sorted(proof_references - proof_ids)
    if missing_proofs:
        add(errors, "proof-reference", "parts reference unknown proof ids", proofs=missing_proofs)
    unreferenced = sorted(proof_ids - proof_references)
    if unreferenced:
        add(warnings, "proof-unreferenced", "proof is not assigned to a main part", proofs=unreferenced)

    config_code = str(code_language).lower()
    if config_code not in {"csharp", "cs", "cpp", "c++", "rust", "java", "python", "typescript", "javascript", "mixed"}:
        add(warnings, "code-language", "unrecognized code language; use explicit semantic spans", value=code_language)


def validate_docs(root: Path, timeline: dict, errors: list[dict], warnings: list[dict]) -> None:
    docs = root / "project" / "docs"
    requirements = {
        "STYLE_STUDY.md": 280,
        "AUDIENCE_MODEL.md": 280,
        "TECHNICAL_RESEARCH.md": 450,
        "EXAMPLE_DECISIONS.md": 220,
        "PRODUCTION_NOTES.md": 180,
        "REVISION_REVIEW.md": 180,
    }
    for name, minimum in requirements.items():
        path = docs / name
        if not path.is_file():
            add(errors, "doc-missing", "required project evidence document is missing", path=str(path))
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        if len(text.strip()) < minimum:
            add(errors, "doc-placeholder", "evidence document is too short to contain a real review", path=str(path), characters=len(text.strip()), minimum=minimum)
        if PLACEHOLDER.search(text):
            add(errors, "doc-placeholder", "evidence document still contains template text", path=str(path))
        if "�" in text:
            add(errors, "replacement-char", "replacement character found in project document", path=str(path))
    research = docs / "TECHNICAL_RESEARCH.md"
    if research.is_file() and "http" not in research.read_text(encoding="utf-8-sig", errors="replace"):
        add(warnings, "research-source", "technical research should contain primary-source URLs", path=str(research))

    storyboard = root / "project" / "content" / "storyboard.md"
    if not storyboard.is_file():
        add(errors, "storyboard", "storyboard is missing", path=str(storyboard))
    else:
        text = storyboard.read_text(encoding="utf-8-sig", errors="replace")
        if PLACEHOLDER.search(text) or len(text.strip()) < 300:
            add(errors, "storyboard-placeholder", "storyboard must contain cue-level production decisions", path=str(storyboard), characters=len(text.strip()))
        cue_ids = {int(cue["id"]) for cue in timeline.get("cues", []) if isinstance(cue, dict) and str(cue.get("id", "")).isdigit()}
        covered = storyboard_coverage(text)
        missing = sorted(cue_ids - covered)
        if missing:
            add(errors, "storyboard-coverage", "storyboard does not cover every cue", missing=missing[:50], missing_count=len(missing))
        maximum = max_timecode(text)
        duration = float(timeline.get("duration", 0) or 0)
        if maximum is not None and maximum > duration + 1.0:
            add(errors, "storyboard-duration", "storyboard contains a time later than the timeline duration", storyboard_max=maximum, timeline_duration=duration)

    music = root / "project" / "content" / "music-cues.csv"
    if music.is_file():
        text = music.read_text(encoding="utf-8-sig", errors="replace")
        if PLACEHOLDER.search(text):
            add(errors, "music-placeholder", "music cue sheet contains a template edit note", path=str(music))

    verification = root / "project" / "examples" / "verification.json"
    example_report = root / "project" / "docs" / "EXAMPLE_QA.json"
    if not verification.is_file() or not example_report.is_file():
        add(errors, "example-evidence", "example verification spec/report is missing", spec=str(verification), report=str(example_report))
    else:
        try:
            value = json.loads(example_report.read_text(encoding="utf-8-sig"))
            if str(value.get("spec_sha256", "")).upper() != digest_file(verification):
                add(errors, "example-stale", "example QA report does not match the current verification spec")
            if value.get("errors"):
                add(errors, "example-failed", "example QA report contains unresolved errors", count=len(value.get("errors", [])))
            if any(item.get("status") != "pass" for item in value.get("runs", []) if isinstance(item, dict)):
                add(errors, "example-failed", "one or more executable examples did not pass")
        except (json.JSONDecodeError, OSError) as exc:
            add(errors, "example-report", "cannot parse example QA report", error=str(exc), path=str(example_report))


def validate_proof_example_links(root: Path, contract: dict, errors: list[dict]) -> None:
    report_path = root / "project" / "docs" / "EXAMPLE_QA.json"
    if not report_path.is_file():
        return
    try:
        report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return
    entries = {
        str(item.get("id")): item
        for item in [*report.get("runs", []), *report.get("documented_exceptions", [])]
        if isinstance(item, dict)
    }
    for proof in contract.get("proofs", []):
        if not isinstance(proof, dict):
            continue
        proof_id = str(proof.get("id", ""))
        example_id = str(proof.get("example_id", "")).strip()
        if not example_id or PLACEHOLDER.search(example_id):
            add(errors, "proof-example", "every proof must reference a verified example id", proof=proof_id)
            continue
        entry = entries.get(example_id)
        if entry is None:
            add(errors, "proof-example", "proof references an unknown verification run/exception", proof=proof_id, example_id=example_id)
            continue
        if proof_id not in [str(value) for value in entry.get("proof_ids", [])]:
            add(errors, "proof-example", "verification entry does not claim this proof id", proof=proof_id, example_id=example_id)
        source_hashes = entry.get("source_sha256")
        if not isinstance(source_hashes, dict) or not source_hashes:
            add(errors, "proof-source", "verification entry has no hashed source files", proof=proof_id, example_id=example_id)
            continue
        source_text = "\n".join(
            (root / path).read_text(encoding="utf-8-sig", errors="replace")
            for path in source_hashes
            if (root / path).is_file()
        )
        for path, expected_hash in source_hashes.items():
            source = root / path
            if not source.is_file() or digest_file(source) != str(expected_hash).upper():
                add(errors, "proof-source-stale", "verified source hash is stale or missing", proof=proof_id, path=str(source))
        source_contains = proof.get("source_contains")
        if not isinstance(source_contains, list) or not source_contains:
            add(errors, "proof-source", "proof must name exact source text that supports the visible claim", proof=proof_id)
        else:
            for value in source_contains:
                text = str(value)
                if len(text.strip()) < 2 or PLACEHOLDER.search(text) or text not in source_text:
                    add(errors, "proof-source", "proof source_contains text is absent from verified sources", proof=proof_id, text=text)
        for value in proof.get("expected_code", []):
            text = str(value)
            if text not in source_text:
                add(errors, "proof-code-source", "required visible code is not present in the hashed verified sources", proof=proof_id, text=text)
        output_contains = proof.get("output_contains", [])
        if not isinstance(output_contains, list):
            add(errors, "proof-output", "proof output_contains must be a list", proof=proof_id)
        else:
            observed = str(entry.get("stdout", "")) + "\n" + str(entry.get("stderr", ""))
            for value in output_contains:
                text = str(value)
                if len(text.strip()) < 1 or PLACEHOLDER.search(text) or text not in observed:
                    add(errors, "proof-output", "proof output_contains text is absent from verified output", proof=proof_id, text=text)


def validate_surfaces(root: Path, timeline: dict, errors: list[dict], warnings: list[dict]) -> None:
    for scene in timeline.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        if str(scene.get("kind", "")) == "topic_scene":
            add(errors, "template-scene", "generic topic_scene is a smoke-test placeholder; replace it with topic-specific scene logic", scene=scene.get("id"))
        visual = scene.get("visual", {})
        if isinstance(visual, dict) and isinstance(visual.get("code"), list):
            for line_index, line in enumerate(visual["code"]):
                if not isinstance(line, dict):
                    continue
                code_text = str(line.get("text", ""))
                spans = line.get("spans", [])
                if not isinstance(spans, list):
                    add(errors, "semantic-spans", "code spans must be a list", scene=scene.get("id"), line=line_index)
                    continue
                cursor = 0
                for span_index, span in enumerate(spans):
                    if not isinstance(span, dict):
                        add(errors, "semantic-span-type", "every semantic span must be an object", scene=scene.get("id"), line=line_index, span=span_index, value_type=type(span).__name__)
                        continue
                    try:
                        start, end = int(span.get("start")), int(span.get("end"))
                    except (TypeError, ValueError):
                        add(errors, "semantic-span-range", "semantic span start/end must be integers", scene=scene.get("id"), line=line_index, span=span_index)
                        continue
                    kind = str(span.get("kind", ""))
                    if start < cursor or end <= start or end > len(code_text):
                        add(errors, "semantic-span-range", "semantic spans must be ordered, non-overlapping, and inside the code string", scene=scene.get("id"), line=line_index, span=span_index, range=[start, end], length=len(code_text))
                    if kind not in {"keyword", "type", "method", "number", "string", "comment", "text", "operator"}:
                        add(errors, "semantic-span-kind", "unknown semantic span kind", scene=scene.get("id"), line=line_index, span=span_index, kind=kind)
                    cursor = max(cursor, end)
        surface = {"title": scene.get("title", ""), "chapter_title": scene.get("chapter_title", ""), "visual": visual}
        for path, text in strings(surface):
            if PLACEHOLDER.search(text):
                add(errors, "visible-placeholder", "audience-visible scene data contains a placeholder", scene=scene.get("id"), field=path, text=text)
            for name, pattern in CREATOR_PATTERNS.items():
                if pattern.search(text):
                    add(errors, name, "production instruction leaked into audience-visible scene data", scene=scene.get("id"), field=path, text=text)
    for cue in timeline.get("cues", []):
        if not isinstance(cue, dict):
            continue
        text = str(cue.get("text", ""))
        if PLACEHOLDER.search(text):
            add(errors, "visible-placeholder", "audience subtitle contains a placeholder", cue=cue.get("id"), text=text)
        for name, pattern in CREATOR_PATTERNS.items():
            if pattern.search(text):
                add(errors, name, "production instruction leaked into audience subtitle", cue=cue.get("id"), text=text)

    cjk_allowlist = {
        "build_content.py",
        "qa_layout.py",
        "qa_motion.py",
        "qa_code_colors.py",
        "qa_final.py",
        "preflight.py",
        "validate_project.py",
        "validate_timeline.py",
        "verify_examples.py",
    }
    for path in sorted((root / "project" / "scripts").rglob("*.py")):
        for line, value in hardcoded_draw_literals(path):
            add(errors, "renderer-hardcoded-copy", "draw_text/draw_code receives a hard-coded string; move audience copy to timeline data", path=str(path), line=line, literal=value)
        if path.name not in cjk_allowlist:
            for line, value in python_cjk_literals(path):
                add(errors, "renderer-hardcoded-cjk", "renderer/helper contains a CJK string literal outside the infrastructure allowlist", path=str(path), line=line, literal=value)


def validate_code_language(root: Path, contract: dict, timeline: dict, errors: list[dict], warnings: list[dict]) -> None:
    language = str(contract.get("code_language", "")).lower()
    config_path = root / "project" / "config.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        config = {}
    code_config = config.get("code", {}) if isinstance(config.get("code"), dict) else {}
    lexer_mode = str(code_config.get("lexer", "builtin"))
    builtin_languages = {"csharp", "cs", "cpp", "c++"}
    common = root / "project" / "scripts" / "render_common.py"
    if language not in builtin_languages and lexer_mode != "explicit-spans":
        add(errors, "lexer-language", "language has no bundled lexer; set code.lexer=explicit-spans and annotate every visible code token", language=language, lexer=lexer_mode)
    if language in {"cpp", "c++"} and common.is_file():
        text = common.read_text(encoding="utf-8-sig", errors="replace")
        csharp_markers = sum(marker in text for marker in ('"namespace"', '"using"', '"extension"', '"record"'))
        has_dispatch = "language_lexer" in text
        if csharp_markers >= 2 and not has_dispatch:
            add(errors, "lexer-language", "non-C# project appears to use the bundled C#-only keyword heuristic", language=language, path=str(common))
    if lexer_mode == "explicit-spans":
        code_line_count = 0
        for scene in timeline.get("scenes", []):
            visual = scene.get("visual", {}) if isinstance(scene, dict) else {}
            lines = visual.get("code", []) if isinstance(visual, dict) else []
            for line_index, line in enumerate(lines if isinstance(lines, list) else []):
                code_line_count += 1
                if not isinstance(line, dict) or not isinstance(line.get("spans"), list) or not line.get("spans"):
                    add(errors, "explicit-spans", "every visible code line needs semantic spans for this language", scene=scene.get("id"), line=line_index)
                    continue
                code_text = str(line.get("text", ""))
                covered = [False] * len(code_text)
                for span in line["spans"]:
                    if not isinstance(span, dict):
                        continue
                    try:
                        start, end = int(span["start"]), int(span["end"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    for offset in range(max(0, start), min(len(code_text), end)):
                        covered[offset] = True
                for token in re.finditer(r"[A-Za-z_]\w*|\d+(?:\.\d+)?|\"(?:\\.|[^\"])*\"", code_text):
                    if not all(covered[token.start() : token.end()]):
                        add(errors, "explicit-span-coverage", "semantic spans do not cover every visible identifier/literal", scene=scene.get("id"), line=line_index, token=token.group())
        if code_line_count == 0:
            add(errors, "explicit-spans", "explicit-span mode requires structured visible code lines in timeline data")
    fixture = root / "project" / "docs" / "CODE_COLOR_QA.json"
    value = load_json(fixture, errors)
    if value:
        if str(value.get("content_sha256", "")).upper() != canonical_content_digest(root):
            add(errors, "code-color-stale", "code-color QA does not match the current renderer/material digest", path=str(fixture))
        aliases = {"cs": "csharp", "c++": "cpp"}
        if aliases.get(str(value.get("language", "")).lower(), str(value.get("language", "")).lower()) != aliases.get(language, language):
            add(errors, "code-color-language", "code-color QA language differs from content contract", path=str(fixture))
        if str(value.get("lexer", "")) != lexer_mode:
            add(errors, "code-color-lexer", "code-color QA lexer differs from config", path=str(fixture))
        required_palette = {
            "keyword": [86, 156, 214, 255],
            "type": [78, 201, 176, 255],
            "method": [220, 220, 170, 255],
            "number": [179, 196, 147, 255],
            "string": [214, 157, 133, 255],
            "comment": [87, 166, 74, 255],
        }
        if value.get("palette") != required_palette:
            add(errors, "code-color-palette", "code-color QA palette differs from the required semantic colors", actual=value.get("palette"))
        checked_kinds = {str(item.get("kind")) for item in value.get("checks", []) if isinstance(item, dict) and item.get("status") == "pass" and item.get("actual_rgba") == item.get("expected_rgba")}
        if checked_kinds != set(required_palette):
            add(errors, "code-color-coverage", "code-color QA must exercise every required semantic kind", actual=sorted(checked_kinds), expected=sorted(required_palette))
        if value.get("errors") or value.get("warnings") or any(item.get("status") != "pass" for item in value.get("checks", []) if isinstance(item, dict)):
            add(errors, "code-color-findings", "code-color QA contains unresolved findings", path=str(fixture))
        image_value = str(value.get("fixture_image", "") or "")
        image_path = Path(image_value)
        if image_value and not image_path.is_absolute():
            image_path = root / image_path
        if not image_value or not image_path.is_file() or str(value.get("fixture_image_sha256", "")).upper() != (digest_file(image_path) if image_path.is_file() else ""):
            add(errors, "code-color-image", "code-color fixture image is missing or stale", path=str(image_path))


def validate_review(root: Path, errors: list[dict], warnings: list[dict]) -> None:
    context_path = root / "work" / "review-context.json"
    manifest_path = root / "project" / "reviews" / "review-manifest.json"
    context = load_json(context_path, errors)
    manifest = load_json(manifest_path, errors)
    if not context or not manifest:
        return
    actual_content = digest_content(project_content_files(root), root)
    preview_value = str(context.get("preview", "") or "")
    preview_path = Path(preview_value)
    if preview_value and not preview_path.is_absolute():
        preview_path = root / preview_path
    if not preview_value or not preview_path.is_file():
        add(errors, "review-preview", "review context preview is missing", path=str(preview_path))
        actual_preview = ""
    else:
        actual_preview = digest_file(preview_path)
        config_path = root / "project" / "config.json"
        try:
            config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, OSError):
            config = {}
        explicit_ffprobe = str(config.get("tools", {}).get("ffprobe", "") or "") if isinstance(config.get("tools"), dict) else ""
        ffprobe_path: Path | None = None
        for candidate_value in (explicit_ffprobe, os.environ.get("ARABIDOPSIS_FFPROBE"), shutil.which("ffprobe")):
            if not candidate_value:
                continue
            candidate = Path(candidate_value)
            if candidate.is_absolute() and candidate.is_file():
                ffprobe_path = candidate.resolve()
                break
            relative = root / candidate
            if relative.is_file():
                ffprobe_path = relative.resolve()
                break
            command = shutil.which(str(candidate_value))
            if command:
                ffprobe_path = Path(command).resolve()
                break
        if ffprobe_path is None:
            add(errors, "review-preview-probe", "ffprobe is required to validate the independent-review preview")
        else:
            completed = subprocess.run(
                [str(ffprobe_path), "-v", "error", "-show_format", "-show_streams", "-of", "json", str(preview_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            try:
                preview_probe = json.loads(completed.stdout) if completed.returncode == 0 else {}
            except json.JSONDecodeError:
                preview_probe = {}
            streams = preview_probe.get("streams", []) if isinstance(preview_probe, dict) else []
            if completed.returncode != 0 or len([item for item in streams if item.get("codec_type") == "video"]) != 1 or len([item for item in streams if item.get("codec_type") == "audio"]) != 1:
                add(errors, "review-preview-probe", "review preview must be a decodable one-video/one-audio media file", path=str(preview_path))
            else:
                try:
                    preview_duration = float(preview_probe.get("format", {}).get("duration"))
                    timeline_duration = float(json.loads((root / "project" / "content" / "timeline.json").read_text(encoding="utf-8-sig"))["duration"])
                    if abs(preview_duration - timeline_duration) > 0.1:
                        add(errors, "review-preview-duration", "review preview duration does not match the current timeline", preview=preview_duration, timeline=timeline_duration)
                except (TypeError, ValueError, KeyError, json.JSONDecodeError, OSError):
                    add(errors, "review-preview-duration", "cannot verify review preview duration")
    expected_content = str(context.get("content_sha256", "")).upper()
    expected_preview = str(context.get("preview_sha256", "")).upper()
    if expected_content != actual_content:
        add(errors, "review-content-stale", "review context does not match current content", recorded=expected_content, actual=actual_content)
    if actual_preview and expected_preview != actual_preview:
        add(errors, "review-preview-stale", "review context does not match current preview", recorded=expected_preview, actual=actual_preview)
    if str(manifest.get("content_sha256", "")).upper() != actual_content:
        add(errors, "manifest-content-stale", "review manifest does not match current content")
    if actual_preview and str(manifest.get("preview_sha256", "")).upper() != actual_preview:
        add(errors, "manifest-preview-stale", "review manifest does not match current preview")

    reviews = manifest.get("reviews")
    if not isinstance(reviews, list):
        add(errors, "reviews", "review manifest reviews must be a list")
        return
    roles = [str(item.get("role")) for item in reviews if isinstance(item, dict)]
    duplicate_roles = sorted(name for name, count in Counter(roles).items() if name and count > 1)
    if duplicate_roles:
        add(errors, "review-role-duplicate", "review roles must be unique", roles=duplicate_roles)
    by_role = {str(item.get("role")): item for item in reviews if isinstance(item, dict)}
    missing_roles = sorted(REQUIRED_REVIEW_ROLES - set(by_role))
    if missing_roles:
        add(errors, "review-roles", "review manifest is missing required roles", roles=missing_roles)
    evidence_paths: list[str] = []
    reviewers: list[str] = []
    contract = load_json(root / "project" / "content" / "content-contract.json", errors)
    part_titles = [str(item.get("title", "")) for item in contract.get("parts", []) if isinstance(item, dict)]
    proof_ids = [str(item.get("id", "")) for item in contract.get("proofs", []) if isinstance(item, dict)]
    for role in sorted(REQUIRED_REVIEW_ROLES):
        item = by_role.get(role)
        if not item:
            continue
        if item.get("status") != "pass":
            add(errors, "review-status", "independent review has not passed", role=role, status=item.get("status"))
        evidence_value = str(item.get("evidence", "") or "")
        reviewer = str(item.get("reviewer", "") or "").strip()
        reviewers.append(reviewer.lower())
        if len(reviewer) < 3 or PLACEHOLDER.search(reviewer):
            add(errors, "reviewer", "each review needs a concrete independent reviewer id", role=role, reviewer=reviewer)
        evidence = Path(evidence_value)
        if evidence_value and not evidence.is_absolute():
            evidence = root / evidence
        evidence_paths.append(str(evidence.resolve()).lower() if evidence_value else "")
        if not evidence_value or not evidence.is_file():
            add(errors, "review-evidence", "review evidence file is missing", role=role, path=str(evidence))
            continue
        text = evidence.read_text(encoding="utf-8-sig", errors="replace")
        if len(text.strip()) < 260 or PLACEHOLDER.search(text):
            add(errors, "review-placeholder", "review evidence is too short or still a template", role=role, path=str(evidence), characters=len(text.strip()))
        if str(item.get("evidence_sha256", "")).upper() != digest_file(evidence):
            add(errors, "review-evidence-stale", "manifest evidence hash does not match the current review file", role=role, path=str(evidence))
        required_names = part_titles if role in {"copy", "first_viewer"} else proof_ids
        missing_names = [name for name in required_names if name and name not in text]
        if missing_names:
            add(errors, "review-coverage", "role evidence does not cover every required part/proof", role=role, missing=missing_names)
        if role == "first_viewer":
            if "第一次" not in text or ("倒回" not in text and "回看" not in text):
                add(errors, "first-view-time", "first-viewer evidence must record the first rewind point or explicitly state none", path=str(evidence))
            if "盲转录" not in text and "抄写" not in text:
                add(errors, "first-view-proof", "first-viewer evidence must transcribe the core syntax from the preview", path=str(evidence))
        if role == "visual_geometry" and "proof" not in text.lower() and "证明帧" not in text:
            add(errors, "geometry-proof", "visual review evidence must inspect every core proof frame", path=str(evidence))
        if role in {"first_viewer", "visual_geometry"} and not TIMECODE.search(text):
            add(errors, "review-timecodes", "review evidence must contain concrete video timecodes", role=role, path=str(evidence))
    if len(set(evidence_paths)) != len(evidence_paths):
        add(errors, "review-evidence-shared", "independent roles must use distinct evidence files")
    if "" in reviewers or len(set(reviewers)) != len(reviewers):
        add(errors, "reviewer-shared", "independent roles must use distinct reviewer ids", reviewers=reviewers)


def validate_release(root: Path, config: dict, errors: list[dict], warnings: list[dict]) -> None:
    output = config.get("output", {}) if isinstance(config.get("output"), dict) else {}
    final_value = str(output.get("final", "") or "")
    final = Path(final_value)
    if final_value and not final.is_absolute():
        final = root / final
    if not final_value or not final.is_file():
        add(errors, "final-missing", "final release file is missing", path=str(final))

    current_content = canonical_content_digest(root)
    for name, kind in (("QA_LAYOUT_REPORT.json", "layout"), ("QA_MOTION_REPORT.json", "motion")):
        path = root / "project" / "docs" / name
        value = load_json(path, errors)
        if not value:
            continue
        if str(value.get("content_sha256", "")).upper() != current_content:
            add(errors, f"{kind}-report-stale", f"{kind} QA report does not match the current material digest", path=str(path))
        if value.get("errors") or value.get("warnings"):
            add(errors, f"{kind}-open-findings", f"{kind} QA report contains unresolved findings", errors=value.get("errors"), warnings=value.get("warnings"), path=str(path))
        if kind == "layout" and not isinstance(value.get("sample_frames"), int):
            add(errors, "layout-schema", "layout QA report is not a generated machine-readable report", path=str(path))
        if kind == "layout" and value.get("safe_zone"):
            add(errors, "layout-safe-zone", "layout QA report contains unresolved subtitle-safe-zone findings", findings=value.get("safe_zone"), path=str(path))
        if kind == "motion":
            events = value.get("events")
            if not isinstance(events, list) or not events or any(item.get("status") != "pass" for item in events if isinstance(item, dict)):
                add(errors, "motion-schema", "motion QA report must contain passed teaching events", path=str(path))

    report = root / "project" / "docs" / "QA_REPORT.json"
    value = load_json(report, errors)
    if value:
        if final.is_file() and str(value.get("sha256", "")).upper() != digest_file(final):
            add(errors, "final-report-hash", "final QA report does not match the current release SHA-256", path=str(report))
        try:
            report_media = Path(str(value.get("media", ""))).resolve()
        except (OSError, ValueError):
            report_media = Path()
        if final.is_file() and report_media != final.resolve():
            add(errors, "final-report-target", "final QA report targets a different media file", final=str(final), report_media=str(report_media))
        if value.get("errors") or value.get("warnings"):
            add(errors, "final-report-findings", "final media QA contains unresolved findings", report_errors=value.get("errors"), report_warnings=value.get("warnings"))
        decode = value.get("decode")
        if not isinstance(decode, dict) or decode.get("returncode") != 0:
            add(errors, "final-report-decode", "final media report lacks a successful full decode")
        streams = value.get("streams")
        if not isinstance(streams, list) or not streams:
            add(errors, "final-report-streams", "final media report lacks stream evidence")
        fade_windows = value.get("fade_windows")
        if not isinstance(fade_windows, list) or len(fade_windows) < 4:
            add(errors, "final-report-fade", "final media report lacks complete fade-window evidence")

    proof_dir = root / "renders" / "final-proofs"
    if not proof_dir.is_dir() or not any(proof_dir.glob("*.png")):
        add(errors, "final-proofs", "final MP4 proof frames are missing", path=str(proof_dir))
    proof_manifest = proof_dir / "manifest.json"
    if final.is_file() and proof_manifest.is_file():
        try:
            value = json.loads(proof_manifest.read_text(encoding="utf-8-sig"))
            if str(value.get("video_sha256", "")).upper() != digest_file(final):
                add(errors, "final-proofs-stale", "proof frames were not extracted from the current final MP4")
            contract = json.loads((root / "project" / "content" / "content-contract.json").read_text(encoding="utf-8-sig"))
            expected_ids = {str(item.get("id")) for item in contract.get("proofs", []) if isinstance(item, dict)}
            actual_ids = {str(item.get("id")) for item in value.get("proofs", []) if isinstance(item, dict)}
            if expected_ids != actual_ids:
                add(errors, "final-proofs-incomplete", "final proof manifest does not match the content contract", expected=sorted(expected_ids), actual=sorted(actual_ids))
            for item in value.get("proofs", []):
                image_value = str(item.get("image", "") or "")
                image_path = Path(image_value)
                if image_value and not image_path.is_absolute():
                    image_path = root / image_path
                if not image_value or not image_path.is_file() or str(item.get("image_sha256", "")).upper() != (digest_file(image_path) if image_path.is_file() else ""):
                    add(errors, "final-proof-image", "proof image is missing or stale", proof=item.get("id"), path=str(image_path))
        except (json.JSONDecodeError, OSError, KeyError) as exc:
            add(errors, "final-proofs", "cannot validate final proof manifest", error=str(exc), path=str(proof_manifest))
    elif proof_dir.is_dir():
        add(errors, "final-proofs", "final proof manifest is missing", path=str(proof_manifest))
    final_proof_review = root / "project" / "reviews" / "final-proofs.json"
    if not final_proof_review.is_file():
        add(errors, "final-proof-review", "final proof blind-transcription review is missing", path=str(final_proof_review))
    else:
        try:
            review_value = json.loads(final_proof_review.read_text(encoding="utf-8-sig"))
            contract_for_review = json.loads((root / "project" / "content" / "content-contract.json").read_text(encoding="utf-8-sig"))
            manifest_value = json.loads(proof_manifest.read_text(encoding="utf-8-sig"))
            if final.is_file() and str(review_value.get("video_sha256", "")).upper() != digest_file(final):
                add(errors, "final-proof-review-stale", "final proof review does not match the current final MP4")
            reviewer = str(review_value.get("reviewer", "")).strip()
            if len(reviewer) < 3 or PLACEHOLDER.search(reviewer):
                add(errors, "final-proof-reviewer", "final proof review needs a concrete blind reviewer id")
            expected_by_id = {str(item.get("id")): item for item in contract_for_review.get("proofs", []) if isinstance(item, dict)}
            image_by_id = {str(item.get("id")): item for item in manifest_value.get("proofs", []) if isinstance(item, dict)}
            actual_by_id = {str(item.get("id")): item for item in review_value.get("proofs", []) if isinstance(item, dict)}
            if set(actual_by_id) != set(expected_by_id):
                add(errors, "final-proof-review-incomplete", "final proof review ids must exactly match the contract", expected=sorted(expected_by_id), actual=sorted(actual_by_id))
            for proof_id, expected_proof in expected_by_id.items():
                item = actual_by_id.get(proof_id, {})
                image_item = image_by_id.get(proof_id, {})
                if item.get("status") != "pass":
                    add(errors, "final-proof-status", "final proof review has not passed", proof=proof_id, status=item.get("status"))
                if abs(float(item.get("time", -999)) - float(expected_proof.get("time"))) > 0.001:
                    add(errors, "final-proof-time", "final proof review time differs from contract", proof=proof_id)
                expected_visible = list(dict.fromkeys(str(value) for value in [*expected_proof.get("expected_visible", []), *expected_proof.get("expected_code", [])]))
                if [str(value) for value in item.get("expected_visible", [])] != expected_visible:
                    add(errors, "final-proof-expected", "final proof review expected text differs from contract", proof=proof_id)
                if [str(value) for value in item.get("transcribed", [])] != expected_visible:
                    add(errors, "final-proof-transcription", "blind transcription must exactly reproduce every expected token/relation", proof=proof_id)
                if str(item.get("image_sha256", "")).upper() != str(image_item.get("image_sha256", "")).upper():
                    add(errors, "final-proof-image", "final proof review references a stale proof image", proof=proof_id)
        except (json.JSONDecodeError, OSError, TypeError, ValueError, KeyError) as exc:
            add(errors, "final-proof-review", "cannot validate structured final proof review", error=str(exc), path=str(final_proof_review))

    cover_value = str(output.get("cover", "") or "")
    cover = Path(cover_value)
    if cover_value and not cover.is_absolute():
        cover = root / cover
    if not cover_value or not cover.is_file():
        add(errors, "cover-missing", "cover PNG is missing", path=str(cover))
    small = root / "renders" / "cover-320.png"
    if not small.is_file():
        add(errors, "cover-small", "phone-size cover preview is missing", path=str(small))
    cover_spec = root / "project" / "content" / "cover.json"
    if not cover_spec.is_file():
        add(errors, "cover-spec", "cover content spec is missing", path=str(cover_spec))
    else:
        try:
            value = json.loads(cover_spec.read_text(encoding="utf-8-sig"))
            if value.get("status") != "locked":
                add(errors, "cover-lock", "cover content spec must be locked", status=value.get("status"))
            for key in ("title", "subtitle"):
                text = str(value.get(key, "")).strip()
                if len(text) < 2 or PLACEHOLDER.search(text):
                    add(errors, "cover-copy", "cover title/subtitle is empty or placeholder", field=key, value=text)
                for name, pattern in CREATOR_PATTERNS.items():
                    if pattern.search(text):
                        add(errors, name, "production instruction leaked into cover copy", field=key, text=text)
            if value.get("reuse_video_directory") is not False or "directory" in value:
                add(errors, "cover-directory", "cover must not reuse the video directory or internal scene list")
            expected_cover_size = (int(value.get("width", 0)), int(value.get("height", 0)))
            expected_small_size = (int(value.get("thumbnail_width", 0)), int(value.get("thumbnail_height", 0)))
            if cover.is_file() and png_dimensions(cover) != expected_cover_size:
                add(errors, "cover-dimensions", "cover PNG dimensions differ from cover spec", actual=png_dimensions(cover), expected=expected_cover_size)
            if small.is_file() and png_dimensions(small) != expected_small_size:
                add(errors, "cover-small-dimensions", "thumbnail PNG dimensions differ from cover spec", actual=png_dimensions(small), expected=expected_small_size)
        except (json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
            add(errors, "cover-spec", "cannot parse cover content spec", error=str(exc), path=str(cover_spec))
    cover_review = root / "project" / "reviews" / "cover.json"
    if not cover_review.is_file():
        add(errors, "cover-review", "cover blind-review evidence is missing", path=str(cover_review))
    else:
        try:
            review_value = json.loads(cover_review.read_text(encoding="utf-8-sig"))
            if cover.is_file() and str(review_value.get("cover_sha256", "")).upper() != digest_file(cover):
                add(errors, "cover-review-stale", "cover review does not match the current cover")
            if small.is_file() and str(review_value.get("thumbnail_sha256", "")).upper() != digest_file(small):
                add(errors, "cover-review-stale", "cover review does not match the current phone thumbnail")
            reviewer = str(review_value.get("reviewer", "")).strip()
            if len(reviewer) < 3 or PLACEHOLDER.search(reviewer):
                add(errors, "cover-reviewer", "cover review needs a concrete blind reviewer id")
            for key in ("first_impression", "topic_understood"):
                text = str(review_value.get(key, "")).strip()
                if len(text) < 4 or PLACEHOLDER.search(text):
                    add(errors, "cover-review", "cover blind review lacks a concrete result", field=key)
            if review_value.get("looks_like_course_page") is not False:
                add(errors, "cover-course", "cover blind review still identifies course-page styling")
            if review_value.get("status") != "pass":
                add(errors, "cover-review-status", "cover blind review has not passed", status=review_value.get("status"))
        except (json.JSONDecodeError, OSError) as exc:
            add(errors, "cover-review", "cannot parse structured cover review", error=str(exc), path=str(cover_review))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--stage", choices=("content", "final", "release"), default="content")
    parser.add_argument("--warnings-as-errors", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    root = args.project_root.resolve()
    errors: list[dict] = []
    warnings: list[dict] = []
    config = load_json(root / "project" / "config.json", errors)
    timeline = load_json(root / "project" / "content" / "timeline.json", errors)
    contract = load_json(root / "project" / "content" / "content-contract.json", errors)
    if timeline:
        validate_surfaces(root, timeline, errors, warnings)
        validate_docs(root, timeline, errors, warnings)
    if contract and timeline:
        validate_contract(contract, timeline, errors, warnings)
        validate_proof_example_links(root, contract, errors)
    if contract:
        validate_code_language(root, contract, timeline, errors, warnings)
    if contract and config:
        aliases = {"cs": "csharp", "c++": "cpp"}
        contract_language = aliases.get(str(contract.get("code_language", "")).lower(), str(contract.get("code_language", "")).lower())
        raw_config_language = str(config.get("code", {}).get("language", "")).lower() if isinstance(config.get("code"), dict) else ""
        config_language = aliases.get(raw_config_language, raw_config_language)
        if not config_language or config_language != contract_language:
            add(errors, "code-language-mismatch", "config code.language must match content contract code_language", contract=contract_language, config=config_language or None)
        video = config.get("video", {}) if isinstance(config.get("video"), dict) else {}
        if (int(video.get("width", 0) or 0), int(video.get("height", 0) or 0)) != (1920, 1080):
            add(errors, "canvas-contract", "the bundled coordinate renderer is locked to 1920x1080; adapt the renderer and QA together for another canvas", actual=[video.get("width"), video.get("height")])
        if float(video.get("fps", 0) or 0) != 25.0:
            add(errors, "fps-contract", "the bundled renderer/review contract expects 25 fps", actual=video.get("fps"))
        subtitles = config.get("subtitles", {}) if isinstance(config.get("subtitles"), dict) else {}
        center_y = float(subtitles.get("center_y", -1) or -1)
        if not 885 <= center_y <= 1000:
            add(errors, "subtitle-position", "subtitle center must remain inside the 1080p subtitle-safe region", actual=center_y)
        try:
            fade_seconds = float(config.get("audio", {}).get("fade_seconds"))
        except (TypeError, ValueError):
            fade_seconds = -1.0
        if not 3.0 <= fade_seconds <= 5.0:
            add(errors, "fade-contract", "final BGM fade must be between 3 and 5 seconds", actual=config.get("audio", {}).get("fade_seconds"))
    if args.stage in {"final", "release"}:
        validate_review(root, errors, warnings)
    if args.stage == "release" and config:
        validate_release(root, config, errors, warnings)

    report = {
        "project": str(root),
        "stage": args.stage,
        "content_sha256": digest_content(project_content_files(root), root),
        "errors": errors,
        "warnings": warnings,
    }
    value = json.dumps(report, ensure_ascii=False, indent=2)
    print(value)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(value + "\n", encoding="utf-8")
    return 1 if errors or (warnings and args.warnings_as_errors) else 0


if __name__ == "__main__":
    raise SystemExit(main())
