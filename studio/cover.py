"""Ảnh bìa có chữ to: lưới video trên trang trông như một series chuyên nghiệp, người xem bấm xem tiếp nhiều hơn."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

W, H = 1080, 1920


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if font.getlength(trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def make_cover(img_path: Path, out: Path, title: str, cfg: dict, episode: int | None = None,
               part: tuple[int, int] | None = None) -> Path:
    vcfg = cfg.get("video", {})
    font_path = vcfg.get("font", "C:/Windows/Fonts/arialbd.ttf")
    img = ImageOps.fit(Image.open(img_path).convert("RGB"), (W, H), Image.LANCZOS)

    # nền tối dần ở 45% dưới để chữ nổi
    shade = Image.new("L", (1, H))
    for y in range(H):
        a = max(0.0, (y - H * 0.5) / (H * 0.5))
        shade.putpixel((0, y), int(215 * a ** 1.3))
    img = Image.composite(Image.new("RGB", (W, H), (20, 12, 6)), img, shade.resize((W, H)))
    d = ImageDraw.Draw(img)

    # nhãn series trên cùng
    series = vcfg.get("series_name", "")
    tag = series + (f" • TẬP {episode}" if episode else "") + (f" • PHẦN {part[0]}/{part[1]}" if part else "")
    if tag.strip():
        f = ImageFont.truetype(font_path, 46)
        tw = f.getlength(tag)
        d.rounded_rectangle(((W - tw) / 2 - 28, 120, (W + tw) / 2 + 28, 196), radius=38, fill=(217, 130, 43))
        d.text(((W - tw) / 2, 132), tag, font=f, fill=(255, 255, 255))

    # tiêu đề to, tự co chữ cho vừa tối đa 4 dòng
    text = title.upper()
    size = 110
    while True:
        f = ImageFont.truetype(font_path, size)
        lines = _wrap(text, f, 960)
        if len(lines) <= 4 or size <= 64:
            break
        size -= 6
    lh = int(size * 1.18)
    y = H - 260 - lh * len(lines)
    for i, ln in enumerate(lines):
        x = (W - f.getlength(ln)) / 2
        color = (255, 214, 90) if i % 2 == 0 else (255, 255, 255)
        d.text((x, y + i * lh), ln, font=f, fill=color, stroke_width=8, stroke_fill=(30, 18, 8))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, quality=92)
    return out
