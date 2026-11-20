"""Tạo file nghe thử các giọng VieNeu: python tools/voice_samples.py [giọng1 giọng2 ...]"""
import sys, time
from pathlib import Path
from vieneu import Vieneu

OUT = Path(__file__).resolve().parent.parent / "output" / "voice_samples"
OUT.mkdir(parents=True, exist_ok=True)
TEXT = ("Hồi đó, cứ trưa hè là cả xóm lại nghe tiếng rao: ai đồng nát sắt vụn bán đi. "
        "Đứa nào cũng lục tung gầm giường, chỉ mong đổi được một đoạn kẹo kéo.")
tts = Vieneu()
print("Giọng có sẵn:", tts.list_preset_voices())
voices = sys.argv[1:] or ["Hải Đăng", "Ngọc Huyền", "Thùy Dung", "Thanh Bình", "Ngọc Linh", "Minh Đức"]
for v in voices:
    t = time.time()
    try:
        audio = tts.infer(TEXT, voice=v)
        tts.save(audio, str(OUT / f"{v}.wav"))
        print(f"OK {v}: {time.time()-t:.1f}s")
    except Exception as e:
        print(f"LỖI {v}: {e}")
