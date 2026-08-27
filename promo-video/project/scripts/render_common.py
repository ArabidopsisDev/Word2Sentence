from __future__ import annotations

import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]


def rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), alpha


WHITE = rgba("#E5E5E5")
MUTED = rgba("#8A8E96")
BLUE = rgba("#569CD6")
TYPE = rgba("#4EC9B0")
METHOD = rgba("#DCDCAA")
NUMBER = rgba("#B3C493")
STRING = rgba("#D69D85")
COMMENT = rgba("#57A64A")
CYAN = rgba("#4DC8AF")
PURPLE = rgba("#8E61F2")
YELLOW = rgba("#E8E28A")
RED = rgba("#DB5558")
LINE = rgba("#31343B")
BLACK = rgba("#000000")


CSHARP_KEYWORDS = {
    "abstract", "as", "async", "await", "base", "bool", "break", "byte", "case",
    "catch", "char", "class", "const", "continue", "decimal", "default", "delegate",
    "do", "double", "else", "enum", "event", "explicit", "extension", "extern", "false",
    "finally", "fixed", "float", "for", "foreach", "goto", "if", "implicit", "in", "int",
    "interface", "internal", "is", "lock", "long", "namespace", "new", "null", "object",
    "operator", "out", "override", "params", "private", "protected", "public", "readonly",
    "record", "ref", "return", "sbyte", "sealed", "short", "sizeof", "stackalloc", "static",
    "string", "struct", "switch", "this", "throw", "true", "try", "typeof", "uint", "ulong",
    "unchecked", "unsafe", "ushort", "using", "var", "virtual", "void", "volatile", "while",
    "with", "yield",
}

CPP_KEYWORDS = {
    "alignas", "alignof", "and", "and_eq", "asm", "auto", "bitand", "bitor", "bool",
    "break", "case", "catch", "char", "class", "compl", "concept", "const", "consteval",
    "constexpr", "constinit", "const_cast", "continue", "co_await", "co_return", "co_yield",
    "decltype", "default", "delete", "do", "double", "dynamic_cast", "else", "enum", "explicit",
    "export", "extern", "false", "float", "for", "friend", "goto", "if", "inline", "int", "long",
    "mutable", "namespace", "new", "noexcept", "not", "not_eq", "nullptr", "operator", "or",
    "or_eq", "private", "protected", "public", "register", "reinterpret_cast", "requires", "return",
    "short", "signed", "sizeof", "static", "static_assert", "static_cast", "struct", "switch",
    "template", "this", "thread_local", "throw", "true", "try", "typedef", "typeid", "typename",
    "union", "unsigned", "using", "virtual", "void", "volatile", "wchar_t", "while", "xor", "xor_eq",
}

LANGUAGE_KEYWORDS = {
    "csharp": CSHARP_KEYWORDS,
    "cs": CSHARP_KEYWORDS,
    "cpp": CPP_KEYWORDS,
    "c++": CPP_KEYWORDS,
}

KNOWN_TYPES = {
    "csharp": {"String", "DateTime", "Task", "List", "IEnumerable", "Span"},
    "cs": {"String", "DateTime", "Task", "List", "IEnumerable", "Span"},
    "cpp": {"string", "vector", "array", "optional", "strong_ordering", "weak_ordering", "partial_ordering"},
    "c++": {"string", "vector", "array", "optional", "strong_ordering", "weak_ordering", "partial_ordering"},
}

SEMANTIC_COLORS = {
    "keyword": BLUE,
    "type": TYPE,
    "method": METHOD,
    "number": NUMBER,
    "string": STRING,
    "comment": COMMENT,
    "text": WHITE,
    "operator": WHITE,
}

TOKEN_RE = re.compile(
    r"//[^\n]*|/\*.*?\*/|\$?@?\"(?:\"\"|\\.|[^\"])*\"|"
    r"<=>|==|!=|<=|>=|=>|\+\+|--|\+=|-=|\?\?=|"
    r"\b\d+(?:\.\d+)?\b|\b[A-Za-z_][A-Za-z0-9_]*\b|\s+|.",
    re.DOTALL,
)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def progress(t: float, start: float, duration: float) -> float:
    return clamp((t - start) / max(duration, 1e-6))


def smooth(value: float) -> float:
    value = clamp(value)
    return value * value * (3.0 - 2.0 * value)


def fade_window(t: float, start: float, end: float, fade: float = 0.45) -> float:
    return smooth(progress(t, start, fade)) * (1.0 - smooth(progress(t, end - fade, fade)))


def with_alpha(color: tuple[int, int, int, int], alpha: float) -> tuple[int, int, int, int]:
    return color[0], color[1], color[2], round(color[3] * clamp(alpha))


def _font_candidates(kind: str) -> list[Path]:
    if kind.startswith("code"):
        return [
            Path("C:/Windows/Fonts/consola.ttf"),
            Path("C:/Windows/Fonts/CascadiaMono.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
            Path("/Library/Fonts/Menlo.ttc"),
        ]
    return [
        Path("C:/Windows/Fonts/msyhbd.ttc" if kind.endswith("bold") else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/PingFang.ttc"),
    ]


@lru_cache(maxsize=256)
def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size=size)


def get_font(config: dict, kind: str, size: int) -> ImageFont.FreeTypeFont:
    explicit = str(config.get("fonts", {}).get(kind, "") or "")
    candidates: list[Path] = []
    if explicit:
        path = Path(explicit)
        candidates.append(path if path.is_absolute() else ROOT / path)
    candidates.extend(_font_candidates(kind))
    for path in candidates:
        if path.is_file():
            return _font(str(path.resolve()), size)
    raise FileNotFoundError(f"no usable {kind} font; set project/config.json fonts.{kind}")


@dataclass
class SceneContext:
    config: dict
    image: Image.Image
    draw: ImageDraw.ImageDraw
    t: float
    scene_t: float
    scene: dict
    trace: list[dict]


def make_context(config: dict, t: float, scene: dict) -> SceneContext:
    width = int(config["video"]["width"])
    height = int(config["video"]["height"])
    background = rgba(config["video"].get("background", "#000000"))
    image = Image.new("RGBA", (width, height), background)
    return SceneContext(config, image, ImageDraw.Draw(image, "RGBA"), t, t - float(scene["start"]), scene, [])


def draw_text(
    ctx: SceneContext,
    xy: tuple[float, float],
    value: str,
    *,
    size: int,
    kind: str = "sans",
    fill: tuple[int, int, int, int] = WHITE,
    alpha: float = 1.0,
    anchor: str = "la",
    stroke_width: int = 0,
    trace_id: str | None = None,
) -> None:
    if alpha <= 0:
        return
    font = get_font(ctx.config, kind, size)
    box = ctx.draw.textbbox(xy, value, font=font, anchor=anchor, stroke_width=stroke_width)
    ctx.trace.append({"type": "text", "value": value, "bbox": list(box), "alpha": alpha, "trace_id": trace_id, "style": list(fill[:3]), "_font": font, "_xy": xy, "_anchor": anchor, "_stroke_width": stroke_width})
    ctx.draw.text(
        xy,
        value,
        font=font,
        fill=with_alpha(fill, alpha),
        anchor=anchor,
        stroke_width=stroke_width,
        stroke_fill=with_alpha(BLACK, alpha),
    )


def draw_line(
    ctx: SceneContext,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    color: tuple[int, int, int, int] = CYAN,
    width: int = 3,
    alpha: float = 1.0,
    trace_id: str | None = None,
) -> None:
    if alpha <= 0:
        return
    ctx.trace.append({"type": "line", "value": "", "bbox": [min(start[0], end[0]), min(start[1], end[1]), max(start[0], end[0]), max(start[1], end[1])], "alpha": alpha, "trace_id": trace_id, "style": list(color[:3])})
    ctx.draw.line((*start, *end), fill=with_alpha(color, alpha), width=width)


def draw_arrow(
    ctx: SceneContext,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    color: tuple[int, int, int, int] = CYAN,
    width: int = 3,
    head: float = 12.0,
    alpha: float = 1.0,
    trace_id: str | None = None,
) -> None:
    draw_line(ctx, start, end, color=color, width=width, alpha=alpha, trace_id=trace_id)
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length < 8.0 or alpha <= 0:
        return
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    effective = min(head, max(1.5, length * 0.20))
    p1 = (end[0] - ux * effective + px * effective * 0.55, end[1] - uy * effective + py * effective * 0.55)
    p2 = (end[0] - ux * effective - px * effective * 0.55, end[1] - uy * effective - py * effective * 0.55)
    ctx.draw.polygon((end, p1, p2), fill=with_alpha(color, alpha))


def language_lexer(language: str) -> tuple[set[str], set[str]]:
    normalized = language.lower()
    return LANGUAGE_KEYWORDS.get(normalized, set()), KNOWN_TYPES.get(normalized, set())


def code_tokens(value: str, language: str = "csharp") -> list[tuple[str, tuple[int, int, int, int]]]:
    raw = TOKEN_RE.findall(value)
    keywords, known_types = language_lexer(language)
    colored: list[tuple[str, tuple[int, int, int, int]]] = []
    for index, token in enumerate(raw):
        if token.startswith("//") or token.startswith("/*"):
            color = COMMENT
        elif '"' in token and not token.isspace():
            color = STRING
        elif token in keywords:
            color = BLUE
        elif re.fullmatch(r"\d+(?:\.\d+)?", token):
            color = NUMBER
        elif re.fullmatch(r"[A-Za-z_]\w*", token):
            next_non_space = next((item for item in raw[index + 1 :] if not item.isspace()), "")
            previous_non_space = next((item for item in reversed(raw[:index]) if not item.isspace()), "")
            if token in known_types or (language.lower() in {"csharp", "cs"} and previous_non_space == "new"):
                color = TYPE
            elif next_non_space == "(":
                color = METHOD
            elif language.lower() in {"csharp", "cs"} and token[0].isupper():
                color = TYPE
            else:
                color = WHITE
        else:
            color = WHITE
        colored.append((token, color))
    return colored


def semantic_spans(value: str, language: str, spans: list[dict] | None) -> list[tuple[str, tuple[int, int, int, int]]]:
    if not spans:
        return code_tokens(value, language)
    ordered = sorted(spans, key=lambda item: int(item["start"]))
    output: list[tuple[str, tuple[int, int, int, int]]] = []
    cursor = 0
    for span in ordered:
        start, end = int(span["start"]), int(span["end"])
        if start < cursor or end <= start or end > len(value):
            raise ValueError(f"invalid semantic span {start}..{end} for {len(value)} characters")
        if start > cursor:
            output.extend(code_tokens(value[cursor:start], language))
        kind = str(span["kind"])
        if kind not in SEMANTIC_COLORS:
            raise ValueError(f"unknown semantic span kind: {kind}")
        output.append((value[start:end], SEMANTIC_COLORS[kind]))
        cursor = end
    if cursor < len(value):
        output.extend(code_tokens(value[cursor:], language))
    return output


def draw_code(
    ctx: SceneContext,
    value: str,
    xy: tuple[float, float],
    *,
    size: int = 40,
    alpha: float = 1.0,
    anchor: str = "la",
    spans: list[dict] | None = None,
    trace_id: str | None = None,
) -> float:
    font = get_font(ctx.config, "code", size)
    x, y = xy
    total_width = ctx.draw.textlength(value, font=font)
    if anchor in {"ma", "mm", "ms"}:
        x -= total_width / 2
    elif anchor in {"ra", "rm", "rs"}:
        x -= total_width
    if alpha <= 0:
        return x + total_width
    language = str(ctx.config.get("code", {}).get("language", "csharp"))
    segments = semantic_spans(value, language, spans)
    style_signature = [[token, list(color[:3])] for token, color in segments if token.strip()]
    ctx.trace.append({"type": "code", "value": value, "bbox": [x, y, x + total_width, y + size * 1.35], "alpha": alpha, "trace_id": trace_id, "style": style_signature, "_segments": [token for token, _ in segments], "_font": font, "_xy": (x, y), "_anchor": "la", "_stroke_width": 0})
    for token, color in segments:
        ctx.draw.text((x, y), token, font=font, fill=with_alpha(color, alpha), anchor="la")
        x += ctx.draw.textlength(token, font=font)
    return x


def fit_one_line(ctx: SceneContext, value: str) -> tuple[ImageFont.FreeTypeFont, int]:
    subtitle = ctx.config["subtitles"]
    safe_width = int(subtitle["safe_width"])
    for size in range(int(subtitle["max_size"]), int(subtitle["min_size"]) - 1, -1):
        font = get_font(ctx.config, "sans_bold", size)
        box = ctx.draw.textbbox((0, 0), value, font=font, stroke_width=int(subtitle.get("stroke_width", 3)))
        if box[2] - box[0] <= safe_width:
            return font, size
    raise ValueError(f"subtitle cannot fit one line: {value}")


def draw_subtitle(ctx: SceneContext, value: str, alpha: float) -> int:
    font, size = fit_one_line(ctx, value)
    if alpha <= 0:
        return size
    subtitle = ctx.config["subtitles"]
    box = ctx.draw.textbbox(
        (int(ctx.config["video"]["width"]) / 2, int(subtitle["center_y"])),
        value,
        font=font,
        anchor="mm",
        stroke_width=int(subtitle.get("stroke_width", 3)),
    )
    band = (box[0] - 34, box[1] - 18, box[2] + 34, box[3] + 18)
    ctx.draw.rounded_rectangle(
        band,
        radius=18,
        fill=with_alpha(rgba("#242522"), 0.94 * alpha),
    )
    ctx.trace.append({"type": "subtitle", "value": value, "bbox": list(box), "alpha": alpha})
    ctx.draw.text(
        (int(ctx.config["video"]["width"]) / 2, int(subtitle["center_y"])),
        value,
        font=font,
        fill=with_alpha(WHITE, alpha),
        anchor="mm",
        stroke_width=int(subtitle.get("stroke_width", 3)),
        stroke_fill=with_alpha(BLACK, alpha),
    )
    return size


def draw_chapter_header(ctx: SceneContext, scene: dict, alpha: float = 1.0) -> None:
    index = scene.get("chapter_index")
    total = scene.get("chapter_total")
    if index is None or total is None:
        return
    draw_text(ctx, (78, 74), f"{int(index):02d} / {int(total):02d}", size=27, kind="code", fill=CYAN, alpha=alpha, anchor="lm")
    draw_line(ctx, (184, 74), (242, 74), color=CYAN, width=2, alpha=0.75 * alpha)
    draw_text(ctx, (262, 74), str(scene.get("chapter_title", scene.get("title", ""))), size=29, kind="sans_bold", fill=MUTED, alpha=alpha, anchor="lm")


def focus_box(
    ctx: SceneContext,
    box: tuple[float, float, float, float],
    *,
    color: tuple[int, int, int, int] = CYAN,
    alpha: float = 1.0,
    radius: int = 6,
    trace_id: str | None = None,
) -> None:
    if alpha <= 0:
        return
    ctx.trace.append({"type": "focus_box", "value": "", "bbox": list(box), "alpha": alpha, "trace_id": trace_id, "style": list(color[:3])})
    overlay = Image.new("RGBA", ctx.image.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay, "RGBA")
    overlay_draw.rounded_rectangle(box, radius=radius, fill=with_alpha(color, 0.06 * alpha), outline=with_alpha(color, 0.75 * alpha), width=2)
    ctx.image.alpha_composite(overlay)


def distribute(items: Iterable[str], top: float, step: float) -> list[tuple[str, float]]:
    return [(value, top + index * step) for index, value in enumerate(items)]
