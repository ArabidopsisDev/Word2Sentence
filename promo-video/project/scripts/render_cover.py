from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / "project" / "content" / "cover.json"
CONFIG = ROOT / "project" / "config.json"


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size=size)


def main() -> None:
    cover = json.loads(CONTENT.read_text(encoding="utf-8"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    width, height = int(cover["width"]), int(cover["height"])
    sans = str(config["fonts"]["sans"])
    bold = str(config["fonts"]["sans_bold"])
    code = str(config["fonts"]["code"])
    image = Image.new("RGB", (width, height), "#F5F4F0")
    draw = ImageDraw.Draw(image)

    background = Image.open(ROOT / str(cover["background_image"])).convert("RGB")
    background = ImageOps.fit(background, (1220, 820), Image.Resampling.LANCZOS)
    wash = Image.new("RGB", background.size, "#F5F4F0")
    background = Image.blend(background, wash, 0.72)
    image.paste(background, (650, 130))

    draw.rounded_rectangle((90, 130, 570, 950), radius=48, fill="#2F6048")
    draw.text((330, 360), str(cover["logo_text"]), font=font(bold, 190), fill="white", anchor="mm")
    draw.line((170, 610, 490, 610), fill="#A8C5B3", width=3)
    draw.text((330, 685), str(cover["example_word"]), font=font(code, 48), fill="white", anchor="mm")
    draw.text((330, 755), str(cover["example_pattern"]), font=font(code, 25), fill="#DDE9E1", anchor="mm")

    draw.text((690, 185), str(cover["keyword"]), font=font(bold, 42), fill="#2F6048")
    title_font = font(bold, 128)
    for index, line in enumerate(list(cover["title_lines"])):
        draw.text((690, 330 + index * 150), str(line), font=title_font, fill="#242522")
    draw.line((695, 660, 1710, 660), fill="#2F6048", width=5)
    draw.text((700, 710), str(cover["subtitle"]), font=font(bold, 50), fill="#4F514C")

    output = ROOT / str(config["output"]["cover"])
    image.save(output, quality=95)
    thumb = image.resize((int(cover["thumbnail_width"]), int(cover["thumbnail_height"])), Image.Resampling.LANCZOS)
    thumb_path = ROOT / "renders" / "cover-320.png"
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    thumb.save(thumb_path)
    print(output)
    print(thumb_path)


if __name__ == "__main__":
    main()
