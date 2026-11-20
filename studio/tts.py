"""Giọng đọc tiếng Việt miễn phí.

- "vieneu": VieNeu-TTS chạy trên máy (CPU), giọng tự nhiên, có thể nhân bản giọng của bạn.
- "edge":   edge-tts (giọng Microsoft) - dự phòng khi VieNeu lỗi.
"""
from __future__ import annotations

import asyncio
import re
import time
import wave
from pathlib import Path

from .util import ROOT, ffmpeg_exe, log, run

SAMPLE_RATE = 44100
_vieneu = None

# Cắt khoảng lặng đầu/cuối để nhịp video gọn
TRIM = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
        "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse")


def _to_wav(src: Path, dst: Path, tempo: float = 1.0) -> None:
    af = TRIM + (f",atempo={tempo:.3f}" if abs(tempo - 1.0) > 0.005 else "")
    run([ffmpeg_exe(), "-y", "-i", src, "-af", af, "-ac", "1", "-ar", SAMPLE_RATE, "-sample_fmt", "s16", dst])


# ---------- VieNeu ----------

def _vieneu_engine():
    global _vieneu
    if _vieneu is None:
        from vieneu import Vieneu

        log("  Đang nạp VieNeu-TTS (lần đầu sẽ tải model)...")
        _vieneu = Vieneu()
        clone = ROOT / "assets" / "voice" / "my_voice.wav"
        if clone.exists():
            _vieneu.add_voice("__my_voice__", str(clone))
            log("  Dùng giọng nhân bản từ assets/voice/my_voice.wav")
    return _vieneu


def _vieneu_say(text: str, out: Path, cfg: dict, speaker: str | None = None) -> None:
    eng = _vieneu_engine()
    clone = ROOT / "assets" / "voice" / "my_voice.wav"
    voice = "__my_voice__" if clone.exists() else cfg.get("vieneu_voice", "Ngọc Huyền")
    if speaker and speaker in cfg.get("speakers", {}):
        voice = cfg["speakers"][speaker]["voice"]  # lời thoại của ông/bà dùng giọng riêng
    audio = eng.infer(text, voice=voice)
    eng.save(audio, str(out))


# ---------- MAI-Voice (Microsoft, qua Pollinations; dùng được phần miễn phí hằng ngày) ----------

def _mai_say(text: str, out: Path, cfg: dict, speaker: str | None = None) -> None:
    import urllib.parse

    import requests

    from . import polli

    mcfg = cfg.get("mai", {})
    voice = mcfg.get("voice", "vi-VN-Grant")
    if speaker and speaker in mcfg.get("speakers", {}):
        voice = mcfg["speakers"][speaker]
    sp = cfg.get("speakers", {}).get(speaker, {}) if speaker else {}
    if sp.get("provider") == "mai" and sp.get("voice"):
        voice = sp["voice"]
    clean = re.sub(r"\[[^\]]*\]", "", text).strip()  # MAI không hiểu thẻ [cười]
    url = f"{polli.GEN}/audio/" + urllib.parse.quote(clean, safe="")
    last = None
    for attempt in range(3):
        r = requests.get(url, params={"model": mcfg.get("model", "microsoft/mai-voice-2.1"), "voice": voice},
                         headers=polli._auth(), timeout=180)
        if r.ok and r.headers.get("content-type", "").startswith("audio"):
            out.write_bytes(r.content)
            return
        last = f"{r.status_code}: {r.text[:200]}"
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"MAI-Voice lỗi {last}")


# ---------- edge-tts (dự phòng) ----------

async def _edge_save(text: str, voice: str, rate: str, out: Path) -> None:
    import edge_tts

    await edge_tts.Communicate(text, voice, rate=rate).save(str(out))


def _edge_say(text: str, out: Path, cfg: dict) -> None:
    voice = cfg.get("edge_voice", "vi-VN-HoaiMyNeural")
    rate = cfg.get("edge_rate", "+0%")
    base = re.sub(r"\[[^\]]*\]", "", text).strip()  # bỏ thẻ cảm xúc của VieNeu
    alt = base.rstrip(".!?") + "."
    for attempt, (t, r) in enumerate([(base, rate), (base, rate), (alt + " ", rate), (base, "+0%"), (alt, "-5%")]):
        try:
            asyncio.run(_edge_save(t, voice, r, out))
            if out.exists() and out.stat().st_size > 1000:
                return
        except Exception as e:
            if attempt == 0:
                log(f"  edge-tts trục trặc, thử lại: {e}")
        time.sleep(1.5 + attempt)
    raise RuntimeError(f"edge-tts không đọc được: {text[:40]}")


def synth_scenes(scenes: list[dict], work: Path, cfg: dict) -> list[Path]:
    """Tạo 1 file wav (44.1kHz mono, đã cắt lặng) cho mỗi cảnh."""
    tcfg = cfg.get("tts", {})
    order = [tcfg.get("provider", "vieneu"), "vieneu", "edge"]  # lỗi thì lùi về VieNeu rồi edge-tts
    tempo = float(tcfg.get("tempo", 1.0))
    wavs = []
    t0 = time.time()
    used = None
    for i, s in enumerate(scenes):
        wav = work / f"voice_{i:02d}.wav"
        last_err = None
        speaker = s.get("speaker")
        sp = tcfg.get("speakers", {}).get(speaker, {}) if speaker else {}
        sp_tempo = tempo * float(sp.get("tempo", 1.0))
        # Mỗi người nói có thể dùng bộ giọng riêng, ví dụ bà dùng MAI-Voice, người kể dùng VieNeu
        prov_order = [sp["provider"]] + order if sp.get("provider") else order
        for prov in dict.fromkeys(prov_order):
            raw = work / f"voice_{i:02d}_{prov}.{'wav' if prov == 'vieneu' else 'mp3'}"
            try:
                if prov == "vieneu":
                    _vieneu_say(s["text"], raw, tcfg, speaker)
                elif prov == "mai":
                    _mai_say(s["text"], raw, tcfg, speaker)
                else:
                    _edge_say(s["text"], raw, tcfg)
                _to_wav(raw, wav, sp_tempo)
                used = prov
                break
            except Exception as e:
                last_err = e
                log(f"  giọng {prov} lỗi ở cảnh {i + 1}: {e}")
        else:
            raise RuntimeError(f"Không tạo được giọng đọc cảnh {i + 1}: {last_err}")
        wavs.append(wav)
    log(f"Giọng đọc: xong {len(wavs)} câu bằng {used} ({time.time() - t0:.0f}s)")
    return wavs


def wav_samples(path: Path) -> int:
    with wave.open(str(path), "rb") as w:
        return w.getnframes()
