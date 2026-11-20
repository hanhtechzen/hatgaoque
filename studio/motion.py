"""Biến vài ảnh quan trọng thành clip chuyển động thật (nhân vật chạy, cười, vẫy tay...) bằng AI video.

Chỉ chạy khi có POLLINATIONS_TOKEN. Số clip tự tính theo ngân sách mỗi video (config: budget_usd_per_video).
"""
from __future__ import annotations

import math
import re
from pathlib import Path

from . import polli
from .images import brighten
from .util import log

ACTION = re.compile(
    r"\b(run|running|jump|jumping|dance|dancing|cheer|cheering|clap|clapping|laugh|laughing|march|marching|"
    r"wave|waving|spring|springing|tiptoe|tiptoeing|lick|licking|fan|fanning|hug|hugging|fly|flying|play|playing)\b",
    re.I,
)


def pick_scenes(script: dict, n: int) -> list[int]:
    """Ưu tiên cảnh có 'motion' trong kịch bản, sau đó cảnh mở đầu, rồi cảnh có hành động."""
    scenes = script["scenes"]
    chosen = [i for i, s in enumerate(scenes) if s.get("motion")]
    for i in [0] + [i for i, s in enumerate(scenes) if ACTION.search(" ".join(s.get("images", [])))]:
        if i not in chosen:
            chosen.append(i)
    return chosen[:n]


def _prompt(s: dict) -> str:
    action = s.get("motion") or brighten(s["images"][0])
    return (f"3D animated cartoon, {action}. Lively natural character animation, expressive faces, "
            "smooth movement, gentle camera motion, keep characters and style exactly as in the image.")


def _animate_local(script: dict, images: list[list[Path]], work: Path, cfg: dict,
                   wavs: list[Path] | None = None) -> dict[int, Path]:
    """Card NVIDIA của máy: làm chuyển động cho (gần như) MỌI cảnh, miễn phí."""
    from . import local_gpu

    mcfg = cfg.get("motion", {})
    n = int(mcfg.get("max_shots_local", 6))
    sec = float(mcfg.get("clip_sec_local", 4))
    out: dict[int, Path] = {}
    log(f"Chuyển động [GPU]: làm tối đa {n} cảnh, mỗi cảnh {sec:.0f}s")
    for i in pick_scenes(script, n):
        dur = sec
        if wavs and i < len(wavs):  # clip dài vừa đúng câu thoại của cảnh (2.5-6 giây)
            from .tts import SAMPLE_RATE, wav_samples

            dur = min(6.0, max(2.5, wav_samples(wavs[i]) / SAMPLE_RATE + 0.5))
        try:
            out[i] = local_gpu.video(images[i][0], _prompt(script["scenes"][i]), work / f"motion_{i:02d}.mp4",
                                     dur, cfg, seed=1000 + i)
        except Exception as e:
            log(f"  [GPU] clip cảnh {i + 1} lỗi, dùng ảnh tĩnh: {e}")
            if "out of memory" in str(e).lower():
                log("  [GPU] hết VRAM - giảm gpu.video_width/height hoặc clip_sec_local trong config.json")
                break
    local_gpu.release()
    script["_cost_motion"] = 0.0
    log(f"Chuyển động [GPU]: {len(out)} clip")
    return out


def animate(script: dict, images: list[list[Path]], work: Path, cfg: dict,
            wavs: list[Path] | None = None) -> dict[int, Path]:
    """Trả về {chỉ số cảnh: file mp4} cho các cảnh được làm chuyển động."""
    mcfg = cfg.get("motion", {})
    if not mcfg.get("enabled"):
        return {}
    if mcfg.get("provider", "auto") in ("auto", "local"):
        from . import local_gpu

        if local_gpu.info().get("cuda"):
            return _animate_local(script, images, work, cfg, wavs)
        if mcfg.get("provider") == "local":
            log("Chuyển động: không thấy card NVIDIA -> dùng Pollinations")
    if not polli.key():
        return {}
    price = float(mcfg.get("price_per_sec", 0.0099225))
    clip_sec = int(mcfg.get("clip_sec", 4))
    budget = float(cfg.get("budget_usd_per_video", 0.18)) - float(script.get("_cost_images", 0.0))
    n = min(int(mcfg.get("max_shots", 3)), max(0, math.floor(budget / (price * clip_sec) + 1e-9)))
    if n <= 0:
        log("Chuyển động: hết ngân sách cho video này, dùng ảnh tĩnh")
        return {}

    out: dict[int, Path] = {}
    spent = 0.0
    for i in pick_scenes(script, n):
        s = script["scenes"][i]
        img = images[i][0]
        prompt = _prompt(s)
        try:
            url = polli.upload(img)
            mp4 = polli.video(prompt, url, work / f"motion_{i:02d}.mp4", model=mcfg.get("model", "seedance-pro"),
                              duration=clip_sec, resolution=mcfg.get("resolution", "480p"))
            out[i] = mp4
            spent += price * clip_sec
            log(f"  clip chuyển động cảnh {i + 1} xong")
        except Exception as e:
            log(f"  clip chuyển động cảnh {i + 1} lỗi, dùng ảnh tĩnh: {e}")
    script["_cost_motion"] = spent
    log(f"Chuyển động: {len(out)} clip, ~{spent:.3f} USD")
    return out
