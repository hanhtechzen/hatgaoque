"""Tạo file nghe thử so sánh giọng đọc: python tools/voice_compare.py
Kết quả: output/voice_compare/*.mp3"""
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import requests  # noqa: E402

from studio import polli  # noqa: E402
from studio.util import OUTPUT, load_config  # noqa: E402

load_config()
OUT = OUTPUT / "voice_compare"
OUT.mkdir(parents=True, exist_ok=True)

TEXT = ("Trưa hè, tiếng rao ai đồng nát sắt vụn bán đi vang đầu ngõ. Bin bật dậy như lò xo. "
        "Lục mãi chẳng có gì, Bin ôm luôn cái nồi nhôm của bà chạy ra đổi kẹo kéo.")
BA = "Bin ơi, cái nồi cơm của bà đâu rồi?"

SAMPLES = [
    ("MAI_nam_Grant", "microsoft/mai-voice-2.1", "vi-VN-Grant", TEXT),
    ("MAI_nu_Harper", "microsoft/mai-voice-2.1", "vi-VN-Harper", TEXT),
    ("MAI_nu_Harper_loi_ba", "microsoft/mai-voice-2.1", "vi-VN-Harper", BA),
]
for name, model, voice, text in SAMPLES:
    url = f"{polli.GEN}/audio/" + urllib.parse.quote(text, safe="")
    r = requests.get(url, params={"model": model, "voice": voice}, headers=polli._auth(), timeout=180)
    if r.ok and r.headers.get("content-type", "").startswith("audio"):
        (OUT / f"{name}.mp3").write_bytes(r.content)
        print("OK", name)
    else:
        print("LỖI", name, r.status_code, r.text[:300])
