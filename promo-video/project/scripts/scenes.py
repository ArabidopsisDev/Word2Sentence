from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from render_common import (
    BLACK,
    BLUE,
    CYAN,
    METHOD,
    RED,
    STRING,
    TYPE,
    WHITE,
    SceneContext,
    draw_arrow,
    draw_code,
    draw_line,
    draw_text,
    get_font,
    progress,
    rgba,
    smooth,
    with_alpha,
)


ROOT = Path(__file__).resolve().parents[2]
INK = rgba("#242522")
MUTED = rgba("#686A64")
GREEN = rgba("#2F6048")
GREEN_SOFT = rgba("#DDE9E1")
CREAM = rgba("#FFFDF9")
CANVAS = rgba("#F5F4F0")
BORDER = rgba("#D9D8D2")
BLUE_DARK = rgba("#356AA0")
BLUE_SOFT = rgba("#E4EEF8")
RED_DARK = rgba("#B83C37")
RED_SOFT = rgba("#F8E5E3")
GREEN_DARK = rgba("#237A4B")
GREEN_FEEDBACK = rgba("#E1F2E8")


def _ease(ctx: SceneContext, delay: float = 0.0, duration: float = 0.45) -> float:
    return smooth(progress(ctx.scene_t, delay, duration))


def _use_design_time(ctx: SceneContext, fallback_duration: float) -> None:
    scene_duration = float(ctx.scene["end"]) - float(ctx.scene["start"])
    design_duration = float(ctx.scene.get("design_duration", fallback_duration))
    if scene_duration > 0:
        ctx.scene_t *= design_duration / scene_duration


def _lerp(start: float, end: float, value: float) -> float:
    return start + (end - start) * value


@lru_cache(maxsize=32)
def _asset(path: str) -> Image.Image:
    value = Path(path)
    resolved = value if value.is_absolute() else ROOT / value
    return Image.open(resolved).convert("RGBA")


def _panel(
    ctx: SceneContext,
    box: tuple[float, float, float, float],
    *,
    fill=CREAM,
    outline=BORDER,
    radius: int = 18,
    alpha: float = 1.0,
    trace_id: str | None = None,
) -> None:
    if alpha <= 0:
        return
    ctx.trace.append({"type": "panel", "value": "", "bbox": list(box), "alpha": alpha, "trace_id": trace_id, "style": list(fill[:3])})
    ctx.draw.rounded_rectangle(box, radius=radius, fill=with_alpha(fill, alpha), outline=with_alpha(outline, alpha), width=2)


def _paste_image(
    ctx: SceneContext,
    path: str,
    box: tuple[int, int, int, int],
    *,
    crop: tuple[int, int, int, int] | None = None,
    alpha: float = 1.0,
    radius: int = 16,
    trace_id: str | None = None,
) -> None:
    if alpha <= 0:
        return
    x1, y1, x2, y2 = box
    width, height = max(1, x2 - x1), max(1, y2 - y1)
    source = _asset(path)
    if crop is not None:
        source = source.crop(crop)
    fitted = ImageOps.fit(source, (width, height), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width - 1, height - 1), radius=radius, fill=round(255 * alpha))
    shadow = (x1 + 10, y1 + 14, x2 + 10, y2 + 14)
    ctx.draw.rounded_rectangle(shadow, radius=radius, fill=with_alpha(rgba("#242522"), 0.10 * alpha))
    ctx.image.paste(fitted, (x1, y1), mask)
    ctx.draw.rounded_rectangle(box, radius=radius, outline=with_alpha(BORDER, alpha), width=2)
    ctx.trace.append({"type": "image", "value": path, "bbox": list(box), "alpha": alpha, "trace_id": trace_id, "style": [255, 255, 255]})


def _chapter(ctx: SceneContext, alpha: float = 1.0) -> None:
    scene = ctx.scene
    index, total = int(scene["chapter_index"]), int(scene["chapter_total"])
    draw_text(ctx, (78, 72), f"{index:02d} / {total:02d}", size=25, kind="code", fill=GREEN, alpha=alpha, anchor="lm")
    draw_line(ctx, (184, 72), (244, 72), color=GREEN, width=2, alpha=0.7 * alpha)
    draw_text(ctx, (264, 72), str(scene["chapter_title"]), size=28, kind="sans_bold", fill=MUTED, alpha=alpha, anchor="lm")


def _code_panel(
    ctx: SceneContext,
    box: tuple[int, int, int, int],
    lines: list[str],
    *,
    alpha: float,
    trace_ids: list[str] | None = None,
    explicit_kinds: list[str | None] | None = None,
    token_kinds: list[dict] | None = None,
) -> None:
    if alpha <= 0:
        return
    _panel(ctx, box, fill=rgba("#202321"), outline=rgba("#39403C"), radius=12, alpha=alpha)
    x1, y1, x2, y2 = box
    panel_width = x2 - x1 - 44
    size = 24 if x2 - x1 > 700 else 20
    line_height = 38
    for index, line in enumerate(lines):
        line_size = size
        while line_size > 14 and ctx.draw.textlength(line, font=get_font(ctx.config, "code", line_size)) > panel_width:
            line_size -= 1
        spans = None
        kind = explicit_kinds[index] if explicit_kinds and index < len(explicit_kinds) else None
        if kind:
            spans = [{"start": 0, "end": len(line), "kind": kind}]
        elif token_kinds:
            spans = []
            for item in token_kinds:
                token = str(item["token"])
                start = line.find(token)
                if start >= 0:
                    spans.append({"start": start, "end": start + len(token), "kind": str(item["kind"])})
            spans = spans or None
        trace_id = trace_ids[index] if trace_ids and index < len(trace_ids) else None
        draw_code(ctx, line, (x1 + 22, y1 + 22 + index * line_height), size=line_size, alpha=alpha, spans=spans, trace_id=trace_id)


def _tag(ctx: SceneContext, xy: tuple[float, float], value: str, *, alpha: float, active: bool = False, trace_id: str | None = None) -> None:
    font = get_font(ctx.config, "sans_bold" if active else "sans", 24)
    width = 38 + ctx.draw.textlength(value, font=font)
    box = (xy[0], xy[1], xy[0] + width, xy[1] + 52)
    _panel(ctx, box, fill=GREEN_SOFT if active else CREAM, outline=GREEN if active else BORDER, radius=12, alpha=alpha, trace_id=trace_id)
    draw_text(ctx, (xy[0] + 17, xy[1] + 27), value, size=24, kind="sans_bold" if active else "sans", fill=GREEN if active else INK, alpha=alpha, anchor="lm")


def _draw_segments(ctx: SceneContext, segments: list[dict], xy: tuple[int, int], alpha: float, reveal: float) -> None:
    x, y = xy
    _panel(ctx, (x - 22, y - 20, x + 1270, y + 64), fill=rgba("#F6F5F1"), outline=rgba("#F6F5F1"), radius=10, alpha=alpha)
    palette = {
        "excellent": (GREEN_DARK, GREEN_FEEDBACK),
        "error": (RED_DARK, RED_SOFT),
        "acceptable": (BLUE_DARK, BLUE_SOFT),
    }
    cursor = float(x)
    for index, segment in enumerate(segments):
        local = smooth(progress(reveal, index / max(1, len(segments)), 0.32))
        if local <= 0:
            continue
        text = str(segment["text"])
        foreground, background = palette.get(str(segment["rating"]), (INK, CREAM))
        measure_font = get_font(ctx.config, "sans", 34)
        width = ctx.draw.textlength(text, font=measure_font)
        ctx.draw.rectangle((cursor, y - 6, cursor + width, y + 42), fill=with_alpha(background, alpha * local))
        draw_text(ctx, (cursor, y), text, size=34, kind="sans", fill=foreground, alpha=alpha * local, trace_id="feedback-segments")
        cursor += width


def open_source_intro(ctx: SceneContext, visual: dict) -> None:
    _use_design_time(ctx, 8.5)
    alpha = _ease(ctx)
    app_alpha = alpha * _ease(ctx, 0.25, 0.65)
    app_x = round(_lerp(760, 690, _ease(ctx, 0.25, 0.8)))
    _paste_image(ctx, str(visual["app_image"]), (app_x, 112, 1800, 805), alpha=app_alpha, radius=22, trace_id="about-window")
    draw_text(ctx, (120, 138), str(visual["headline"]), size=58, kind="sans_bold", fill=INK, alpha=alpha)
    draw_text(ctx, (122, 212), str(visual["detail"]), size=28, kind="sans", fill=GREEN, alpha=alpha)
    draw_text(ctx, (122, 285), str(visual["problem_hint"]), size=30, kind="sans_bold", fill=INK, alpha=alpha * _ease(ctx, 2.4, 0.5))
    directory = list(visual["directory"])
    for index, item in enumerate(directory):
        item_alpha = alpha * _ease(ctx, 4.1 + index * 0.38, 0.4)
        y = 430 + index * 64
        draw_text(ctx, (125, y), f"{index + 1:02d}", size=20, kind="code", fill=GREEN, alpha=item_alpha, anchor="lm")
        draw_line(ctx, (172, y), (210, y), color=GREEN, width=2, alpha=0.55 * item_alpha)
        draw_text(ctx, (228, y), str(item), size=25, kind="sans_bold", fill=INK, alpha=item_alpha, anchor="lm")


def word_gap(ctx: SceneContext, visual: dict) -> None:
    _use_design_time(ctx, 12.0)
    alpha = _ease(ctx)
    _chapter(ctx, alpha)
    full = 1.0 - _ease(ctx, 1.35, 0.55)
    _paste_image(ctx, str(visual["app_image"]), (260, 118, 1660, 800), alpha=alpha * full, radius=18, trace_id="library-window")
    detail = _ease(ctx, 1.45, 0.55)
    _paste_image(ctx, str(visual["app_image"]), (105, 200, 970, 765), crop=(320, 250, 1520, 860), alpha=alpha * detail, radius=16, trace_id="library-window")
    _panel(ctx, (1040, 196, 1785, 718), fill=CREAM, outline=BORDER, radius=18, alpha=alpha * detail)
    draw_text(ctx, (1100, 270), str(visual["headline"]), size=68, kind="sans_bold", fill=GREEN, alpha=alpha * detail, trace_id="word-distract")
    draw_text(ctx, (1102, 352), str(visual["meaning"]), size=30, kind="sans", fill=MUTED, alpha=alpha * detail)
    gap_alpha = alpha * _ease(ctx, 2.7, 0.45)
    draw_text(ctx, (1102, 458), str(visual["gap_label"]), size=24, kind="sans_bold", fill=MUTED, alpha=gap_alpha)
    draw_line(ctx, (1102, 510), (1698, 510), color=BORDER, width=3, alpha=gap_alpha, trace_id="collocation-gap")
    cursor_alpha = gap_alpha * (0.35 + 0.65 * (1 if int(ctx.scene_t * 2) % 2 == 0 else 0))
    draw_line(ctx, (1110, 482), (1110, 516), color=GREEN, width=3, alpha=cursor_alpha)
    value_alpha = alpha * _ease(ctx, 4.0, 0.55)
    draw_text(ctx, (1102, 560), str(visual["gap_value"]), size=38, kind="sans_bold", fill=INK, alpha=value_alpha, trace_id="collocation-answer")
    _tag(ctx, (1102, 630), str(visual["screen_text"][0]), alpha=alpha * _ease(ctx, 6.7, 0.45), active=False, trace_id="word-summary")
    _tag(ctx, (1400, 630), str(visual["screen_text"][1]), alpha=alpha * _ease(ctx, 9.5, 0.45), active=True, trace_id="gap-summary")
    _code_panel(ctx, (1130, 112, 1785, 170), list(visual["code"]), alpha=0.82 * alpha * _ease(ctx, 9.2, 0.45), trace_ids=["license-code"], token_kinds=[{"token": "AGPL-3.0-only", "kind": "string"}])


def sentence_flow(ctx: SceneContext, visual: dict) -> None:
    _use_design_time(ctx, 15.5)
    alpha = _ease(ctx)
    _chapter(ctx, alpha)
    labels = list(visual["flow"])
    for index, label in enumerate(labels):
        _tag(ctx, (710 + index * 250, 106), str(label), alpha=alpha * _ease(ctx, 0.25 + index * 0.38, 0.4), active=index == min(2, int(ctx.scene_t // 4)), trace_id=["add-word-fragment", "scenario-fragment", "sentence-input"][index])
    source_alpha = alpha * (1.0 - _ease(ctx, 3.6, 0.6))
    _paste_image(ctx, str(visual["source_image"]), (105, 208, 930, 660), crop=(280, 135, 1510, 600), alpha=source_alpha, radius=16, trace_id="add-word-fragment")
    overlay_progress = _ease(ctx, 3.6, 0.7)
    practice_alpha = alpha * _ease(ctx, 2.7, 0.6) * (1.0 - 0.43 * overlay_progress)
    x1 = round(_lerp(980, 235, _ease(ctx, 3.6, 0.7)))
    x2 = round(_lerp(1810, 1690, _ease(ctx, 3.6, 0.7)))
    _paste_image(ctx, str(visual["app_image"]), (x1, 185, x2, 810), crop=(360, 120, 1460, 770), alpha=practice_alpha, radius=18, trace_id="scenario-fragment")
    arrow_alpha = alpha * _ease(ctx, 2.1, 0.5) * (1.0 - _ease(ctx, 5.0, 0.4))
    draw_arrow(ctx, (845, 430), (1020, 430), color=GREEN, width=4, alpha=arrow_alpha, trace_id="word-transfer")
    scenario_alpha = alpha * _ease(ctx, 5.7, 0.5)
    _panel(ctx, (330, 260, 1590, 430), fill=CREAM, outline=BORDER, radius=14, alpha=scenario_alpha, trace_id="scenario-fragment")
    draw_text(ctx, (372, 300), str(visual["screen_text"][0]), size=23, kind="sans_bold", fill=MUTED, alpha=scenario_alpha)
    draw_text(ctx, (372, 350), str(visual["scenario"]), size=30, kind="sans", fill=INK, alpha=scenario_alpha)
    input_alpha = alpha * _ease(ctx, 8.2, 0.45)
    _panel(ctx, (330, 470, 1590, 690), fill=CREAM, outline=BORDER, radius=14, alpha=input_alpha, trace_id="sentence-input")
    draw_text(ctx, (372, 512), str(visual["screen_text"][1]), size=28, kind="sans_bold", fill=INK, alpha=input_alpha)
    sentence = str(visual["sentence"])
    typed = sentence[: round(len(sentence) * smooth(progress(ctx.scene_t, 9.0, 3.0)))]
    draw_text(ctx, (372, 580), typed, size=32, kind="sans", fill=INK, alpha=input_alpha, trace_id="typed-sentence")
    _tag(ctx, (1390, 714), str(visual["screen_text"][2]), alpha=alpha * _ease(ctx, 10.3, 0.4), active=True, trace_id="submit-button")
    _tag(ctx, (360, 714), str(visual["hint_label"]), alpha=alpha * _ease(ctx, 10.8, 0.4), active=False, trace_id="hint-option")
    submit_line = smooth(progress(ctx.scene_t, 13.5, 0.55))
    draw_line(ctx, (1390, 778), (1390 + 190 * submit_line, 778), color=GREEN, width=4, alpha=alpha * submit_line, trace_id="submit-button")
    error_alpha = alpha * _ease(ctx, 14.0, 0.4)
    sentence_font = get_font(ctx.config, "sans", 32)
    token = str(visual["error_token"])
    token_index = sentence.find(token)
    if token_index >= 0:
        token_x = 372 + ctx.draw.textlength(sentence[:token_index], font=sentence_font)
        token_width = ctx.draw.textlength(token, font=sentence_font)
        draw_line(ctx, (token_x, 622), (token_x + token_width, 622), color=RED_DARK, width=5, alpha=error_alpha, trace_id="error-token")
    _code_panel(ctx, (105, 106, 650, 206), list(visual["code"]), alpha=alpha * _ease(ctx, 12.0, 0.45), trace_ids=["challenge-method", "evaluate-method"], explicit_kinds=["method", "method"])


def feedback_artifacts(ctx: SceneContext, visual: dict) -> None:
    _use_design_time(ctx, 20.0)
    alpha = _ease(ctx)
    _chapter(ctx, alpha)
    dialog_in = _ease(ctx, 15.5, 0.55)
    version_in = _ease(ctx, 5.2, 0.55)
    usage_in = _ease(ctx, 9.0, 0.55)
    screenshot_alpha = alpha * (1.0 - 0.45 * version_in) * (1.0 - 0.55 * dialog_in)
    _paste_image(ctx, str(visual["app_image"]), (180, 128, 1740, 800), crop=(320, 250, 1430, 990), alpha=screenshot_alpha, radius=18, trace_id="feedback-window")
    feedback_line = smooth(progress(ctx.scene_t, 0.5, 0.5))
    draw_line(ctx, (180, 116), (180 + 1560 * feedback_line, 116), color=GREEN, width=6, alpha=alpha * feedback_line, trace_id="feedback-window")
    segment_alpha = alpha * (1.0 - 0.72 * version_in) * (1.0 - 0.72 * dialog_in) * _ease(ctx, 1.5, 0.45)
    _draw_segments(ctx, list(visual["segments"]), (315, 322), segment_alpha, progress(ctx.scene_t, 1.6, 2.5))
    version_alpha = alpha * version_in * (1.0 - 0.62 * usage_in) * (1.0 - 0.72 * dialog_in)
    _panel(ctx, (300, 445, 1135, 722), fill=CREAM, outline=BORDER, radius=14, alpha=version_alpha, trace_id="sentence-versions")
    draw_text(ctx, (340, 490), str(visual["screen_text"][0]), size=22, kind="sans_bold", fill=MUTED, alpha=version_alpha)
    draw_text(ctx, (340, 535), str(visual["corrected"]), size=24, kind="sans", fill=INK, alpha=version_alpha)
    draw_text(ctx, (340, 605), str(visual["screen_text"][1]), size=22, kind="sans_bold", fill=MUTED, alpha=version_alpha)
    draw_text(ctx, (340, 652), str(visual["better"]), size=20, kind="sans", fill=INK, alpha=version_alpha)
    version_line = smooth(progress(ctx.scene_t, 8.0, 0.5))
    draw_line(ctx, (300, 730), (300 + 835 * version_line, 730), color=GREEN, width=4, alpha=version_alpha * version_line, trace_id="sentence-versions")
    usage_alpha = alpha * usage_in * (1.0 - 0.72 * dialog_in)
    _paste_image(ctx, str(visual["usage_image"]), (1160, 430, 1785, 760), crop=(820, 250, 1370, 620), alpha=usage_alpha, radius=16, trace_id="usage-card")
    pattern_alpha = usage_alpha * _ease(ctx, 10.5, 0.45)
    draw_text(ctx, (1210, 785), str(visual["usage_patterns"][0]), size=22, kind="sans_bold", fill=GREEN, alpha=pattern_alpha, trace_id="usage-pattern")
    usage_line = smooth(progress(ctx.scene_t, 12.8, 0.55))
    draw_line(ctx, (1160, 770), (1160 + 625 * usage_line, 770), color=GREEN, width=4, alpha=usage_alpha * usage_line, trace_id="usage-card")
    usage_focus = smooth(progress(ctx.scene_t, 14.5, 0.5))
    draw_line(ctx, (1185, 405), (1185 + 540 * usage_focus, 405), color=GREEN, width=4, alpha=usage_alpha * usage_focus, trace_id="usage-card")
    code_alpha = alpha * _ease(ctx, 6.0, 0.45) * (1.0 - 0.72 * usage_in) * (1.0 - 0.72 * dialog_in)
    _code_panel(ctx, (1360, 112, 1785, 242), list(visual["code"]), alpha=0.72 * code_alpha, trace_ids=["corrected-code", "better-code", "usage-code"])
    _paste_image(ctx, str(visual["dialog_image"]), (610, 150, 1310, 725), alpha=alpha * dialog_in, radius=18, trace_id="detected-dialog")
    dialog_focus = smooth(progress(ctx.scene_t, 16.8, 0.5))
    draw_line(ctx, (690, 345), (690 + 480 * dialog_focus, 345), color=GREEN, width=5, alpha=alpha * dialog_focus, trace_id="detected-dialog")
    dialog_line = smooth(progress(ctx.scene_t, 18.0, 0.55))
    draw_line(ctx, (720, 737), (720 + 480 * dialog_line, 737), color=GREEN, width=8, alpha=alpha * dialog_line, trace_id="detected-dialog")


def automatic_scheduler(ctx: SceneContext, visual: dict) -> None:
    _use_design_time(ctx, 13.5)
    alpha = _ease(ctx)
    _chapter(ctx, alpha)
    draw_text(ctx, (960, 148), str(visual["headline"]), size=40, kind="sans_bold", fill=INK, alpha=alpha, anchor="mm")
    settings_alpha = alpha * (0.56 + 0.18 * _ease(ctx, 7.4, 0.45))
    _paste_image(ctx, str(visual["app_image"]), (95, 205, 815, 795), crop=(270, 525, 1060, 980), alpha=settings_alpha, radius=18, trace_id="settings-evidence")
    _panel(ctx, (140, 245, 770, 355), fill=CREAM, outline=BORDER, radius=16, alpha=alpha, trace_id="settings-evidence")
    draw_text(ctx, (455, 285), str(visual["exercise_label"]), size=22, kind="sans", fill=MUTED, alpha=alpha, anchor="mm")
    draw_text(ctx, (455, 326), str(visual["word"]), size=46, kind="sans_bold", fill=GREEN, alpha=alpha, anchor="mm")
    evidence = list(visual["evidence"])
    positions = [(900, 245), (1245, 245), (900, 355), (1245, 355)]
    for index, (item, position) in enumerate(zip(evidence, positions)):
        event_alpha = alpha * _ease(ctx, 1.0 + index * 0.32, 0.32)
        _tag(ctx, position, str(item), alpha=event_alpha, active=index < 2, trace_id="evidence-points" if index < 2 else "behavior-points")
    merge_alpha = alpha * _ease(ctx, 3.5, 0.4)
    for index, position in enumerate(positions):
        arrow_alpha = alpha * _ease(ctx, 3.5 + index * 0.18, 0.3)
        draw_arrow(ctx, (position[0] + 120, position[1] + 52), (1160, 520), color=GREEN, width=3, alpha=0.32 * arrow_alpha, trace_id="evidence-merge")
    _panel(ctx, (960, 490, 1360, 575), fill=GREEN_SOFT, outline=GREEN, radius=16, alpha=merge_alpha, trace_id="evidence-merge")
    draw_text(ctx, (1160, 530), str(visual["screen_text"][0]), size=32, kind="sans_bold", fill=GREEN, alpha=merge_alpha, anchor="mm")
    timeline_alpha = alpha * _ease(ctx, 5.7, 0.4)
    draw_line(ctx, (875, 690), (1640, 690), color=BORDER, width=5, alpha=timeline_alpha, trace_id="fsrs-timeline")
    draw_text(ctx, (895, 735), str(visual["timeline"][0]), size=23, kind="sans", fill=MUTED, alpha=timeline_alpha, anchor="mm")
    draw_text(ctx, (1620, 735), str(visual["timeline"][1]), size=23, kind="sans_bold", fill=GREEN, alpha=timeline_alpha, anchor="mm")
    marker_progress = smooth(progress(ctx.scene_t, 6.0, 1.6))
    marker_x = _lerp(895, 1620, marker_progress)
    ctx.trace.append({"type": "marker", "value": "", "bbox": [marker_x - 13, 702, marker_x + 13, 728], "alpha": timeline_alpha, "trace_id": "fsrs-timeline", "style": list(GREEN[:3])})
    ctx.draw.ellipse((marker_x - 13, 677, marker_x + 13, 703), fill=with_alpha(GREEN, timeline_alpha))
    success_alpha = alpha * _ease(ctx, 7.4, 0.35) * (1.0 - _ease(ctx, 10.4, 0.35))
    _tag(ctx, (1010, 595), str(visual["success_label"]), alpha=success_alpha, active=True, trace_id="success-benefit")
    retest_alpha = alpha * _ease(ctx, 9.2, 0.4)
    _panel(ctx, (125, 620, 755, 735), fill=RED_SOFT, outline=RED_DARK, radius=16, alpha=retest_alpha, trace_id="retest-note")
    draw_text(ctx, (440, 662), str(visual["retest_title"]), size=22, kind="sans_bold", fill=RED_DARK, alpha=retest_alpha, anchor="mm")
    draw_text(ctx, (440, 704), str(visual["retest_action"]), size=27, kind="sans_bold", fill=INK, alpha=retest_alpha, anchor="mm")
    note_alpha = alpha * _ease(ctx, 10.9, 0.4)
    _tag(ctx, (1010, 595), str(visual["screen_text"][1]), alpha=note_alpha, active=True, trace_id="no-rating-note")
    draw_text(ctx, (1645, 790), str(visual["algorithm_label"]), size=16, kind="sans", fill=MUTED, alpha=note_alpha, anchor="rm")
    _code_panel(ctx, (145, 755, 570, 815), list(visual["code"]), alpha=0.72 * alpha * _ease(ctx, 6.8, 0.35), trace_ids=["scheduler-code"])


def data_boundary(ctx: SceneContext, visual: dict) -> None:
    _use_design_time(ctx, 10.5)
    alpha = _ease(ctx)
    _chapter(ctx, alpha)
    _paste_image(ctx, str(visual["app_image"]), (90, 175, 900, 805), crop=(240, 110, 1120, 990), alpha=0.72 * alpha, radius=18, trace_id="settings-window")
    draw_text(ctx, (960, 145), str(visual["headline"]), size=40, kind="sans_bold", fill=INK, alpha=alpha, anchor="mm")
    local_alpha = alpha * _ease(ctx, 0.8, 0.4)
    _panel(ctx, (980, 220, 1765, 385), fill=GREEN_SOFT, outline=GREEN, radius=18, alpha=local_alpha, trace_id="local-route")
    draw_text(ctx, (1370, 270), str(visual["routes"][0]), size=31, kind="sans_bold", fill=GREEN, alpha=local_alpha, anchor="mm")
    draw_text(ctx, (1370, 325), str(visual["local_detail"]), size=22, kind="sans", fill=MUTED, alpha=local_alpha, anchor="mm")
    api_alpha = alpha * _ease(ctx, 3.0, 0.4)
    _panel(ctx, (980, 420, 1765, 600), fill=CREAM, outline=BORDER, radius=18, alpha=api_alpha, trace_id="ai-optional")
    draw_text(ctx, (1370, 470), str(visual["ai_optional"]), size=27, kind="sans_bold", fill=BLUE_DARK, alpha=api_alpha, anchor="mm", trace_id="ai-optional")
    route_alpha = alpha * _ease(ctx, 3.8, 0.4)
    draw_text(ctx, (1370, 523), str(visual["routes"][1]), size=21, kind="sans", fill=INK, alpha=route_alpha, anchor="mm", trace_id="api-route")
    draw_text(ctx, (1370, 565), str(visual["provider_note"]), size=17, kind="sans", fill=MUTED, alpha=route_alpha * _ease(ctx, 4.5, 0.35), anchor="mm", trace_id="provider-route")
    language_alpha = alpha * _ease(ctx, 6.2, 0.45)
    _panel(ctx, (980, 635, 1765, 785), fill=CREAM, outline=BORDER, radius=18, alpha=language_alpha, trace_id="language-settings")
    draw_text(ctx, (1370, 670), str(visual["language_heading"]), size=23, kind="sans_bold", fill=INK, alpha=language_alpha, anchor="mm")
    for index, item in enumerate(list(visual["languages"])):
        _tag(ctx, (1030 + index * 230, 710), str(item), alpha=language_alpha * _ease(ctx, 6.2 + index * 0.25, 0.3), active=index == 1, trace_id="language-settings")
    language_line = smooth(progress(ctx.scene_t, 8.2, 0.4))
    draw_line(ctx, (1030, 770), (1710, 770), color=GREEN, width=4, alpha=alpha * language_line, trace_id="language-settings")
    _code_panel(ctx, (140, 735, 570, 800), list(visual["code"]), alpha=0.72 * alpha * _ease(ctx, 6.0, 0.35), trace_ids=["data-path-code", "language-code"])


def summary(ctx: SceneContext, visual: dict) -> None:
    _use_design_time(ctx, 7.0)
    alpha = _ease(ctx)
    _paste_image(ctx, str(visual["app_image"]), (280, 115, 1640, 800), alpha=0.34 * alpha, radius=22, trace_id="summary-window")
    _panel(ctx, (470, 215, 1450, 710), fill=CREAM, outline=BORDER, radius=24, alpha=0.96 * alpha)
    draw_text(ctx, (960, 320), str(visual["headline"]), size=62, kind="sans_bold", fill=INK, alpha=alpha, anchor="mm")
    draw_text(ctx, (960, 390), str(visual["detail"]), size=26, kind="code", fill=GREEN, alpha=alpha, anchor="mm")
    items = list(visual["items"])
    for index, item in enumerate(items):
        item_alpha = alpha * _ease(ctx, 0.9 + index * 1.0, 0.5)
        _tag(ctx, (585 + index * 270, 500), str(item), alpha=item_alpha, active=index == 1, trace_id=f"summary-{index}")


RENDERERS = {
    "open_source_intro": open_source_intro,
    "word_gap": word_gap,
    "sentence_flow": sentence_flow,
    "feedback_artifacts": feedback_artifacts,
    "automatic_scheduler": automatic_scheduler,
    "data_boundary": data_boundary,
    "summary": summary,
}


def render_scene(ctx: SceneContext) -> None:
    kind = str(ctx.scene["kind"])
    renderer = RENDERERS.get(kind)
    if renderer is None:
        raise KeyError(f"unknown scene kind: {kind}")
    renderer(ctx, dict(ctx.scene["visual"]))
