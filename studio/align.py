"""Khớp phụ đề đúng từng chữ với giọng đọc bằng Whisper (faster-whisper).

Whisper nghe lại file giọng, lấy thời điểm từng chữ, rồi so khớp với chữ trong kịch bản
(chữ nào nghe sai/thiếu thì nội suy giữa 2 chữ khớp gần nhất). Không có Whisper -> trả None
và phụ đề dùng cách ước lượng cũ.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from pathlib import Path

from .util import log

_model = None


def _norm(w: str) -> str:
    w = unicodedata.normalize("NFC", w.lower())
    return re.sub(r"[^\w]", "", w)


def _get_model(cfg: dict):
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        try:
            import torch

            cuda = torch.cuda.is_available()
        except Exception:
            cuda = False
        scfg = cfg.get("subtitles", {})
        name = scfg.get("whisper_model_gpu" if cuda else "whisper_model_cpu", "large-v3-turbo" if cuda else "small")
        log(f"  Nạp Whisper '{name}' ({'GPU' if cuda else 'CPU'})...")
        _model = WhisperModel(name, device="cuda" if cuda else "cpu", compute_type="float16" if cuda else "int8")
    return _model


def _load_16k(wav: Path):
    """Đọc wav -> mảng float32 16kHz mono (tự làm, khỏi phụ thuộc thư viện giải mã âm thanh của Whisper)."""
    import subprocess
    import numpy as np

    from .util import ffmpeg_exe

    raw = subprocess.run([ffmpeg_exe(), "-v", "error", "-i", str(wav), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def word_times(wav: Path, words: list[str], cfg: dict) -> list[tuple[float, float]] | None:
    """Thời điểm (bắt đầu, kết thúc) tính từ đầu file wav cho từng chữ trong `words`."""
    if not words or cfg.get("subtitles", {}).get("align", "whisper") != "whisper":
        return None
    try:
        model = _get_model(cfg)
        segs, _ = model.transcribe(_load_16k(wav), language="vi", word_timestamps=True, beam_size=1,
                                   initial_prompt=" ".join(words), vad_filter=False)
        heard = [(w.word.strip(), w.start, w.end) for s in segs for w in (s.words or []) if w.word.strip()]
    except Exception as e:
        log(f"  (Whisper lỗi, dùng phụ đề ước lượng: {e})")
        return None
    if not heard:
        return None

    a = [_norm(w) for w in words]
    b = [_norm(w) for w, _, _ in heard]
    times: list[tuple[float, float] | None] = [None] * len(words)
    for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            _, s, e = heard[blk.b + k]
            times[blk.a + k] = (s, e)
    matched = sum(t is not None for t in times)
    if matched < max(2, len(words) * 0.4):
        return None  # khớp quá ít -> không tin được

    # nội suy chữ không khớp giữa 2 chữ khớp gần nhất
    total_end = heard[-1][2]
    i = 0
    while i < len(times):
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < len(times) and times[j] is None:
            j += 1
        left = times[i - 1][1] if i > 0 else 0.0
        right = times[j][0] if j < len(times) else total_end
        step = max(0.05, (right - left) / (j - i))
        for k in range(i, j):
            times[k] = (left + step * (k - i), left + step * (k - i + 1))
        i = j
    # làm liền mạch: chữ kéo dài tới khi chữ sau bắt đầu
    out = []
    for k, (s, e) in enumerate(times):
        nxt = times[k + 1][0] if k + 1 < len(times) else e
        out.append((s, max(e, nxt) if k + 1 < len(times) else e))
    return out
