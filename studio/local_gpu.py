"""Chạy AI trên card đồ họa NVIDIA của máy: miễn phí, không giới hạn, không cần mạng sau khi tải model.

- Ảnh: SDXL (mặc định DreamShaper XL Turbo - hợp hoạt hình 3D) + IP-Adapter Plus để giữ đúng
  gương mặt nhân vật theo ảnh mẫu assets/characters/<KEY>.png.
- Cảnh cử động: LTX-Video image-to-video (mặc định) hoặc Wan 2.1 I2V (card lớn).
Tự chọn chế độ tiết kiệm VRAM theo card. Lần đầu tải model khoảng 20-30 GB.
Lỗi gì thì nơi gọi tự lùi về Pollinations.
"""
from __future__ import annotations

import gc
import time
from pathlib import Path

from PIL import Image

from .util import log

_img_pipe = None
_vid_pipe = None
_vid_name = None

NEG_IMG = ("worst quality, low quality, blurry, deformed, distorted face, extra fingers, extra limbs, text, watermark, "
           "logo, scary, creepy, dark, gloomy, nsfw")
NEG_VID = "worst quality, blurry, jittery, distorted, morphing face, flicker, inconsistent motion, text, watermark"


def info() -> dict:
    try:
        import torch
    except ImportError:
        return {"cuda": False, "reason": "chưa cài torch (chạy setup-gpu.bat)"}
    if not torch.cuda.is_available():
        return {"cuda": False, "reason": "torch không thấy card NVIDIA (thiếu driver hoặc cài nhầm torch bản CPU)",
                "torch": torch.__version__}
    p = torch.cuda.get_device_properties(0)
    return {"cuda": True, "name": p.name, "vram_gb": round(p.total_memory / 1024**3, 1), "torch": torch.__version__}


def _free() -> None:
    import torch

    gc.collect()
    torch.cuda.empty_cache()


def _low_vram() -> bool:
    return info().get("vram_gb", 0) < 16


# ======================= ẢNH =======================

def _load_img(cfg: dict):
    global _img_pipe, _vid_pipe
    if _img_pipe is not None:
        return _img_pipe
    import torch
    from diffusers import AutoPipelineForText2Image, DPMSolverMultistepScheduler
    from transformers import CLIPVisionModelWithProjection

    if _vid_pipe is not None:  # nhả model video trước cho đủ VRAM
        _unload_video()
    g = cfg.get("gpu", {})
    model = g.get("image_model", "Lykon/dreamshaper-xl-v2-turbo")
    log(f"  [GPU] nạp model ảnh {model} + IP-Adapter (lần đầu sẽ tải về)...")
    enc = CLIPVisionModelWithProjection.from_pretrained("h94/IP-Adapter", subfolder="models/image_encoder",
                                                        torch_dtype=torch.float16)
    pipe = AutoPipelineForText2Image.from_pretrained(model, image_encoder=enc, torch_dtype=torch.float16,
                                                     variant=g.get("image_variant") or None)
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(
        pipe.scheduler.config, use_karras_sigmas=True, algorithm_type="sde-dpmsolver++")
    pipe.load_ip_adapter("h94/IP-Adapter", subfolder="sdxl_models", weight_name="ip-adapter-plus_sdxl_vit-h.safetensors")
    if _low_vram():
        pipe.enable_model_cpu_offload()
    else:
        pipe.to("cuda")
    pipe.enable_vae_tiling()
    _img_pipe = pipe
    return pipe


def image(prompt: str, seed: int, cfg: dict, refs: list[Path] | None = None) -> Image.Image:
    import torch

    g = cfg.get("gpu", {})
    pipe = _load_img(cfg)
    ref = Image.open(refs[0]).convert("RGB") if refs else Image.new("RGB", (224, 224), (128, 128, 128))
    pipe.set_ip_adapter_scale(float(g.get("ip_adapter_scale", 0.55)) if refs else 0.0)
    t0 = time.time()
    out = pipe(
        prompt=prompt, negative_prompt=NEG_IMG, ip_adapter_image=ref,
        width=int(g.get("image_width", 832)), height=int(g.get("image_height", 1472)),
        num_inference_steps=int(g.get("image_steps", 8)), guidance_scale=float(g.get("image_guidance", 2.0)),
        generator=torch.Generator("cpu").manual_seed(seed),
    ).images[0]
    log(f"  [GPU] ảnh xong {time.time() - t0:.0f}s")
    return out


def _unload_image() -> None:
    global _img_pipe
    if _img_pipe is not None:
        _img_pipe = None
        _free()


# ======================= VIDEO =======================

def _unload_video() -> None:
    global _vid_pipe, _vid_name
    if _vid_pipe is not None:
        _vid_pipe, _vid_name = None, None
        _free()


def _load_vid(cfg: dict):
    global _vid_pipe, _vid_name
    g = cfg.get("gpu", {})
    model = g.get("video_model", "Lightricks/LTX-Video")
    if _vid_pipe is not None and _vid_name == model:
        return _vid_pipe
    _unload_image()  # nhả model ảnh cho đủ VRAM
    import torch

    log(f"  [GPU] nạp model video {model} (lần đầu sẽ tải về)...")
    if "wan" in model.lower():
        from diffusers import AutoencoderKLWan, WanImageToVideoPipeline
        from transformers import CLIPVisionModel

        enc = CLIPVisionModel.from_pretrained(model, subfolder="image_encoder", torch_dtype=torch.float32)
        vae = AutoencoderKLWan.from_pretrained(model, subfolder="vae", torch_dtype=torch.float32)
        pipe = WanImageToVideoPipeline.from_pretrained(model, vae=vae, image_encoder=enc, torch_dtype=torch.bfloat16)
    else:
        from diffusers import LTXImageToVideoPipeline

        pipe = LTXImageToVideoPipeline.from_pretrained(model, torch_dtype=torch.bfloat16)
    if _low_vram() or "wan" in model.lower():
        pipe.enable_model_cpu_offload()
    else:
        pipe.to("cuda")
    if hasattr(pipe, "vae") and hasattr(pipe.vae, "enable_tiling"):
        pipe.vae.enable_tiling()
    _vid_pipe, _vid_name = pipe, model
    return pipe


def video(img_path: Path, prompt: str, out: Path, seconds: float, cfg: dict, seed: int = 42) -> Path:
    import torch
    from diffusers.utils import export_to_video

    g = cfg.get("gpu", {})
    pipe = _load_vid(cfg)
    wan = "wan" in (_vid_name or "").lower()
    fps = 16 if wan else 24
    w, h = (480, 832) if wan else (int(g.get("video_width", 512)), int(g.get("video_height", 896)))
    if not wan and info().get("vram_gb", 0) < 12 and "video_width" not in g:
        w, h = 384, 672  # card nhỏ: giảm độ phân giải để khỏi tràn VRAM
    n = int(seconds * fps)
    n = (n // 4) * 4 + 1 if wan else (n // 8) * 8 + 1  # Wan: 4k+1 khung, LTX: 8k+1 khung
    img = Image.open(img_path).convert("RGB").resize((w, h), Image.LANCZOS)
    t0 = time.time()
    frames = pipe(
        image=img, prompt=prompt, negative_prompt=NEG_VID, width=w, height=h, num_frames=n,
        num_inference_steps=int(g.get("video_steps", 30 if not wan else 30)),
        guidance_scale=float(g.get("video_guidance", 3.0 if not wan else 5.0)),
        generator=torch.Generator("cpu").manual_seed(seed),
    ).frames[0]
    export_to_video(frames, str(out), fps=fps)
    log(f"  [GPU] clip {seconds:.0f}s xong sau {time.time() - t0:.0f}s")
    return out


def release() -> None:
    _unload_image()
    _unload_video()
