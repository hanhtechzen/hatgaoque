"""Tạo ảnh minh họa: Stable Diffusion trên máy (nếu có NVIDIA) hoặc Pollinations (miễn phí, online)."""
from __future__ import annotations

import hashlib
import os
import random
import time
import urllib.parse
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps

from .util import ASSETS, DATA, log

W, H = 1080, 1920

# Phong cách ảnh: chọn bằng "images.style" trong config.json
STYLES = {
    # Hoạt hình 3D kiểu phim chiếu rạp: nhân vật mũm mĩm, mắt to, nắng vàng ấm (kiểu đang thịnh hành trên TikTok)
    # Model miễn phí (sana) chỉ ra chất 3D khi có cụm "3D Pixar style"; giữ ngắn để nó không bỏ qua hành động
    "hoat_hinh_3d": (
        "3D Pixar style animation movie still, medium wide shot showing full bodies and surroundings, "
        "cute chubby cartoon characters with big eyes, warm golden light, 1990s Vietnamese village, heartwarming"
    ),
    # Ảnh chụp phim xưa nhưng tươi sáng (dùng chung với color_grade "xua_sang")
    "anh_xua_sang": (
        "bright nostalgic 1990s film photograph, cute chubby happy Vietnamese kids with big smiles, "
        "sunny warm daylight, rural Vietnamese village, faded warm pastel colors, cheerful"
    ),
    # Tranh minh họa kiểu truyện thiếu nhi: trẻ con dễ thương, tươi sáng, không bị "ma" như ảnh AI giả thật
    "minh_hoa": (
        "warm hand-painted storybook illustration, soft gouache and watercolor, "
        "adorable cheerful Vietnamese children with round chubby faces, big bright smiles, sparkling eyes, rosy cheeks, "
        "neat colorful simple 1990s Vietnamese clothes, rural Vietnam village in the 1990s, "
        "bright warm golden light, vivid cheerful colors, cozy joyful nostalgic mood, detailed background, "
        "high quality children's picture book art"
    ),
    # Ảnh chụp tươi sáng
    "anh_that": (
        "bright cheerful candid photograph, rural Vietnam village in the 1990s, "
        "cute happy Vietnamese children with round faces, big genuine smiles, laughing, rosy cheeks, "
        "neat colorful simple 1990s Vietnamese clothes, bright sunny daylight, vivid warm colors, "
        "joyful nostalgic mood, Kodak Gold film look, sharp focus, high quality"
    ),
}
NEGATIVE = (
    "nudity, shirtless, scary, creepy, horror, ghost, sad, crying, dark, gloomy, empty eyes, "
    "text, letters, watermark, logo, deformed, distorted face, extra fingers, modern skyscraper, smartphone"
)

# Những cụm từ khiến ảnh u ám / như ma -> đổi sang tươi sáng
_BRIGHTEN = [
    (r",?\s*seen from (behind|above|far away)", ""),
    (r"\bsilhouettes? of\b", ""),
    (r"\bsilhouettes?\b", "happy children"),
    (r"\bdim(ly lit)?\b", "warm"),
    (r"\bdark\b", "cozy warmly lit"),
    (r"\bdusty\b", "sunlit"),
    (r"\bempty\b", "peaceful"),
    (r"\bharsh\b", "bright"),
    (r"\bsleeping\b", "peacefully sleeping, smiling"),
    (r"\bonly moonlight\b", "soft warm lantern light"),
    (r"\bat night\b", "in the evening with warm golden lantern light"),
    (r"\bsad\b", "nostalgic"),
]

_pipe = None
_COST = {"images": 0.0}  # chi phí USD (pollen) của video đang làm


def style_text(cfg: dict) -> str:
    return STYLES.get(cfg["images"].get("style", "hoat_hinh_3d"), STYLES["hoat_hinh_3d"])


CHAR_FILE = DATA / "characters.json"


def characters() -> dict:
    """Nhân vật cố định của kênh (data/characters.json). Trong mô tả ảnh viết {BIN}, {BA}, {ONG}..."""
    import json

    if not CHAR_FILE.exists():
        return {}
    data = json.loads(CHAR_FILE.read_text(encoding="utf-8"))
    return {k: (v if isinstance(v, dict) else {"look": v}) for k, v in data.items()}


def save_characters(chars: dict) -> None:
    import json

    CHAR_FILE.write_text(json.dumps(chars, ensure_ascii=False, indent=2), encoding="utf-8")


def char_keys(prompt: str) -> list[str]:
    import re

    return [k for k in dict.fromkeys(re.findall(r"\{([A-Z_]+)\}", prompt)) if k in characters()]


def ref_urls(keys: list[str]) -> list[str]:
    """URL ảnh mẫu của nhân vật (để model vẽ đúng mặt). Tự tải lại nếu link sắp hết hạn 30 ngày."""
    import datetime as dt

    from . import polli

    chars = characters()
    urls, changed = [], False
    for k in keys:
        c = chars.get(k, {})
        ref = ASSETS / "characters" / f"{k}.png"
        if not ref.exists():
            continue
        fresh = c.get("ref_uploaded") and (dt.date.today() - dt.date.fromisoformat(c["ref_uploaded"])).days < 25
        if not (c.get("ref_url") and fresh):
            c["ref_url"] = polli.upload(ref)
            c["ref_uploaded"] = dt.date.today().isoformat()
            changed = True
        urls.append(c["ref_url"])
    if changed:
        save_characters(chars)
    return urls


def brighten(prompt: str) -> str:
    import re

    for key, c in characters().items():
        prompt = prompt.replace("{" + key + "}", f"({c['look']})")
    for pat, rep in _BRIGHTEN:
        prompt = re.sub(pat, rep, prompt, flags=re.IGNORECASE)
    if "child" in prompt.lower() or "kid" in prompt.lower():
        prompt += ", children smiling happily"
    return re.sub(r"\s{2,}", " ", prompt).strip(" ,")


# ---------- hậu kỳ: cắt khung 9:16 + chỉnh màu ấm, tươi ----------

def _grade_xua_sang(img: Image.Image) -> Image.Image:
    """Tông "ảnh xưa mà sáng": ngả vàng ấm như ảnh phim cũ, nâng vùng tối (không bị u tối),
    giảm bão hòa nhẹ cho màu phai pastel, thêm chút hào quang mềm. Không viền tối, không nhiễu."""
    sepia = ImageOps.colorize(ImageOps.grayscale(img), black=(52, 38, 28), white=(255, 246, 228))
    img = Image.blend(img, sepia, 0.22)
    # Nâng vùng tối: đen -> nâu sáng (màu "phai" của ảnh cũ) thay vì tối đặc
    img = img.point(lambda v: int(24 + v * (250 - 24) / 255))
    r, g, b = img.split()
    r = r.point(lambda v: min(255, int(v * 1.04 + 6)))
    g = g.point(lambda v: min(255, int(v * 1.01 + 3)))
    b = b.point(lambda v: int(v * 0.90))
    img = Image.merge("RGB", (r, g, b))
    img = ImageEnhance.Color(img).enhance(0.88)
    img = ImageEnhance.Brightness(img).enhance(1.06)
    # Không thêm hào quang mờ: làm mặt nhân vật trông như "ma"
    return img


def finish(img: Image.Image, retro) -> Image.Image:
    """Đưa về 1080x1920, làm nét (ảnh nhỏ phóng to dễ bị mờ/sạn), chỉnh màu. Không thêm nhiễu.
    retro: False / True (ấm nhẹ) / "xua_sang" (ảnh xưa mà sáng)."""
    img = img.convert("RGB")
    small = img.width < W * 0.9
    img = ImageOps.fit(img, (W, H), Image.LANCZOS)
    if small:
        img = img.filter(ImageFilter.UnsharpMask(radius=2.2, percent=70, threshold=3))
    else:
        img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=40, threshold=3))
    if not retro:
        return img
    if retro == "xua_sang":
        return _grade_xua_sang(img)
    r, g, b = img.split()
    r = r.point(lambda v: min(255, int(v * 1.03 + 4)))
    b = b.point(lambda v: int(v * 0.96))
    img = Image.merge("RGB", (r, g, b))
    img = ImageEnhance.Brightness(img).enhance(1.04)
    return ImageEnhance.Color(img).enhance(1.06)


# ---------- nguồn ảnh ----------

def _has_cuda() -> bool:
    try:
        import torch

        return torch.cuda.is_available()
    except Exception:
        return False


def _local(prompt: str, seed: int, cfg: dict) -> Image.Image:
    global _pipe
    import torch
    from diffusers import AutoPipelineForText2Image

    icfg = cfg["images"]
    if _pipe is None:
        log(f"  Đang nạp model {icfg['local_model']} (lần đầu sẽ tải ~7GB)...")
        _pipe = AutoPipelineForText2Image.from_pretrained(icfg["local_model"], torch_dtype=torch.float16)
        vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
        if vram_gb < 11:
            _pipe.enable_model_cpu_offload()
        else:
            _pipe.to("cuda")
    gen = torch.Generator("cuda").manual_seed(seed)
    return _pipe(
        prompt=f"{brighten(prompt)}, {style_text(cfg)}",
        negative_prompt=NEGATIVE,
        width=768,
        height=1344,
        num_inference_steps=int(icfg.get("local_steps", 28)),
        guidance_scale=float(icfg.get("local_guidance", 5.0)),
        generator=gen,
    ).images[0]


def _pollinations(prompt: str, seed: int, cfg: dict) -> Image.Image:
    icfg = cfg["images"]
    # Phong cách đặt TRƯỚC hành động để model không bỏ qua; không liệt kê "cần tránh" (model sẽ vẽ ra)
    full = f"{style_text(cfg)}. Scene: {brighten(prompt)}. No text."
    token = os.environ.get("POLLINATIONS_TOKEN", "").strip()
    if token:
        from . import polli

        refs = ref_urls(char_keys(prompt))
        if refs:
            # Có ảnh mẫu nhân vật -> FLUX Klein vẽ đúng mặt Bin/ông/bà ở mọi cảnh
            full = ("Keep the exact same characters as in the reference images (same face, hair, clothes). " + full)
            model = icfg.get("ref_model", "klein")
        else:
            model = icfg.get("pollinations_model", "zimage")
        _COST["images"] += float(icfg.get("price", {}).get(model, 0.005))
        return polli.image(full, model=model, width=W, height=H, seed=seed, refs=refs[:4])
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(full, safe="")
    headers = {}
    params = {"width": W, "height": H, "seed": seed, "nologo": "true", "private": "true"}
    last = None
    for attempt in range(4):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=240)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
                img = Image.open(BytesIO(r.content)).convert("RGB")
                if not token:
                    # Bản miễn phí đóng logo ở góc dưới -> cắt bỏ 7% phía dưới
                    img = img.crop((0, 0, img.width, int(img.height * 0.93)))
                return img
            last = f"HTTP {r.status_code}: {r.text[:200]}"
        except requests.RequestException as e:
            last = str(e)
        log(f"  Pollinations lỗi (lần {attempt + 1}): {last}")
        time.sleep(15 * (attempt + 1))
    raise RuntimeError(f"Pollinations không trả ảnh: {last}")


def _folder_images(script_id: str) -> list[Path]:
    folder = ASSETS / "images" / script_id
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})


def generate(script: dict, work: Path, cfg: dict) -> list[Path]:
    """Trả về danh sách ảnh cho từng cảnh (mỗi cảnh 1-2 ảnh)."""
    icfg = cfg["images"]
    retro = icfg.get("color_grade", icfg.get("retro_filter", True))
    prompts = [list(s.get("images") or [s.get("image_prompt", "")])[:3] for s in script["scenes"]]
    flat = [(i, j, p) for i, ps in enumerate(prompts) for j, p in enumerate(ps)]
    out: list[list[Path]] = [[] for _ in prompts]

    # Ảnh bạn tự bỏ vào assets/images/<id>/ luôn được ưu tiên
    own = _folder_images(script["id"])
    provider = icfg.get("provider", "auto")
    if own and provider in ("auto", "folder"):
        log(f"Ảnh: dùng {len(own)} ảnh có sẵn trong assets/images/{script['id']}")
        for k, (i, j, _) in enumerate(flat):
            p = work / f"img_{i:02d}_{j}.jpg"
            finish(Image.open(own[k % len(own)]), retro).save(p, quality=92)
            out[i].append(p)
        return out
    if provider == "folder":
        raise RuntimeError(f"Không có ảnh trong assets/images/{script['id']}")

    if provider == "auto":
        provider = "local" if _has_cuda() else "pollinations"
    if provider == "local" and not _has_cuda():
        log("  Không thấy GPU NVIDIA/torch CUDA -> chuyển sang Pollinations")
        provider = "pollinations"

    fn = _local if provider == "local" else _pollinations
    has_token = bool(os.environ.get("POLLINATIONS_TOKEN", "").strip())
    cache = DATA / "image_cache"
    cache.mkdir(parents=True, exist_ok=True)
    tier = "key" if has_token else "free"
    log(f"Ảnh: cần {len(flat)} ảnh, tạo bằng {provider} ({tier})")
    _COST["images"] = 0.0
    need_wait = False
    video_seed = int(hashlib.sha1(script["id"].encode()).hexdigest()[:6], 16)
    for k, (i, j, prompt) in enumerate(flat):
        key = hashlib.sha1(f"{provider}|{tier}|{style_text(cfg)}|{brighten(prompt)}".encode("utf-8")).hexdigest()[:16]
        cached = cache / f"{key}.jpg"
        if cached.exists():
            img = Image.open(cached)
        else:
            if need_wait and provider == "pollinations":
                # Không có token: giới hạn miễn phí 1 ảnh / 45 giây
                time.sleep(3 if has_token else float(icfg.get("pollinations_delay_sec", 46)))
            img = fn(prompt, video_seed + k, cfg).convert("RGB")  # cùng seed cả video -> nhân vật giống nhau hơn
            img.save(cached, quality=95)
            need_wait = True
        p = work / f"img_{i:02d}_{j}.jpg"
        finish(img, retro).save(p, quality=92)
        out[i].append(p)
        log(f"  ảnh {k + 1}/{len(flat)} xong")
    script["_cost_images"] = _COST["images"]
    return out


def make_character_refs(cfg: dict, only: list[str] | None = None) -> list[Path]:
    """Vẽ ảnh mẫu (toàn thân, nền trơn) cho từng nhân vật -> assets/characters/<KEY>.png.
    Các ảnh sau sẽ dùng ảnh mẫu này để giữ đúng gương mặt nhân vật."""
    from . import polli

    folder = ASSETS / "characters"
    folder.mkdir(parents=True, exist_ok=True)
    chars = characters()
    made = []
    for k, c in chars.items():
        if only and k not in only:
            continue
        prompt = (f"{style_text(cfg)}. Character reference sheet: {c['look']}. Full body, standing, "
                  "facing the camera, friendly smile, only ONE character alone, no other people, "
                  "plain light warm beige background, no text.")
        img = polli.image(prompt, model=cfg["images"].get("pollinations_model", "zimage"),
                          width=1024, height=1024, seed=1234)
        path = folder / f"{k}.png"
        img.save(path)
        c.pop("ref_url", None)
        c.pop("ref_uploaded", None)
        made.append(path)
        log(f"  ảnh mẫu nhân vật {k} -> {path}")
    save_characters(chars)
    return made
