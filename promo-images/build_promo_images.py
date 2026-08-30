from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageSequence


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
BG = ROOT / "backgrounds"
OUT = ROOT / "output"
APP = ROOT / "assets" / "app"
ICON = PROJECT / "Word2Sentence" / "Assets" / "Word2Sentence.ico"

W, H = 1920, 1080
INK = "#20231F"
MUTED = "#636861"
GREEN = "#2F684E"
GREEN_DEEP = "#234F3B"
GREEN_SOFT = "#DDEADF"
BLUE = "#4779A6"
RED = "#B34A45"
CREAM = "#FFFDF8"
LINE = "#D7D7D0"

FONT_REGULAR = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def background(name: str, tint: tuple[int, int, int, int] = (255, 253, 248, 30)) -> Image.Image:
    image = Image.open(BG / name).convert("RGBA")
    image = ImageOps.fit(image, (W, H), method=Image.Resampling.LANCZOS)
    veil = Image.new("RGBA", (W, H), tint)
    return Image.alpha_composite(image, veil)


def rounded(image: Image.Image, radius: int = 24, outline: bool = True) -> Image.Image:
    source = image.convert("RGBA")
    mask = Image.new("L", source.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, source.width - 1, source.height - 1), radius=radius, fill=255)
    result = Image.new("RGBA", source.size)
    result.paste(source, (0, 0), mask)
    if outline:
        ImageDraw.Draw(result).rounded_rectangle(
            (1, 1, source.width - 2, source.height - 2),
            radius=radius,
            outline=(196, 198, 191, 220),
            width=2,
        )
    return result


def place_window(
    canvas: Image.Image,
    path: Path,
    box: tuple[int, int, int, int],
    *,
    angle: float = 0,
    shadow: int = 28,
    opacity: float = 1.0,
) -> None:
    x1, y1, x2, y2 = box
    source = Image.open(path).convert("RGBA")
    source = ImageOps.fit(source, (x2 - x1, y2 - y1), method=Image.Resampling.LANCZOS)
    if opacity < 1:
        source.putalpha(source.getchannel("A").point(lambda value: round(value * opacity)))
    card = rounded(source, radius=max(14, round((x2 - x1) * 0.015)))
    if angle:
        card = card.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    shadow_layer = Image.new("RGBA", canvas.size)
    alpha = card.getchannel("A")
    blurred = alpha.filter(ImageFilter.GaussianBlur(shadow))
    shadow_card = Image.new("RGBA", card.size, (30, 36, 30, 0))
    shadow_card.putalpha(blurred.point(lambda value: round(value * 0.28)))
    px = x1 - (card.width - (x2 - x1)) // 2
    py = y1 - (card.height - (y2 - y1)) // 2
    shadow_layer.alpha_composite(shadow_card, (px + 14, py + 20))
    canvas.alpha_composite(shadow_layer)
    canvas.alpha_composite(card, (px, py))


def pill(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, *, active: bool = False, size: int = 22) -> int:
    f = font(size, active)
    left, top = xy
    bbox = draw.textbbox((0, 0), text, font=f)
    width = bbox[2] - bbox[0] + 32
    height = size + 24
    draw.rounded_rectangle(
        (left, top, left + width, top + height),
        radius=height // 2,
        fill=GREEN if active else (255, 253, 248, 225),
        outline=GREEN if active else LINE,
        width=2,
    )
    draw.text((left + 16, top + 9), text, font=f, fill="white" if active else INK)
    return width


def title_block(canvas: Image.Image, title: str, subtitle: str, *, x: int = 90, y: int = 70, width: int = 1100) -> None:
    draw = ImageDraw.Draw(canvas)
    draw.text((x, y), title, font=font(56, True), fill=INK)
    draw.rounded_rectangle((x, y + 82, x + 130, y + 88), radius=3, fill=GREEN)
    draw.multiline_text((x, y + 112), subtitle, font=font(25), fill=MUTED, spacing=8)


def load_icon(size: int) -> Image.Image:
    ico = Image.open(ICON)
    frames = [frame.copy().convert("RGBA") for frame in ImageSequence.Iterator(ico)]
    source = max(frames, key=lambda item: item.width * item.height)
    return ImageOps.fit(source, (size, size), method=Image.Resampling.LANCZOS)


def brand(canvas: Image.Image, *, x: int = 90, y: int = 55, compact: bool = False) -> None:
    size = 58 if compact else 70
    canvas.alpha_composite(load_icon(size), (x, y))
    draw = ImageDraw.Draw(canvas)
    draw.text((x + size + 18, y + 3), "Word2Sentence", font=font(29 if compact else 34, True), fill=INK)
    draw.text((x + size + 18, y + 42), "开源桌面词汇学习工具", font=font(16 if compact else 18), fill=MUTED)


def label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str) -> None:
    x, y = xy
    f = font(20, True)
    tw = draw.textbbox((0, 0), text, font=f)[2]
    draw.rounded_rectangle((x, y, x + tw + 28, y + 44), radius=12, fill=(255, 253, 248, 235), outline=LINE, width=2)
    draw.text((x + 14, y + 8), text, font=f, fill=GREEN_DEEP)


def hero() -> Image.Image:
    canvas = background("hero.png", (255, 253, 248, 16))
    draw = ImageDraw.Draw(canvas)
    brand(canvas, x=76, y=54)
    draw.text((76, 150), "从一个生词，到真正会用", font=font(54, True), fill=INK)
    draw.text((78, 220), "把词义、搭配、表达和复习，放进同一条学习路径。", font=font(24), fill=MUTED)

    features = ["主动词库", "情境造句", "AI 批改", "用法卡", "错词确认", "自动复习", "学习统计", "本地优先", "多语言"]
    cursor_x, cursor_y = 78, 278
    for index, item in enumerate(features):
        item_width = pill(draw, (cursor_x, cursor_y), item, active=index in {1, 2, 5, 6}, size=18)
        cursor_x += item_width + 10
        if cursor_x > 1750:
            cursor_x, cursor_y = 78, cursor_y + 54

    place_window(canvas, APP / "library-zh.png", (35, 405, 690, 975), angle=-3.8, shadow=30)
    place_window(canvas, APP / "statistics-zh.png", (1250, 390, 1900, 980), angle=3.6, shadow=30)
    place_window(canvas, APP / "practice-feedback-zh.png", (430, 350, 1505, 1030), angle=0, shadow=36)
    label(draw, (110, 390), "词库与选词")
    label(draw, (800, 340), "造句 · 批改 · 用法")
    label(draw, (1570, 375), "统计与连胜")

    draw.rounded_rectangle((75, 1002, 620, 1055), radius=18, fill=(255, 253, 248, 220), outline=LINE, width=2)
    draw.text((96, 1015), "开源 · AGPL-3.0-only · Windows · .NET 10", font=font(18), fill=GREEN_DEEP)
    return canvas


def sentence_flow() -> Image.Image:
    canvas = background("sentence.png")
    brand(canvas, x=90, y=60, compact=True)
    title_block(canvas, "把生词放进情境里", "AI 给出具体情境，但完整句子仍由你写下。", x=90, y=150)
    place_window(canvas, APP / "practice-session-empty-zh.png", (70, 350, 1270, 1015), angle=-1.2, shadow=30)
    place_window(canvas, APP / "practice-session-zh.png", (1030, 285, 1880, 900), angle=2.2, shadow=30)
    draw = ImageDraw.Draw(canvas)
    label(draw, (1060, 265), "独立造句")
    steps = [("01", "主动加入生词"), ("02", "生成具体情境"), ("03", "写下自己的句子")]
    y = 735
    for number, text in steps:
        draw.ellipse((1300, y, 1348, y + 48), fill=GREEN)
        draw.text((1312, y + 10), number, font=font(15, True), fill="white")
        draw.text((1368, y + 8), text, font=font(22, True), fill=INK)
        y += 70
    return canvas


def feedback() -> Image.Image:
    canvas = background("feedback.png")
    brand(canvas, x=90, y=60, compact=True)
    title_block(canvas, "不只告诉你哪里错", "还留下修改后的句子、更自然的表达，以及一行一个的常用搭配。", x=90, y=150)
    place_window(canvas, APP / "practice-feedback-zh.png", (90, 340, 1510, 1025), angle=-0.8, shadow=34)
    place_window(canvas, APP / "detected-words-dialog-zh.png", (1270, 455, 1880, 950), angle=2.5, shadow=30)
    draw = ImageDraw.Draw(canvas)
    label(draw, (1370, 420), "错词先确认，再加入")
    x = 1170
    for color, text in [(GREEN, "表达自然"), (BLUE, "正确，可优化"), (RED, "语法 / 用法错误")]:
        draw.ellipse((x, 310, x + 18, 328), fill=color)
        draw.text((x + 28, 301), text, font=font(18), fill=INK)
        x += 190
    return canvas


def statistics() -> Image.Image:
    canvas = background("statistics.png")
    brand(canvas, x=90, y=60, compact=True)
    title_block(canvas, "复习有依据，进步看得见", "根据实际作答安排复习；打卡、分数、掌握度和待强化词一页看清。", x=90, y=150)
    place_window(canvas, APP / "statistics-zh.png", (55, 330, 1290, 1015), angle=-1.1, shadow=32)
    place_window(canvas, APP / "statistics-lower-zh.png", (970, 360, 1880, 960), angle=2.0, shadow=30)
    draw = ImageDraw.Draw(canvas)
    metrics = [("4 天", "连续学习"), ("78.9", "平均分"), ("100%", "主动回忆覆盖"), ("1", "需要巩固")]
    x = 1050
    for value, caption in metrics:
        draw.rounded_rectangle((x, 255, x + 185, 335), radius=16, fill=(255, 253, 248, 235), outline=LINE, width=2)
        draw.text((x + 16, 267), value, font=font(26, True), fill=GREEN_DEEP)
        draw.text((x + 16, 305), caption, font=font(14), fill=MUTED)
        x += 200
    draw.text((1060, 980), "无需自己选择“好 / 中 / 差”", font=font(22, True), fill=GREEN_DEEP)
    return canvas


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    images = {
        "01-overview.png": hero(),
        "02-sentence-practice.png": sentence_flow(),
        "03-feedback-and-usage.png": feedback(),
        "04-statistics-and-review.png": statistics(),
    }
    for name, image in images.items():
        path = OUT / name
        image.convert("RGB").save(path, quality=96, subsampling=0)
        print(path)


if __name__ == "__main__":
    main()
