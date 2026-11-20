"""Cảnh kết cuối mỗi video: bé Bin vẫy tay + chữ mời theo dõi + lời mời đọc bằng giọng người kể.

Ảnh cảnh kết được tạo MỘT lần (assets/outro/outro.png) rồi dùng lại cho mọi video.
Có thể tự thay bằng ảnh của bạn: bỏ file outro.png (dọc 9:16) vào assets/outro/.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from .util import ASSETS, log

OUTRO_DIR = ASSETS / "outro"
PROMPT = ("{BIN} standing in front of an old village house gate, waving goodbye at the camera with one hand raised high, "
          "big happy smile, full body in the lower half of the frame, empty warm sky in the upper half, golden sunset light")


def _fallback_from_ref() -> Path | None:
    """Không tạo được ảnh mới thì ghép ảnh mẫu Bin lên nền ấm."""
    ref = ASSETS / "characters" / "BIN.png"
    if not ref.exists():
        return None
    W, H = 1080, 1920
    bg = Image.new("RGB", (W, H), (250, 226, 186))
    grad = Image.new("L", (1, H))
    for y in range(H):
        grad.putpixel((0, y), int(255 * y / H))
    warm = Image.new("RGB", (W, H), (236, 170, 96))
    bg = Image.composite(warm, bg, grad.resize((W, H)))
    bin_img = Image.open(ref).convert("RGB")
    # ảnh mẫu nền trơn -> cắt hình tròn mềm đặt giữa nửa dưới
    size = 900
    bin_img = bin_img.resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((40, 40, size - 40, size - 40), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(30))
    bg.paste(bin_img, ((W - size) // 2, H - size - 260), mask)
    out = OUTRO_DIR / "outro.png"
    bg.save(out)
    return out


def outro_image(cfg: dict) -> Path | None:
    OUTRO_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTRO_DIR / "outro.png"
    if out.exists():
        return out
    from . import images, polli

    if polli.key():
        try:
            log("  Tạo ảnh cảnh kết (chỉ lần đầu)...")
            img = images._pollinations(PROMPT, 2468, cfg).convert("RGB")
            images.finish(img, False).save(out)
            return out
        except Exception as e:
            log(f"  tạo ảnh cảnh kết lỗi ({e}), dùng ảnh mẫu Bin")
    return _fallback_from_ref()


def scene(cfg: dict) -> dict | None:
    """Cảnh kết dạng 1 'scene' để ghép vào cuối kịch bản (đã có sẵn ảnh, không cần tạo)."""
    ocfg = cfg.get("video", {}).get("outro", {})
    if not ocfg.get("enabled", True):
        return None
    img = outro_image(cfg)
    if not img:
        log("  (bỏ qua cảnh kết: chưa có ảnh mẫu Bin)")
        return None
    return {
        "_outro": True,
        "text": ocfg.get("voice", "Theo dõi Hạt Gạo Quê để xem tập sau nha!"),
        "_cta": ocfg.get("text", "Theo dõi HẠT GẠO QUÊ\\Nđể xem tập sau nhé!"),
        "_image": str(img),
        "images": [],
    }
