from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

import scenes
from project_digest import content_digest
from render_animation import load, render_frame
from render_common import fit_one_line, make_context, rgba


ROOT = Path(__file__).resolve().parents[2]


def content_pixels(image: Image.Image, top: int, bottom: int, background: tuple[int, int, int]) -> int:
    crop = image.convert("RGB").crop((0, top, image.width, bottom))
    return sum(
        1
        for red, green, blue in crop.getdata()
        if max(abs(red - background[0]), abs(green - background[1]), abs(blue - background[2])) >= 8
    )


def render_base(config: dict, timeline: dict, timestamp: float) -> Image.Image:
    image, _ = render_base_trace(config, timeline, timestamp)
    return image


def render_base_trace(config: dict, timeline: dict, timestamp: float) -> tuple[Image.Image, list[dict]]:
    scene = next(item for item in timeline["scenes"] if float(item["start"]) <= timestamp < float(item["end"]))
    scene = dict(scene)
    scene["all_scenes"] = timeline["scenes"]
    ctx = make_context(config, timestamp, scene)
    scenes.render_scene(ctx)
    background = rgba(config["video"].get("background", "#000000"))
    image = Image.alpha_composite(Image.new("RGBA", ctx.image.size, background), ctx.image).convert("RGB")
    return image, list(ctx.trace)


def token_pixel_visibility(image: Image.Image, event: dict, token: str) -> tuple[float, float]:
    value = str(event.get("value", ""))
    index = value.find(token)
    font = event.get("_font")
    xy = event.get("_xy")
    anchor = str(event.get("_anchor", "la"))
    if index < 0 or font is None or not isinstance(xy, (tuple, list)) or len(xy) != 2:
        return 0.0, 0.0
    mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(mask)
    total_width = draw.textlength(value, font=font)
    horizontal = anchor[0] if anchor else "l"
    left = float(xy[0])
    if horizontal == "m":
        left -= total_width / 2.0
    elif horizontal == "r":
        left -= total_width
    vertical = anchor[1] if len(anchor) > 1 else "a"
    segments = event.get("_segments") if event.get("type") == "code" else None
    if isinstance(segments, list) and "".join(str(segment) for segment in segments) == value:
        token_end = index + len(token)
        cursor = 0
        segment_x = left
        for raw_segment in segments:
            segment = str(raw_segment)
            segment_end = cursor + len(segment)
            overlap_start = max(index, cursor)
            overlap_end = min(token_end, segment_end)
            if overlap_start < overlap_end:
                prefix = segment[: overlap_start - cursor]
                visible_part = segment[overlap_start - cursor : overlap_end - cursor]
                draw.text((segment_x + draw.textlength(prefix, font=font), float(xy[1])), visible_part, font=font, fill=255, anchor="l" + vertical, stroke_width=int(event.get("_stroke_width", 0)), stroke_fill=255)
            segment_x += draw.textlength(segment, font=font)
            cursor = segment_end
    else:
        token_x = left + draw.textlength(value[:index], font=font)
        draw.text((token_x, float(xy[1])), token, font=font, fill=255, anchor="l" + vertical, stroke_width=int(event.get("_stroke_width", 0)), stroke_fill=255)
    box = mask.getbbox()
    if box is None:
        return 0.0, 0.0
    box = (max(0, box[0] - 6), max(0, box[1] - 6), min(image.width, box[2] + 6), min(image.height, box[3] + 6))
    mask_crop = mask.crop(box)
    mask_values = list(mask_crop.getdata())
    final_values = list(image.convert("L").crop(box).getdata())
    active = [index for index, value in enumerate(mask_values) if value >= 32]
    if not active:
        return 0.0, 0.0
    visible = sum(1 for index in active if final_values[index] >= max(3.0, mask_values[index] * 0.20))
    expanded_values = list(mask_crop.filter(ImageFilter.MaxFilter(9)).getdata())
    ring = [index for index, value in enumerate(expanded_values) if value >= 32 and mask_values[index] < 32]
    inside_mean = sum(final_values[index] for index in active) / len(active)
    ring_mean = sum(final_values[index] for index in ring) / len(ring) if ring else 0.0
    return visible / len(active), abs(inside_mean - ring_mean)


def text_trace_overlaps(trace: list[dict]) -> list[tuple[dict, dict, float]]:
    items = [item for item in trace if item.get("type") in {"text", "code"} and float(item.get("alpha", 0.0)) >= 0.42 and str(item.get("value", "")).strip()]
    overlaps: list[tuple[dict, dict, float]] = []
    for index, left in enumerate(items):
        lx1, ly1, lx2, ly2 = (float(value) for value in left["bbox"])
        left_area = max(1.0, (lx2 - lx1) * (ly2 - ly1))
        for right in items[index + 1 :]:
            rx1, ry1, rx2, ry2 = (float(value) for value in right["bbox"])
            width = min(lx2, rx2) - max(lx1, rx1)
            height = min(ly2, ry2) - max(ly1, ry1)
            if width <= 4.0 or height <= 4.0:
                continue
            right_area = max(1.0, (rx2 - rx1) * (ry2 - ry1))
            ratio = width * height / min(left_area, right_area)
            min_height = max(1.0, min(ly2 - ly1, ry2 - ry1))
            if ratio >= 0.08 and height / min_height >= 0.18:
                overlaps.append((left, right, ratio))
    return overlaps


def main() -> int:
    config, timeline = load()
    contract_path = ROOT / "project" / "content" / "content-contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8")) if contract_path.is_file() else {}
    errors: list[str] = []
    safe: list[str] = []
    sizes: list[int] = []
    first_scene = dict(timeline["scenes"][0])
    first_scene["all_scenes"] = timeline["scenes"]
    dummy = make_context(config, 0.0, first_scene)
    for cue in timeline["cues"]:
        try:
            _, size = fit_one_line(dummy, str(cue["text"]))
            sizes.append(size)
        except Exception as exc:
            errors.append(f"cue {cue.get('id')} cannot fit one line: {exc}")

    timestamps: dict[float, str] = {}
    for scene in timeline["scenes"]:
        start, end = float(scene["start"]), float(scene["end"])
        for ratio in (0.08, 0.25, 0.50, 0.75, 0.92):
            timestamp = min(end - 1.0 / float(config["video"]["fps"]), start + (end - start) * ratio)
            timestamps[round(timestamp, 4)] = f"scene {scene['id']} {ratio:.2f}"
    for cue in timeline["cues"]:
        start, end = float(cue["start"]), float(cue["end"])
        frame = 1.0 / float(config["video"]["fps"])
        for timestamp, label in (
            (start + frame, "start"),
            ((start + end) / 2.0, "middle"),
            (max(start + frame, end - frame), "end"),
        ):
            timestamps[round(timestamp, 4)] = f"cue {cue.get('id')} {label}"
    for proof in contract.get("proofs", []):
        timestamps[round(float(proof["time"]), 4)] = f"proof {proof.get('id')}"
        stable = max(0.8, float(proof.get("min_stable_seconds", 0.8)))
        proof_times = [float(proof["time"]) - stable / 2.0, float(proof["time"]), float(proof["time"]) + stable / 2.0]
        for proof_time in proof_times:
            try:
                proof_image, trace = render_base_trace(config, timeline, proof_time)
            except Exception as exc:
                errors.append(f"proof {proof.get('id')} @ {proof_time:.3f}s cannot render: {exc}")
                continue
            for token in proof.get("expected_visible", []):
                matches = [
                    item
                    for item in trace
                    if str(token) in str(item.get("value", ""))
                    and float(item.get("alpha", 0)) >= 0.55
                    and item.get("type") in {"text", "code"}
                ]
                if not matches:
                    errors.append(f"proof {proof.get('id')} @ {proof_time:.3f}s does not draw visible token: {token}")
                    continue
                if not any(
                    float(item["bbox"][0]) >= 0
                    and float(item["bbox"][1]) >= 0
                    and float(item["bbox"][2]) <= int(config["video"]["width"])
                    and float(item["bbox"][3]) <= 825
                    for item in matches
                ):
                    errors.append(f"proof {proof.get('id')} @ {proof_time:.3f}s draws token outside the content-safe canvas: {token}")
                    continue
                visibility, contrast = max((token_pixel_visibility(proof_image, item, str(token)) for item in matches), default=(0.0, 0.0), key=lambda item: (item[0], item[1]))
                if visibility < 0.85 or contrast < 10.0:
                    errors.append(f"proof {proof.get('id')} @ {proof_time:.3f}s token is traced but occluded in final pixels: {token} (visibility={visibility:.3f}, contrast={contrast:.2f})")
            for token in proof.get("expected_code", []):
                matches = [
                    item
                    for item in trace
                    if str(token) in str(item.get("value", ""))
                    and float(item.get("alpha", 0)) >= 0.55
                    and item.get("type") == "code"
                ]
                if not matches:
                    errors.append(f"proof {proof.get('id')} @ {proof_time:.3f}s does not draw required code through draw_code: {token}")
                    continue
                visibility, contrast = max((token_pixel_visibility(proof_image, item, str(token)) for item in matches), default=(0.0, 0.0), key=lambda item: (item[0], item[1]))
                if visibility < 0.85 or contrast < 10.0:
                    errors.append(f"proof {proof.get('id')} @ {proof_time:.3f}s required code is occluded: {token} (visibility={visibility:.3f}, contrast={contrast:.2f})")
            palette = {
                "keyword": [86, 156, 214],
                "type": [78, 201, 176],
                "method": [220, 220, 170],
                "number": [179, 196, 147],
                "string": [214, 157, 133],
                "comment": [87, 166, 74],
            }
            for check in proof.get("color_checks", []):
                token = str(check.get("token", ""))
                expected_color = palette.get(str(check.get("kind", "")))
                code_events = [item for item in trace if item.get("type") == "code" and float(item.get("alpha", 0)) >= 0.55]
                passed = any(
                    any(str(segment[0]) == token and list(segment[1]) == expected_color for segment in item.get("style", []))
                    for item in code_events
                )
                if not passed:
                    errors.append(f"proof {proof.get('id')} @ {proof_time:.3f}s actual scene code color mismatch: {token} / {check.get('kind')}")
    for scene in timeline["scenes"]:
        for timestamp in scene.get("qa_times", []):
            timestamps[round(float(timestamp), 4)] = f"scene {scene.get('id')} risk"

    previews: list[Image.Image] = []
    labels: list[str] = []
    overlap_findings: list[str] = []
    for timestamp, reason in sorted(timestamps.items()):
        try:
            base, trace = render_base_trace(config, timeline, timestamp)
            background = rgba(config["video"].get("background", "#000000"))[:3]
            count = content_pixels(base, 825, 885, background)
            if count > 240:
                safe.append(f"{reason} @ {timestamp:.2f}s: {count} content pixels in y825..884")
            for left, right, ratio in text_trace_overlaps(trace):
                finding = f"{reason} @ {timestamp:.2f}s: text/code overlap {left.get('value')!r} vs {right.get('value')!r} (ratio={ratio:.3f})"
                if finding not in overlap_findings:
                    overlap_findings.append(finding)
            previews.append(render_frame(config, timeline, timestamp).resize((480, 270), Image.Resampling.LANCZOS))
            labels.append(f"{timestamp:06.2f}s {reason}")
        except Exception as exc:
            errors.append(f"{reason} @ {timestamp:.3f}s cannot render: {exc}")

    cols = 5
    rows = max(1, (len(previews) + cols - 1) // cols)
    sheet = Image.new("RGB", (cols * 480, rows * 300), (10, 11, 13))
    from PIL import ImageDraw

    draw = ImageDraw.Draw(sheet)
    for index, (preview, label) in enumerate(zip(previews, labels)):
        x, y = (index % cols) * 480, (index // cols) * 300
        sheet.paste(preview, (x, y))
        draw.text((x + 10, y + 276), label, fill=(180, 185, 190))
    output = ROOT / "renders" / "qa-layout-grid.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    errors.extend(overlap_findings)
    report = {
        "content_sha256": content_digest(ROOT),
        "scenes": len(timeline["scenes"]),
        "cues": len(timeline["cues"]),
        "subtitle_size_range": [min(sizes), max(sizes)] if sizes else None,
        "sample_frames": len(previews),
        "safe_zone": safe,
        "text_overlaps": overlap_findings,
        "errors": errors,
        "grid": str(output),
    }
    markdown = [
        "# 版式 QA",
        "",
        f"- 连续场景：{report['scenes']}",
        f"- 字幕：{report['cues']} 条，全部执行单行像素宽度检查",
        f"- 字幕字号范围：{report['subtitle_size_range']}",
        f"- 抽样帧：{report['sample_frames']}（含 cue 边界、proof 与风险时刻）",
        f"- 字幕安全区告警：{len(safe)}",
        f"- 结构/字体错误：{len(errors)}",
        "",
        "## 安全区告警",
        "",
        *(f"- {item}" for item in safe),
        *(["- 无"] if not safe else []),
        "",
        "## 错误",
        "",
        *(f"- {item}" for item in errors),
        *(["- 无"] if not errors else []),
        "",
        f"视觉总览：`{output}`",
    ]
    (ROOT / "project" / "docs" / "QA_LAYOUT_REPORT.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    (ROOT / "project" / "docs" / "QA_LAYOUT_REPORT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors or safe else 0


if __name__ == "__main__":
    raise SystemExit(main())
