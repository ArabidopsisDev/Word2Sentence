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
    # The promotional cut deliberately has no persistent chapter chrome.
    return


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


def _cursor(ctx: SceneContext, xy: tuple[float, float], *, alpha: float = 1.0, click: float = 0.0, trace_id: str | None = None) -> None:
    if alpha <= 0:
        return
    x, y = xy
    if click > 0:
        radius = 16 + 18 * click
        ctx.draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=with_alpha(GREEN, alpha * (1.0 - click)), width=4)
    ctx.draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill=with_alpha(CREAM, alpha), outline=with_alpha(GREEN, alpha), width=3)
    ctx.trace.append({"type": "cursor", "value": "", "bbox": [x - 8, y - 8, x + 8, y + 8], "alpha": alpha, "trace_id": trace_id, "style": list(GREEN[:3])})


def _focus(ctx: SceneContext, box: tuple[float, float, float, float], *, alpha: float, color=GREEN, trace_id: str | None = None) -> None:
    if alpha <= 0:
        return
    ctx.draw.rounded_rectangle(box, radius=12, outline=with_alpha(color, alpha), width=5)
    ctx.trace.append({"type": "focus", "value": "", "bbox": list(box), "alpha": alpha, "trace_id": trace_id, "style": list(color[:3])})


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
    question_alpha = min(_ease(ctx, 0.25, 0.45), 1.0 - _ease(ctx, 3.0, 0.45))
    draw_text(ctx, (960, 465), str(visual["problem_hint"]), size=52, kind="sans_bold", fill=INK, alpha=question_alpha, anchor="mm")
    answer_alpha = _ease(ctx, 3.0, 0.45)
    draw_text(ctx, (960, 415), str(visual["headline"]), size=74, kind="sans_bold", fill=INK, alpha=answer_alpha, anchor="mm")
    draw_line(ctx, (665, 490), (1255, 490), color=GREEN, width=5, alpha=answer_alpha)
    draw_text(ctx, (960, 555), str(visual["detail"]), size=29, kind="sans", fill=GREEN, alpha=_ease(ctx, 3.55, 0.4), anchor="mm", trace_id="about-window")


def word_gap(ctx: SceneContext, visual: dict) -> None:
    _use_design_time(ctx, 12.0)
    entry = _ease(ctx, 0.2, 0.55)
    expand = _ease(ctx, 4.6, 0.85)
    feature_box = (780, 165, 1810, 815)
    demo_box = (183, 50, 1737, 1028)
    box = tuple(round(_lerp(feature_box[index], demo_box[index], expand)) for index in range(4))
    _paste_image(ctx, str(visual["app_image"]), box, alpha=entry, radius=20, trace_id="library-window")

    copy_alpha = entry * (1.0 - _ease(ctx, 4.35, 0.45))
    draw_text(ctx, (130, 270), str(visual["headline"]), size=76, kind="sans_bold", fill=GREEN, alpha=copy_alpha * _ease(ctx, 1.2, 0.4), trace_id="word-distract")
    draw_text(ctx, (132, 370), str(visual["meaning"]), size=30, kind="sans", fill=MUTED, alpha=copy_alpha * _ease(ctx, 1.8, 0.35))
    gap_alpha = copy_alpha * _ease(ctx, 2.7, 0.35)
    draw_text(ctx, (132, 480), str(visual["gap_label"]), size=26, kind="sans_bold", fill=MUTED, alpha=gap_alpha, trace_id="collocation-gap")
    draw_text(ctx, (132, 535), str(visual["gap_value"]), size=39, kind="sans_bold", fill=INK, alpha=copy_alpha * _ease(ctx, 4.0, 0.35), trace_id="collocation-answer")

    demo_alpha = _ease(ctx, 5.6, 0.35)
    row_focus = demo_alpha * _ease(ctx, 6.5, 0.35) * (1.0 - _ease(ctx, 8.8, 0.35))
    _focus(ctx, (590, 476, 1515, 532), alpha=row_focus, trace_id="word-summary")
    cursor_progress = smooth(progress(ctx.scene_t, 6.2, 2.1))
    cursor_x = _lerp(1120, 650, min(cursor_progress, 0.52) / 0.52) if cursor_progress < 0.52 else _lerp(650, 1470, (cursor_progress - 0.52) / 0.48)
    cursor_y = _lerp(300, 505, min(cursor_progress, 0.52) / 0.52) if cursor_progress < 0.52 else _lerp(505, 950, (cursor_progress - 0.52) / 0.48)
    click = smooth(progress(ctx.scene_t, 8.15, 0.18)) * (1.0 - smooth(progress(ctx.scene_t, 8.55, 0.22)))
    _cursor(ctx, (cursor_x, cursor_y), alpha=demo_alpha, click=click, trace_id="gap-summary")
    button_focus = _ease(ctx, 9.2, 0.35)
    _focus(ctx, (1390, 920, 1665, 985), alpha=button_focus, trace_id="gap-summary")
    draw_text(ctx, (650, 825), str(visual["screen_text"][1]), size=23, kind="sans_bold", fill=GREEN, alpha=_ease(ctx, 9.2, 0.45), anchor="rm")
    _code_panel(ctx, (690, 780, 1510, 850), list(visual["code"]), alpha=0.82 * _ease(ctx, 9.2, 0.45), trace_ids=["license-code"], token_kinds=[{"token": "AGPL-3.0-only", "kind": "string"}])


def sentence_flow(ctx: SceneContext, visual: dict) -> None:
    _use_design_time(ctx, 15.5)
    demo_box = (183, 50, 1737, 1028)
    entry = _ease(ctx, 0.15, 0.4)
    completed_state = _ease(ctx, 9.8, 0.35)
    _paste_image(ctx, str(visual["empty_image"]), demo_box, alpha=entry * (1.0 - completed_state), radius=20, trace_id="add-word-fragment")
    _paste_image(ctx, str(visual["app_image"]), demo_box, alpha=completed_state, radius=20, trace_id="scenario-fragment")

    word_focus = _ease(ctx, 1.6, 0.35) * (1.0 - _ease(ctx, 3.5, 0.35))
    _focus(ctx, (585, 140, 880, 220), alpha=word_focus, trace_id="word-transfer")
    scenario_focus = _ease(ctx, 2.3, 0.35) * (1.0 - _ease(ctx, 6.3, 0.35))
    _focus(ctx, (600, 218, 1560, 412), alpha=scenario_focus, trace_id="scenario-fragment")
    input_focus = _ease(ctx, 6.8, 0.35)
    _focus(ctx, (615, 462, 1535, 588), alpha=input_focus, trace_id="sentence-input")

    cursor_to_input = smooth(progress(ctx.scene_t, 4.8, 1.6))
    cursor_x = _lerp(920, 790, cursor_to_input)
    cursor_y = _lerp(300, 520, cursor_to_input)
    _cursor(ctx, (cursor_x, cursor_y), alpha=_ease(ctx, 4.6, 0.3), click=smooth(progress(ctx.scene_t, 6.25, 0.18)) * (1.0 - smooth(progress(ctx.scene_t, 6.55, 0.18))), trace_id="sentence-input")

    sentence = str(visual["sentence"])
    typed_progress = smooth(progress(ctx.scene_t, 7.0, 3.0))
    typed = sentence[: round(len(sentence) * typed_progress)]
    draw_text(ctx, (643, 497), typed, size=18, kind="sans", fill=INK, alpha=(1.0 - completed_state) * input_focus, trace_id="typed-sentence")

    submit_progress = smooth(progress(ctx.scene_t, 10.0, 1.2))
    submit_x = _lerp(790, 1490, submit_progress)
    submit_y = _lerp(520, 620, submit_progress)
    submit_click = smooth(progress(ctx.scene_t, 11.2, 0.18)) * (1.0 - smooth(progress(ctx.scene_t, 11.55, 0.2)))
    _cursor(ctx, (submit_x, submit_y), alpha=_ease(ctx, 9.8, 0.25), click=submit_click, trace_id="submit-button")
    _focus(ctx, (1425, 585, 1605, 655), alpha=_ease(ctx, 10.3, 0.35), trace_id="submit-button")
    _focus(ctx, (615, 330, 990, 382), alpha=_ease(ctx, 10.8, 0.35) * (1.0 - _ease(ctx, 12.2, 0.35)), trace_id="hint-option")

    token = str(visual["error_token"])
    token_index = sentence.find(token)
    if token_index >= 0:
        sentence_font = get_font(ctx.config, "sans", 18)
        token_x = 643 + ctx.draw.textlength(sentence[:token_index], font=sentence_font)
        token_width = ctx.draw.textlength(token, font=sentence_font)
        draw_line(ctx, (token_x, 520), (token_x + token_width, 520), color=RED_DARK, width=4, alpha=_ease(ctx, 11.8, 0.35), trace_id="error-token")
    draw_text(ctx, (1170, 865), str(visual["flow"][2]), size=24, kind="sans_bold", fill=GREEN, alpha=_ease(ctx, 12.0, 0.45), anchor="rm")
    _code_panel(ctx, (1210, 815, 1695, 920), list(visual["code"]), alpha=_ease(ctx, 12.0, 0.45), trace_ids=["challenge-method", "evaluate-method"], explicit_kinds=["method", "method"])


def feedback_artifacts(ctx: SceneContext, visual: dict) -> None:
    _use_design_time(ctx, 20.0)
    demo_box = (100, 80, 1500, 960)
    scrolled = _ease(ctx, 5.2, 0.55)
    dialog_in = _ease(ctx, 15.5, 0.5)
    entry = _ease(ctx, 0.1, 0.45)
    _paste_image(ctx, str(visual["top_image"]), demo_box, alpha=entry * (1.0 - scrolled), radius=20, trace_id="feedback-window")
    _paste_image(ctx, str(visual["app_image"]), demo_box, alpha=scrolled * (1.0 - 0.30 * dialog_in), radius=20, trace_id="usage-card")

    feedback_focus = _ease(ctx, 1.2, 0.35) * (1.0 - _ease(ctx, 3.0, 0.35))
    _focus(ctx, (600, 820, 1515, 950), alpha=feedback_focus, trace_id="feedback-segments")
    _focus(ctx, (620, 875, 1515, 955), alpha=_ease(ctx, 3.2, 0.35) * (1.0 - _ease(ctx, 4.8, 0.35)), trace_id="feedback-detail")
    cursor_scroll = smooth(progress(ctx.scene_t, 4.2, 1.6))
    _cursor(ctx, (1590, _lerp(420, 770, cursor_scroll)), alpha=_ease(ctx, 3.8, 0.3), trace_id="sentence-versions")

    version_focus = _ease(ctx, 6.2, 0.35) * (1.0 - _ease(ctx, 10.5, 0.35))
    _focus(ctx, (600, 755, 1535, 970), alpha=version_focus, trace_id="sentence-versions")
    version_line = smooth(progress(ctx.scene_t, 8.0, 0.5))
    draw_line(ctx, (630, 980), (630 + 820 * version_line, 980), color=GREEN, width=4, alpha=version_focus * version_line, trace_id="sentence-versions")
    code_alpha = _ease(ctx, 6.0, 0.45) * (1.0 - _ease(ctx, 9.3, 0.35)) * (1.0 - dialog_in)
    _code_panel(ctx, (1260, 85, 1705, 220), list(visual["code"]), alpha=0.78 * code_alpha, trace_ids=["corrected-code", "better-code", "usage-code"])
    draw_text(ctx, (1215, 115), str(visual["screen_text"][0]), size=22, kind="sans_bold", fill=GREEN, alpha=code_alpha, anchor="rm")

    usage_focus = _ease(ctx, 10.0, 0.35) * (1.0 - _ease(ctx, 15.0, 0.35))
    _focus(ctx, (600, 145, 1535, 345), alpha=usage_focus, trace_id="usage-card")
    pattern_alpha = _ease(ctx, 11.2, 0.35) * (1.0 - _ease(ctx, 15.0, 0.35))
    _focus(ctx, (615, 180, 1515, 235), alpha=pattern_alpha, trace_id="usage-pattern")
    _focus(ctx, (615, 235, 1515, 285), alpha=_ease(ctx, 13.0, 0.35) * (1.0 - _ease(ctx, 15.0, 0.35)), trace_id="usage-next")
    _focus(ctx, (615, 285, 1515, 335), alpha=_ease(ctx, 14.2, 0.35) * (1.0 - _ease(ctx, 15.5, 0.25)), trace_id="usage-third")

    _paste_image(ctx, str(visual["dialog_image"]), (610, 185, 1310, 760), alpha=dialog_in, radius=18, trace_id="detected-dialog")
    dialog_focus = _ease(ctx, 16.8, 0.35)
    _focus(ctx, (690, 360, 1210, 520), alpha=dialog_focus, trace_id="detected-dialog")
    confirm_progress = smooth(progress(ctx.scene_t, 17.2, 1.2))
    confirm_x = _lerp(850, 1180, confirm_progress)
    confirm_y = _lerp(450, 700, confirm_progress)
    confirm_click = smooth(progress(ctx.scene_t, 18.4, 0.18)) * (1.0 - smooth(progress(ctx.scene_t, 18.8, 0.2)))
    _cursor(ctx, (confirm_x, confirm_y), alpha=dialog_in, click=confirm_click, trace_id="dialog-confirm")


def automatic_scheduler(ctx: SceneContext, visual: dict) -> None:
    _use_design_time(ctx, 13.5)
    demo_box = (183, 50, 1737, 1028)
    switch = _ease(ctx, 4.0, 0.55)
    _paste_image(ctx, str(visual["app_image"]), demo_box, alpha=1.0 - switch, radius=20, trace_id="settings-evidence")
    _paste_image(ctx, str(visual["today_image"]), demo_box, alpha=switch, radius=20, trace_id="evidence-merge")

    evidence_alpha = _ease(ctx, 0.8, 0.35) * (1.0 - _ease(ctx, 3.9, 0.35))
    _focus(ctx, (475, 705, 935, 765), alpha=evidence_alpha, trace_id="evidence-points")
    _focus(ctx, (475, 775, 1320, 892), alpha=_ease(ctx, 1.8, 0.35) * (1.0 - _ease(ctx, 3.9, 0.35)), trace_id="behavior-points")

    timeline_alpha = _ease(ctx, 5.5, 0.4)
    draw_text(ctx, (1690, 285), str(visual["screen_text"][0]), size=28, kind="sans_bold", fill=GREEN, alpha=timeline_alpha, anchor="mm", trace_id="evidence-merge")
    draw_line(ctx, (1690, 390), (1690, 720), color=BORDER, width=5, alpha=timeline_alpha, trace_id="fsrs-timeline")
    draw_text(ctx, (1750, 410), str(visual["timeline"][0]), size=24, kind="sans", fill=MUTED, alpha=timeline_alpha, anchor="lm")
    draw_text(ctx, (1750, 700), str(visual["timeline"][1]), size=24, kind="sans_bold", fill=GREEN, alpha=timeline_alpha, anchor="lm")
    marker_progress = smooth(progress(ctx.scene_t, 6.0, 1.6))
    marker_y = _lerp(410, 700, marker_progress)
    ctx.draw.ellipse((1677, marker_y - 13, 1703, marker_y + 13), fill=with_alpha(GREEN, timeline_alpha))
    ctx.trace.append({"type": "marker", "value": "", "bbox": [1677, marker_y - 13, 1703, marker_y + 13], "alpha": timeline_alpha, "trace_id": "fsrs-timeline", "style": list(GREEN[:3])})

    success_alpha = _ease(ctx, 7.4, 0.35) * (1.0 - _ease(ctx, 10.4, 0.35))
    draw_text(ctx, (1690, 765), str(visual["success_label"]), size=22, kind="sans_bold", fill=GREEN, alpha=success_alpha, anchor="mm", trace_id="success-benefit")
    retest_alpha = _ease(ctx, 9.2, 0.35) * (1.0 - _ease(ctx, 10.5, 0.3))
    draw_text(ctx, (1518, 825), str(visual["retest_title"]), size=20, kind="sans_bold", fill=RED_DARK, alpha=retest_alpha, trace_id="retest-note")
    draw_text(ctx, (1518, 865), str(visual["retest_action"]), size=23, kind="sans_bold", fill=INK, alpha=retest_alpha, trace_id="retest-note")
    note_alpha = _ease(ctx, 10.9, 0.35)
    draw_text(ctx, (1518, 825), str(visual["screen_text"][1]), size=22, kind="sans_bold", fill=GREEN, alpha=note_alpha, trace_id="no-rating-note")
    draw_text(ctx, (1845, 985), str(visual["algorithm_label"]), size=16, kind="sans", fill=MUTED, alpha=note_alpha, anchor="rm")
    _code_panel(ctx, (1510, 870, 1850, 940), list(visual["code"]), alpha=0.78 * _ease(ctx, 6.8, 0.35), trace_ids=["scheduler-code"])


def learning_statistics(ctx: SceneContext, visual: dict) -> None:
    _use_design_time(ctx, 14.0)
    lower = _ease(ctx, 6.3, 0.55)
    shrink = _ease(ctx, 9.3, 0.65)
    full_box = (183, 50, 1737, 1028)
    proof_box = (80, 90, 1490, 977)
    box = tuple(round(_lerp(full_box[index], proof_box[index], shrink)) for index in range(4))
    entry = _ease(ctx, 0.15, 0.45)
    _paste_image(ctx, str(visual["app_image"]), box, alpha=entry * (1.0 - lower), radius=20, trace_id="statistics-window")
    _paste_image(ctx, str(visual["lower_image"]), box, alpha=lower, radius=20, trace_id="statistics-scroll")

    kpi_alpha = _ease(ctx, 1.4, 0.35) * (1.0 - _ease(ctx, 3.0, 0.35))
    _focus(ctx, (535, 215, 1605, 335), alpha=kpi_alpha, trace_id="statistics-kpis")
    calendar_alpha = _ease(ctx, 3.0, 0.35) * (1.0 - _ease(ctx, 5.1, 0.35))
    _focus(ctx, (925, 340, 1605, 680), alpha=calendar_alpha, trace_id="statistics-calendar")
    streak_alpha = _ease(ctx, 4.5, 0.35) * (1.0 - _ease(ctx, 6.1, 0.35))
    _focus(ctx, (535, 340, 920, 680), alpha=streak_alpha, trace_id="statistics-streak")

    scroll_progress = smooth(progress(ctx.scene_t, 5.8, 1.5))
    _cursor(ctx, (1655, _lerp(420, 790, scroll_progress)), alpha=_ease(ctx, 5.5, 0.3) * (1.0 - shrink), trace_id="statistics-scroll")
    trend_alpha = _ease(ctx, 6.7, 0.35) * (1.0 - _ease(ctx, 9.0, 0.35))
    _focus(ctx, (535, 255, 1605, 575), alpha=trend_alpha, trace_id="statistics-trend")
    distribution_alpha = _ease(ctx, 8.8, 0.35) * (1.0 - _ease(ctx, 10.5, 0.35))
    _focus(ctx, (535, 575, 1605, 845), alpha=distribution_alpha, trace_id="statistics-distribution")

    insight_alpha = _ease(ctx, 9.7, 0.35)
    draw_text(ctx, (1530, 300), str(visual["headline"]), size=34, kind="sans_bold", fill=GREEN, alpha=insight_alpha, trace_id="statistics-insights")
    draw_text(ctx, (1530, 365), str(visual["insight_label"]), size=21, kind="sans", fill=MUTED, alpha=insight_alpha, trace_id="statistics-insights")
    draw_line(ctx, (1530, 430), (1815, 430), color=GREEN, width=4, alpha=smooth(progress(ctx.scene_t, 11.6, 0.45)), trace_id="statistics-settle")
    _code_panel(ctx, (1532, 760, 1872, 835), list(visual["code"]), alpha=0.82 * insight_alpha, trace_ids=["statistics-code"])


def data_boundary(ctx: SceneContext, visual: dict) -> None:
    _use_design_time(ctx, 10.5)
    demo_box = (183, 50, 1737, 1028)
    _paste_image(ctx, str(visual["app_image"]), demo_box, alpha=1.0, radius=20, trace_id="settings-window")

    local_alpha = _ease(ctx, 0.6, 0.35) * (1.0 - _ease(ctx, 3.0, 0.35))
    _focus(ctx, (465, 630, 1230, 970), alpha=local_alpha, trace_id="local-route")
    draw_text(ctx, (1280, 760), str(visual["routes"][0]), size=30, kind="sans_bold", fill=GREEN, alpha=local_alpha, trace_id="local-route")
    draw_text(ctx, (1280, 810), str(visual["local_detail"]), size=22, kind="sans", fill=MUTED, alpha=local_alpha)

    api_alpha = _ease(ctx, 3.0, 0.4) * (1.0 - _ease(ctx, 6.2, 0.35))
    _focus(ctx, (455, 220, 1235, 445), alpha=api_alpha, color=BLUE_DARK, trace_id="ai-optional")
    draw_text(ctx, (1280, 280), str(visual["ai_optional"]), size=29, kind="sans_bold", fill=BLUE_DARK, alpha=api_alpha, trace_id="ai-optional")
    draw_text(ctx, (1280, 335), str(visual["routes"][1]), size=22, kind="sans", fill=INK, alpha=api_alpha * _ease(ctx, 3.8, 0.35), trace_id="api-route")
    draw_text(ctx, (1280, 375), str(visual["provider_note"]), size=18, kind="sans", fill=MUTED, alpha=api_alpha * _ease(ctx, 4.5, 0.35), trace_id="provider-route")

    language_alpha = _ease(ctx, 6.2, 0.4)
    _focus(ctx, (455, 445, 1235, 630), alpha=language_alpha, trace_id="language-settings")
    draw_text(ctx, (1280, 500), str(visual["language_heading"]), size=29, kind="sans_bold", fill=INK, alpha=language_alpha)
    for index, item in enumerate(list(visual["languages"])):
        draw_text(ctx, (1280, 555 + index * 42), str(item), size=22, kind="sans_bold" if index == 1 else "sans", fill=GREEN if index == 1 else MUTED, alpha=language_alpha * _ease(ctx, 6.2 + index * 0.25, 0.3), trace_id="language-settings")
    draw_line(ctx, (1270, 685), (1630, 685), color=GREEN, width=4, alpha=smooth(progress(ctx.scene_t, 8.2, 0.4)), trace_id="language-settle")

    cursor_phase = smooth(progress(ctx.scene_t, 0.7, 8.0))
    if cursor_phase < 0.38:
        p = cursor_phase / 0.38
        cursor_xy = (_lerp(1450, 820, p), _lerp(820, 850, p))
    elif cursor_phase < 0.70:
        p = (cursor_phase - 0.38) / 0.32
        cursor_xy = (_lerp(820, 980, p), _lerp(850, 350, p))
    else:
        p = (cursor_phase - 0.70) / 0.30
        cursor_xy = (_lerp(980, 840, p), _lerp(350, 545, p))
    _cursor(ctx, cursor_xy, alpha=_ease(ctx, 0.5, 0.3), trace_id="language-settle")
    _code_panel(ctx, (1240, 835, 1690, 960), list(visual["code"]), alpha=0.92 * _ease(ctx, 3.7, 0.35), trace_ids=["data-path-code", "language-code"])


def summary(ctx: SceneContext, visual: dict) -> None:
    _use_design_time(ctx, 7.0)
    alpha = 1.0
    zoom = _ease(ctx, 0.0, 2.0)
    margin = round(_lerp(230, 150, zoom))
    _paste_image(ctx, str(visual["app_image"]), (margin, 45, 1920 - margin, 1010), alpha=0.62, radius=24, trace_id="summary-window")
    draw_text(ctx, (150, 200), str(visual["headline"]), size=64, kind="sans_bold", fill=INK, alpha=_ease(ctx, 0.2, 0.4))
    draw_line(ctx, (150, 285), (820, 285), color=GREEN, width=5, alpha=_ease(ctx, 0.55, 0.4))
    draw_text(ctx, (150, 335), str(visual["detail"]), size=26, kind="code", fill=GREEN, alpha=_ease(ctx, 0.55, 0.4))


RENDERERS = {
    "open_source_intro": open_source_intro,
    "word_gap": word_gap,
    "sentence_flow": sentence_flow,
    "feedback_artifacts": feedback_artifacts,
    "automatic_scheduler": automatic_scheduler,
    "learning_statistics": learning_statistics,
    "data_boundary": data_boundary,
    "summary": summary,
}


def render_scene(ctx: SceneContext) -> None:
    kind = str(ctx.scene["kind"])
    renderer = RENDERERS.get(kind)
    if renderer is None:
        raise KeyError(f"unknown scene kind: {kind}")
    renderer(ctx, dict(ctx.scene["visual"]))
