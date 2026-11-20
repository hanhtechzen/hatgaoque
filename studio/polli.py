"""Gọi Pollinations (gen.pollinations.ai) có API key: tạo ảnh, tải ảnh lên, tạo video từ ảnh."""
from __future__ import annotations

import os
import time
import urllib.parse
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

from .util import log

GEN = "https://gen.pollinations.ai"
MEDIA = "https://media.pollinations.ai"


def key() -> str:
    return os.environ.get("POLLINATIONS_TOKEN", "").strip()


def _auth() -> dict:
    k = key()
    if not k:
        raise RuntimeError("Chưa có POLLINATIONS_TOKEN trong .env")
    return {"Authorization": f"Bearer {k}"}


def upload(path: Path) -> str:
    """Tải file lên kho media của Pollinations (lưu 30 ngày), trả về URL công khai."""
    with open(path, "rb") as f:
        r = requests.post(f"{MEDIA}/upload", headers=_auth(), files={"file": (path.name, f)}, timeout=180)
    if r.status_code >= 400:
        raise RuntimeError(f"Upload lỗi {r.status_code}: {r.text[:300]}")
    data = r.json()
    url = data.get("url") or (f"{MEDIA}/{data['id']}" if data.get("id") else None)
    if not url:
        raise RuntimeError(f"Upload không trả URL: {str(data)[:300]}")
    return url


def image(prompt: str, *, model: str, width: int, height: int, seed: int, refs: list[str] | None = None) -> Image.Image:
    params = {"model": model, "width": width, "height": height, "seed": seed, "nologo": "true", "private": "true"}
    if refs:
        params["image"] = "|".join(refs)
    url = f"{GEN}/image/" + urllib.parse.quote(prompt, safe="")
    last = None
    for attempt in range(4):
        try:
            r = requests.get(url, params=params, headers=_auth(), timeout=300)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
                return Image.open(BytesIO(r.content)).convert("RGB")
            last = f"HTTP {r.status_code}: {r.text[:300]}"
            if r.status_code in (401, 402, 403):
                break  # sai key / hết tiền: thử lại vô ích
        except requests.RequestException as e:
            last = str(e)
        log(f"  Pollinations ảnh lỗi (lần {attempt + 1}): {last}")
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Pollinations không trả ảnh: {last}")


def video(prompt: str, start_image_url: str, out: Path, *, model: str, duration: int, resolution: str,
          aspect: str = "9:16", timeout_sec: int = 900) -> Path:
    """Tạo video từ ảnh đầu (start frame). Chạy dạng job bất đồng bộ rồi tải kết quả."""
    params = {"model": model, "duration": duration, "resolution": resolution, "aspectRatio": aspect,
              "image": start_image_url, "private": "true"}
    url = f"{GEN}/video/" + urllib.parse.quote(prompt, safe="")
    r = requests.get(url, params=params, headers={**_auth(), "Prefer": "respond-async"}, timeout=300)
    if r.status_code == 200 and r.headers.get("content-type", "").startswith("video"):
        out.write_bytes(r.content)  # kết quả có sẵn trong cache
        return out
    if r.status_code != 202:
        raise RuntimeError(f"Tạo video lỗi {r.status_code}: {r.text[:300]}")
    job = r.json()
    job_id = job["id"]
    t0 = time.time()
    while time.time() - t0 < timeout_sec:
        time.sleep(float(r.headers.get("Retry-After", 5)) if r is not None else 5)
        s = requests.get(f"{GEN}/v1/jobs/{job_id}", headers=_auth(), timeout=60)
        st = s.json().get("status") if s.ok else None
        if st == "succeeded":
            res = requests.get(f"{GEN}/v1/jobs/{job_id}/result", headers=_auth(), timeout=300)
            if res.ok:
                out.write_bytes(res.content)
                return out
            raise RuntimeError(f"Tải video lỗi {res.status_code}: {res.text[:200]}")
        if st in ("failed", "canceled", "cancelled"):
            raise RuntimeError(f"Tạo video thất bại: {s.text[:300]}")
        r = None
    raise RuntimeError("Tạo video quá thời gian chờ")
