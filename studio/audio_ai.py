"""Dùng AI sáng tác nhạc nền + âm thanh không khí cho kênh (tạo 1 lần, dùng lại cho mọi video).

Nhạc: Google Lyria (clip 30 giây, ~0,04 USD/bài). Âm thanh: ElevenLabs Sound Effects (~0,002 USD/giây).
Cần POLLINATIONS_TOKEN và tài khoản có số dư trả phí.
"""
from __future__ import annotations

import urllib.parse
from pathlib import Path

import requests

from . import polli
from .util import ASSETS, log

MUSIC = {
    "nho_nhe_guitar": "gentle nostalgic acoustic guitar and soft piano, warm childhood memories in a Vietnamese village, "
                      "slow and cozy, instrumental, no vocals",
    "vui_nhon_ukulele": "playful bouncy ukulele, glockenspiel and light claps, cheerful cute cartoon kid adventure, "
                        "instrumental, no vocals",
    "sao_truc_que": "heartwarming melody on bamboo flute with soft strings and gentle percussion, Vietnamese countryside "
                    "folk feeling, instrumental, no vocals",
    "piano_ong_ba": "tender emotional lofi piano, grandparents love, warm and slightly bittersweet, instrumental, no vocals",
    "tinh_nghich_pizzicato": "light comedic pizzicato strings and woodblock, mischievous little kid sneaking around, "
                             "cartoon comedy, instrumental, no vocals",
    "trung_thu_tet": "festive warm folk melody with soft drums and bamboo flute, lantern festival and lunar new year "
                     "joy, instrumental, no vocals",
}

SFX = {
    "ve_sau": "loud cicadas chirping on a hot summer noon in a quiet countryside village, continuous ambience",
    "mua": "gentle steady rain falling on a tiled roof and banana leaves, cozy ambience",
    "bep_cui": "crackling wood fire in an outdoor clay stove, soft pops and embers, ambience",
    "dem_que": "countryside night ambience with crickets and frogs, calm and peaceful",
    "san_truong": "distant children laughing and playing in a schoolyard, light ambience",
    "lang_que": "peaceful village morning, roosters crowing far away, birds chirping, light breeze",
    "gio_dong": "soft wind blowing over open rice fields, rustling grass, calm ambience",
    "pho_cu": "old small town street ambience, distant bicycle bells, light chatter, calm",
}

PRICE = {"music": 0.04, "sfx_per_sec": 0.002}


def _gen(prompt: str, out: Path, params: dict) -> None:
    url = f"{polli.GEN}/audio/" + urllib.parse.quote(prompt, safe="")
    r = requests.get(url, params=params, headers=polli._auth(), timeout=600)
    if not (r.ok and r.headers.get("content-type", "").startswith("audio")):
        raise RuntimeError(f"{r.status_code}: {r.text[:300]}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(r.content)


def estimate(music: list[str], sfx: list[str], sfx_sec: int = 20) -> float:
    return len(music) * PRICE["music"] + len(sfx) * sfx_sec * PRICE["sfx_per_sec"]


def generate(music: list[str] | None = None, sfx: list[str] | None = None, sfx_sec: int = 20,
             skip_existing: bool = True) -> dict:
    music = list(MUSIC) if music is None else music
    sfx = list(SFX) if sfx is None else sfx
    done, failed, cost = [], [], 0.0
    for name in music:
        out = ASSETS / "music" / f"ai_{name}.mp3"
        if skip_existing and out.exists():
            continue
        try:
            _gen(MUSIC[name], out, {"model": "google/lyria-3-clip-preview"})
            cost += PRICE["music"]
            done.append(out.name)
            log(f"  nhạc '{name}' xong")
        except Exception as e:
            failed.append(f"nhạc {name}: {e}")
            log(f"  nhạc '{name}' lỗi: {e}")
            if "402" in str(e):
                break  # hết tiền: dừng luôn
    for name in sfx:
        out = ASSETS / "sfx" / f"{name}.mp3"
        if skip_existing and any((ASSETS / "sfx").glob(f"{name}.*")):
            continue
        try:
            _gen(SFX[name], out, {"model": "elevenlabs/eleven-text-to-sound-v2", "duration": sfx_sec, "loop": "true"})
            cost += sfx_sec * PRICE["sfx_per_sec"]
            done.append(out.name)
            log(f"  âm thanh '{name}' xong")
        except Exception as e:
            failed.append(f"âm thanh {name}: {e}")
            log(f"  âm thanh '{name}' lỗi: {e}")
            if "402" in str(e):
                break
    log(f"Âm thanh AI: tạo {len(done)} file, ~{cost:.2f} USD; lỗi {len(failed)}")
    return {"done": done, "failed": failed, "cost": cost}
