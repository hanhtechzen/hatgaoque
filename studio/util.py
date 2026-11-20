from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

try:  # dùng kho chứng chỉ của Windows (tránh lỗi SSL khi mạng có kiểm tra HTTPS / antivirus)
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUTPUT = ROOT / "output"
LOGS = ROOT / "logs"
ASSETS = ROOT / "assets"


def load_config() -> dict:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    with open(ROOT / "config.json", encoding="utf-8") as f:
        return json.load(f)


def log(msg: str) -> None:
    LOGS.mkdir(exist_ok=True)
    now = dt.datetime.now()
    line = f"[{now:%H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(LOGS / f"{now:%Y-%m-%d}.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def slugify(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:60] or "video"


def ffmpeg_exe() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def run(cmd: list, cwd: Path | None = None) -> subprocess.CompletedProcess:
    r = subprocess.run(
        [str(c) for c in cmd],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if r.returncode != 0:
        raise RuntimeError(f"Lệnh lỗi ({r.returncode}): {Path(str(cmd[0])).name} ...\n{r.stderr[-2500:]}")
    return r
