"""Trang quản lý Hoài Niệm Studio (chạy trên máy, chỉ mở được từ chính máy này).

Chạy:  .venv\\Scripts\\python.exe -m studio web   rồi mở http://127.0.0.1:8686
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory

from . import state as st
from .util import ASSETS, DATA, LOGS, OUTPUT, ROOT, load_config

PORT = 8686
app = Flask(__name__, static_folder=str(ROOT / "web"), static_url_path="/static")
app.json.ensure_ascii = False
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0  # luôn tải giao diện mới nhất

VIENEU_VOICES = [
    "Thiện Minh", "Thiền Tâm Đức", "Thanh Bình", "Hải Đăng", "Adam bựa", "Phạm Tuyên", "Xuân Vĩnh", "Quốc Tuấn",
    "Minh Đức", "Ngọc Linh", "Quỳnh Anh", "Ngọc Huyền", "Trúc Ly", "Đoan Trang", "Mai Anh", "Quang Sơn",
    "Ngọc Trân", "Thái Sơn", "Thục Đoan", "Mỹ Duyên", "Kim Thanh", "Đức Trí", "Minh Triết", "Thùy Dung", "Adam",
]
MAI_VOICES = ["vi-VN-Grant", "vi-VN-Harper"]
EDGE_VOICES = ["vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"]
SFX_NAMES = ["ve_sau", "mua", "bep_cui", "dem_que", "san_truong", "lang_que", "gio_dong", "pho_cu"]
AUDIO_EXT = {".mp3", ".m4a", ".wav", ".ogg"}
ENV_KEYS = ["POLLINATIONS_TOKEN", "GEMINI_API_KEY", "FB_PAGE_ID", "FB_PAGE_TOKEN"]
SCRIPTS = DATA / "scripts"


# ======================= HÀNG ĐỢI TÁC VỤ =======================

class Jobs:
    """Chạy lần lượt từng lệnh `python -m studio ...` trong nền, ghi log ra file để trang web xem trực tiếp."""

    def __init__(self) -> None:
        self.items: list[dict] = []
        self.lock = threading.Lock()
        self.cv = threading.Condition(self.lock)
        (LOGS / "jobs").mkdir(parents=True, exist_ok=True)
        self.proc: subprocess.Popen | None = None
        threading.Thread(target=self._worker, daemon=True).start()

    def add(self, label: str, args: list[str]) -> dict:
        with self.cv:
            jid = (self.items[-1]["id"] + 1) if self.items else 1
            job = {"id": jid, "label": label, "args": args, "status": "queued",
                   "created": dt.datetime.now().strftime("%H:%M:%S"), "started": None, "ended": None,
                   "log": str(LOGS / "jobs" / f"{dt.datetime.now():%Y%m%d-%H%M%S}-{jid}.log")}
            self.items.append(job)
            self.items[:] = self.items[-60:]
            self.cv.notify()
            return job

    def get(self, jid: int) -> dict | None:
        return next((j for j in self.items if j["id"] == jid), None)

    def cancel(self, jid: int) -> bool:
        with self.lock:
            j = self.get(jid)
            if not j:
                return False
            if j["status"] == "queued":
                j["status"] = "canceled"
                return True
            if j["status"] == "running" and self.proc:
                self.proc.terminate()
                j["status"] = "canceled"
                return True
        return False

    def _worker(self) -> None:
        while True:
            with self.cv:
                while not any(j["status"] == "queued" for j in self.items):
                    self.cv.wait()
                job = next(j for j in self.items if j["status"] == "queued")
                job["status"] = "running"
                job["started"] = dt.datetime.now().strftime("%H:%M:%S")
            env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
            with open(job["log"], "w", encoding="utf-8") as logf:
                logf.write(f"$ studio {' '.join(job['args'])}\n")
                logf.flush()
                self.proc = subprocess.Popen(
                    [sys.executable, "-m", "studio", *job["args"]], cwd=ROOT, env=env,
                    stdout=logf, stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                code = self.proc.wait()
                self.proc = None
            with self.lock:
                if job["status"] != "canceled":
                    job["status"] = "done" if code == 0 else "failed"
                job["ended"] = dt.datetime.now().strftime("%H:%M:%S")


JOBS = Jobs()


def _job_json(j: dict, tail: int = 0) -> dict:
    out = {k: v for k, v in j.items() if k != "args"}
    if tail:
        try:
            text = Path(j["log"]).read_text(encoding="utf-8", errors="replace")
            lines = [ln for ln in text.splitlines() if not re.search(r"symlinks|HF_TOKEN|HF Hub|faster downloads", ln)]
            out["log_text"] = "\n".join(lines[-tail:])
        except FileNotFoundError:
            out["log_text"] = ""
    return out


# ======================= TIỆN ÍCH =======================

def _safe(base: Path, rel: str) -> Path:
    p = (base / rel).resolve()
    if base.resolve() not in p.parents and p != base.resolve():
        abort(404)
    return p


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _valid_id(sid: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,80}", sid or ""):
        abort(400, "id không hợp lệ")
    return sid


def _read_env() -> dict:
    vals = {}
    path = ROOT / ".env"
    if path.exists():
        for ln in path.read_text(encoding="utf-8").splitlines():
            if "=" in ln and not ln.strip().startswith("#"):
                k, v = ln.split("=", 1)
                vals[k.strip()] = v.strip()
    return vals


def _write_env(updates: dict) -> None:
    path = ROOT / ".env"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    done = set()
    for i, ln in enumerate(lines):
        if "=" in ln and not ln.strip().startswith("#"):
            k = ln.split("=", 1)[0].strip()
            if k in updates:
                lines[i] = f"{k}={updates[k]}"
                done.add(k)
    lines += [f"{k}={v}" for k, v in updates.items() if k not in done]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for k, v in updates.items():
        os.environ[k] = v


def _mask(v: str) -> str:
    return "" if not v else (v[:4] + "•" * 8 + v[-3:] if len(v) > 10 else "•" * len(v))


# ======================= TRANG =======================

@app.get("/")
def index():
    return send_from_directory(ROOT / "web", "index.html")


@app.get("/media/<path:rel>")
def media(rel: str):
    p = _safe(OUTPUT, rel)
    return send_from_directory(p.parent, p.name)


@app.get("/asset/<path:rel>")
def asset(rel: str):
    p = _safe(ASSETS, rel)
    return send_from_directory(p.parent, p.name)


# ---------- tổng quan ----------

@app.get("/api/summary")
def summary():
    cfg = load_config()
    s = st.load()
    scripts = sorted(SCRIPTS.glob("*.json"))
    unused = [p for p in scripts if p.stem not in s["used_bank"]]
    env = _read_env()
    music = [p for p in (ASSETS / "music").glob("*") if p.suffix.lower() in AUDIO_EXT]
    sfx = [n for n in SFX_NAMES if any((ASSETS / "sfx").glob(f"{n}.*")) or (ASSETS / "sfx" / n).is_dir()]
    return jsonify({
        "videos": len([d for d in OUTPUT.iterdir() if (d / "video.mp4").exists()]) if OUTPUT.exists() else 0,
        "scripts_total": len(scripts), "scripts_unused": len(unused),
        "has_key": bool(env.get("POLLINATIONS_TOKEN")),
        "facebook": bool(cfg["publish"]["facebook"].get("enabled")),
        "music": len(music), "sfx": sfx, "budget_vnd": round(cfg.get("budget_usd_per_video", 0.18) * cfg.get("usd_to_vnd", 26000)),
        "running": next((_job_json(j) for j in JOBS.items if j["status"] == "running"), None),
        "gpu": _gpu_info(),
    })


_GPU = None


def _gpu_info() -> dict:
    global _GPU
    if _GPU is None:
        from . import local_gpu

        _GPU = local_gpu.info()
    return _GPU


@app.post("/api/gpu-test")
def gpu_test():
    global _GPU
    _GPU = None
    return jsonify(JOBS.add("Kiểm tra GPU (tạo thử ảnh + clip)", ["gpu-test"]))


# ---------- video ----------

@app.get("/api/videos")
def videos():
    s = st.load()
    by_folder = {Path(v["folder"]).name: v for v in s["videos"]}
    out = []
    if OUTPUT.exists():
        for d in sorted(OUTPUT.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if not (d / "video.mp4").exists():
                continue
            meta = _read_json(d / "script.json", {})
            rec = by_folder.get(d.name, {})
            fb = rec.get("facebook") or {}
            out.append({
                "folder": d.name, "title": meta.get("title", d.name), "id": meta.get("id"),
                "created": dt.datetime.fromtimestamp((d / "video.mp4").stat().st_mtime).strftime("%d/%m %H:%M"),
                "video": f"/media/{d.name}/video.mp4", "cover": f"/media/{d.name}/cover.jpg" if (d / "cover.jpg").exists() else None,
                "video_tiktok": f"/media/{d.name}/video_tiktok.mp4" if (d / "video_tiktok.mp4").exists() else None,
                "compilation": d.name.startswith("tonghop_"),
                "caption": (d / "caption.txt").read_text(encoding="utf-8") if (d / "caption.txt").exists() else "",
                "cost": (d / "cost.txt").read_text(encoding="utf-8").strip() if (d / "cost.txt").exists() else "",
                "facebook": ({"scheduled": dt.datetime.fromtimestamp(fb["publish_ts"]).strftime("%d/%m %H:%M")}
                             if fb.get("publish_ts") else ({"posted": True} if fb else None)),
                "facebook_error": rec.get("facebook_error"),
            })
    return jsonify(out)


@app.post("/api/videos/<folder>/post")
def video_post(folder: str):
    d = _safe(OUTPUT, folder)
    return jsonify(JOBS.add(f"Đăng Facebook: {folder}", ["post", str(d)]))


@app.post("/api/videos/<folder>/archive")
def video_archive(folder: str):
    d = _safe(OUTPUT, folder)
    dest = OUTPUT / "_luu_tru"
    dest.mkdir(exist_ok=True)
    shutil.move(str(d), str(dest / d.name))
    return jsonify({"ok": True})


# ---------- kịch bản ----------

@app.get("/api/scripts")
def scripts_list():
    s = st.load()
    out = []
    for p in sorted(SCRIPTS.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        d = _read_json(p, {})
        out.append({"id": p.stem, "title": d.get("title", p.stem), "hook": d.get("hook", ""),
                    "scenes": len(d.get("scenes", [])), "used": p.stem in s["used_bank"],
                    "updated": dt.datetime.fromtimestamp(p.stat().st_mtime).strftime("%d/%m %H:%M")})
    return jsonify(out)


@app.get("/api/scripts/<sid>")
def script_get(sid: str):
    p = SCRIPTS / f"{_valid_id(sid)}.json"
    if not p.exists():
        abort(404)
    return jsonify(_read_json(p, {}))


@app.put("/api/scripts/<sid>")
def script_put(sid: str):
    from .script_gen import validate

    d = request.get_json(force=True)
    d["id"] = _valid_id(sid)
    try:
        d = validate(d)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    _write_json(SCRIPTS / f"{sid}.json", {k: v for k, v in d.items() if not k.startswith("_")})
    return jsonify({"ok": True})


@app.post("/api/scripts")
def script_new():
    from .util import slugify

    title = (request.get_json(force=True) or {}).get("title") or "Tập mới"
    base = slugify(title)
    sid, n = base, 2
    while (SCRIPTS / f"{sid}.json").exists():
        sid, n = f"{base}-{n}", n + 1
    d = {"id": sid, "topic": title, "title": title, "hook": title, "ambience": "lang_que",
         "scenes": [{"text": "Câu mở đầu...", "images": ["{BIN} ..."]}],
         "caption": "", "hashtags": ["#hatgaoque", "#8x9x", "#tuoitho", "#ongba"]}
    _write_json(SCRIPTS / f"{sid}.json", d)
    return jsonify(d)


@app.post("/api/scripts/<sid>/build")
def script_build(sid: str):
    return jsonify(JOBS.add(f"Dựng video: {sid}", ["make", _valid_id(sid)]))


@app.post("/api/scripts/<sid>/used")
def script_used(sid: str):
    used = bool((request.get_json(force=True) or {}).get("used"))
    s = st.load()
    s["used_bank"] = [x for x in s["used_bank"] if x != sid] + ([sid] if used else [])
    st.save(s)
    return jsonify({"ok": True})


@app.post("/api/scripts/<sid>/archive")
def script_archive(sid: str):
    p = SCRIPTS / f"{_valid_id(sid)}.json"
    dest = DATA / "scripts_luu_tru"
    dest.mkdir(exist_ok=True)
    shutil.move(str(p), str(dest / p.name))
    return jsonify({"ok": True})


@app.post("/api/scripts/write")
def script_write():
    body = request.get_json(force=True) or {}
    topic = (body.get("topic") or "").strip()
    memory = (body.get("memory") or "").strip()
    if not topic and memory:
        topic = memory[:60]
    if not topic:
        return jsonify({"error": "Nhập chủ đề"}), 400
    args = ["write", topic]
    if body.get("two_part"):
        args.append("--two-part")
    if memory:
        args += ["--memory", memory, "--name", (body.get("name") or "giấu tên").strip()[:60]]
        if body.get("source"):
            args += ["--source", str(body["source"])]
    label = ("AI viết truyện 2 phần: " if body.get("two_part") else "AI viết kịch bản: ") + topic[:50]
    return jsonify(JOBS.add(label, args))


# ---------- chủ đề ----------

@app.get("/api/topics")
def topics_get():
    p = DATA / "topics.txt"
    used = set(st.load()["used_topics"])
    lines = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []
    return jsonify([{"topic": t, "used": t in used} for t in lines if t and not t.startswith("#")])


@app.put("/api/topics")
def topics_put():
    items = [t.strip() for t in (request.get_json(force=True) or []) if str(t).strip()]
    header = "# Mỗi dòng một chủ đề. Khi hết kịch bản có sẵn, AI lấy ngẫu nhiên một chủ đề chưa dùng để viết.\n"
    (DATA / "topics.txt").write_text(header + "\n".join(items) + "\n", encoding="utf-8")
    return jsonify({"ok": True})


# ---------- nhân vật ----------

@app.get("/api/characters")
def chars_get():
    data = _read_json(DATA / "characters.json", {})
    out = []
    for k, v in data.items():
        img = ASSETS / "characters" / f"{k}.png"
        out.append({"key": k, "name": v.get("name", k), "look": v.get("look", ""),
                    "image": f"/asset/characters/{k}.png?t={int(img.stat().st_mtime)}" if img.exists() else None})
    return jsonify(out)


@app.put("/api/characters/<key>")
def chars_put(key: str):
    data = _read_json(DATA / "characters.json", {})
    if key not in data:
        abort(404)
    body = request.get_json(force=True) or {}
    for f in ("name", "look"):
        if body.get(f):
            data[key][f] = body[f].strip()
    _write_json(DATA / "characters.json", data)
    return jsonify({"ok": True})


@app.post("/api/characters/<key>/redraw")
def chars_redraw(key: str):
    if not re.fullmatch(r"[A-Z_]+", key):
        abort(400)
    return jsonify(JOBS.add(f"Vẽ ảnh mẫu nhân vật {key}", ["characters", key]))


# ---------- giọng đọc ----------

@app.get("/api/voices")
def voices_get():
    cfg = load_config()
    samples = {}
    folder = OUTPUT / "voice_samples"
    if folder.exists():
        for p in folder.glob("*.wav"):
            samples[p.stem] = f"/media/voice_samples/{p.name}?t={int(p.stat().st_mtime)}"
    return jsonify({"tts": cfg.get("tts", {}), "vieneu": VIENEU_VOICES, "mai": MAI_VOICES, "edge": EDGE_VOICES,
                    "samples": samples})


@app.put("/api/voices")
def voices_put():
    body = request.get_json(force=True) or {}
    cfg = _read_json(ROOT / "config.json", {})
    t = cfg.setdefault("tts", {})
    nar = body.get("narrator", {})
    if nar.get("provider") in ("vieneu", "mai", "edge"):
        t["provider"] = nar["provider"]
        if nar["provider"] == "vieneu":
            t["vieneu_voice"] = nar.get("voice", t.get("vieneu_voice"))
        elif nar["provider"] == "mai":
            t.setdefault("mai", {})["voice"] = nar.get("voice", "vi-VN-Grant")
        else:
            t["edge_voice"] = nar.get("voice", t.get("edge_voice"))
    for who in ("ba", "ong"):
        sp = body.get(who)
        if sp and sp.get("provider") in ("vieneu", "mai"):
            cur = t.setdefault("speakers", {}).setdefault(who, {})
            cur.update({"provider": sp["provider"], "voice": sp.get("voice")})
            if sp.get("tempo"):
                cur["tempo"] = float(sp["tempo"])
    if body.get("tempo"):
        t["tempo"] = float(body["tempo"])
    _write_json(ROOT / "config.json", cfg)
    return jsonify({"ok": True})


@app.post("/api/voices/sample")
def voices_sample():
    body = request.get_json(force=True) or {}
    prov, voice = body.get("provider"), body.get("voice", "")
    if prov not in ("vieneu", "mai", "edge") or not voice:
        return jsonify({"error": "Chọn giọng"}), 400
    name = re.sub(r"[^\w-]+", "_", f"{prov}_{voice}")
    args = ["sample", prov, voice, str(OUTPUT / "voice_samples" / f"{name}.wav")]
    if body.get("text"):
        args += ["--text", body["text"]]
    job = JOBS.add(f"Nghe thử giọng {voice}", args)
    return jsonify({**job, "sample": f"/media/voice_samples/{name}.wav"})


# ---------- âm thanh ----------

@app.get("/api/audio")
def audio_get():
    music = [{"name": p.name, "url": f"/asset/music/{p.name}"}
             for p in sorted((ASSETS / "music").glob("*")) if p.suffix.lower() in AUDIO_EXT]
    sfx = []
    for n in SFX_NAMES:
        files = list((ASSETS / "sfx").glob(f"{n}.*"))
        files = [p for p in files if p.suffix.lower() in AUDIO_EXT]
        sfx.append({"name": n, "file": files[0].name if files else None,
                    "url": f"/asset/sfx/{files[0].name}" if files else None})
    return jsonify({"music": music, "sfx": sfx})


@app.post("/api/audio/upload")
def audio_upload():
    kind = request.form.get("kind")
    f = request.files.get("file")
    if not f or Path(f.filename).suffix.lower() not in AUDIO_EXT:
        return jsonify({"error": "Chỉ nhận file .mp3 .m4a .wav .ogg"}), 400
    if kind == "music":
        name = re.sub(r"[^\w.\- ]+", "_", Path(f.filename).name)
        dest = ASSETS / "music" / name
    elif kind in SFX_NAMES:
        for old in (ASSETS / "sfx").glob(f"{kind}.*"):
            if old.suffix.lower() in AUDIO_EXT:
                old.unlink()
        dest = ASSETS / "sfx" / f"{kind}{Path(f.filename).suffix.lower()}"
    else:
        abort(400)
    dest.parent.mkdir(parents=True, exist_ok=True)
    f.save(dest)
    return jsonify({"ok": True})


@app.get("/api/audio/ai-estimate")
def audio_ai_estimate():
    from . import audio_ai

    music = [n for n in audio_ai.MUSIC if not (ASSETS / "music" / f"ai_{n}.mp3").exists()]
    sfx = [n for n in audio_ai.SFX if not any((ASSETS / "sfx").glob(f"{n}.*"))]
    usd = audio_ai.estimate(music, sfx)
    return jsonify({"music": len(music), "sfx": len(sfx), "usd": round(usd, 3),
                    "vnd": round(usd * load_config().get("usd_to_vnd", 26000), -2)})


@app.post("/api/audio/ai")
def audio_ai_run():
    only = (request.get_json(force=True) or {}).get("only")
    args = ["audio-ai"] + (["--only", only] if only in ("music", "sfx") else [])
    return jsonify(JOBS.add("AI tạo nhạc nền & âm thanh", args))


@app.post("/api/audio/remove")
def audio_remove():
    body = request.get_json(force=True) or {}
    base = ASSETS / ("music" if body.get("kind") == "music" else "sfx")
    p = _safe(base, body.get("name", ""))
    if p.suffix.lower() in AUDIO_EXT and p.exists():
        trash = ASSETS / "_da_go"
        trash.mkdir(exist_ok=True)
        shutil.move(str(p), str(trash / p.name))
    return jsonify({"ok": True})


# ---------- cài đặt ----------

@app.get("/api/settings")
def settings_get():
    cfg = load_config()
    env = _read_env()
    return jsonify({"config": cfg, "env": {k: _mask(env.get(k, "")) for k in ENV_KEYS},
                    "env_set": {k: bool(env.get(k)) for k in ENV_KEYS}})


@app.put("/api/settings")
def settings_put():
    body = request.get_json(force=True) or {}
    cfg = _read_json(ROOT / "config.json", {})
    c = body.get("config", {})
    if "videos_per_run" in c:
        cfg["videos_per_run"] = max(1, min(10, int(c["videos_per_run"])))
    if "budget_vnd" in c:
        cfg["budget_usd_per_video"] = round(float(c["budget_vnd"]) / cfg.get("usd_to_vnd", 26000), 4)
    if "series_name" in c:
        cfg.setdefault("video", {})["series_name"] = c["series_name"]
    if "style" in c:
        cfg.setdefault("images", {})["style"] = c["style"]
    if "motion_enabled" in c:
        cfg.setdefault("motion", {})["enabled"] = bool(c["motion_enabled"])
    if "motion_resolution" in c:
        res = c["motion_resolution"]
        cfg.setdefault("motion", {})["resolution"] = res
        cfg["motion"]["price_per_sec"] = {"480p": 0.0099225, "720p": 0.021021}.get(res, 0.0099225)
    if "max_shots" in c:
        cfg.setdefault("motion", {})["max_shots"] = max(0, min(6, int(c["max_shots"])))
    if "outro" in c:
        o = cfg.setdefault("video", {}).setdefault("outro", {})
        o["enabled"] = bool(c["outro"].get("enabled"))
        if c["outro"].get("text"):
            o["text"] = c["outro"]["text"].strip().replace("\r", "").replace("\n", "\\N")
        if c["outro"].get("voice"):
            o["voice"] = c["outro"]["voice"].strip()
    fb = c.get("facebook")
    if fb:
        f = cfg.setdefault("publish", {}).setdefault("facebook", {})
        f["enabled"] = bool(fb.get("enabled"))
        f["mode"] = "scheduled" if fb.get("mode") != "now" else "now"
        if re.fullmatch(r"\d{1,2}:\d{2}", fb.get("time", "")):
            f["time"] = fb["time"]
    _write_json(ROOT / "config.json", cfg)
    env_up = {k: v.strip() for k, v in (body.get("env") or {}).items() if k in ENV_KEYS and v and "•" not in v}
    if env_up:
        _write_env(env_up)
    return jsonify({"ok": True})


@app.get("/api/outro")
def outro_get():
    p = ASSETS / "outro" / "outro.png"
    return jsonify({"image": f"/asset/outro/outro.png?t={int(p.stat().st_mtime)}" if p.exists() else None})


@app.post("/api/outro/redraw")
def outro_redraw():
    p = ASSETS / "outro" / "outro.png"
    if p.exists():
        trash = ASSETS / "_da_go"
        trash.mkdir(exist_ok=True)
        shutil.move(str(p), str(trash / f"outro_{int(time.time())}.png"))
    return jsonify(JOBS.add("Vẽ ảnh cảnh kết", ["outro"]))


@app.post("/api/check")
def check():
    return jsonify(JOBS.add("Kiểm tra cài đặt", ["check"]))


# ---------- chạy & lịch tự động ----------

@app.post("/api/run")
def run_now():
    body = request.get_json(force=True) or {}
    args = ["run"]
    if body.get("count"):
        args += ["--count", str(int(body["count"]))]
    if body.get("no_post"):
        args.append("--no-post")
    return jsonify(JOBS.add("Tạo video tự động" + (f" x{body['count']}" if body.get("count") else ""), args))


def _ps(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


@app.get("/api/schedule")
def schedule_get():
    r = _ps("$t = Get-ScheduledTask -TaskName HoaiNiemStudio -ErrorAction SilentlyContinue; "
            "if ($t) { $i = $t | Get-ScheduledTaskInfo; "
            "\"{0}|{1}|{2}\" -f $t.State, ($t.Triggers[0].StartBoundary), $i.NextRunTime }")
    out = r.stdout.strip()
    if not out:
        return jsonify({"enabled": False})
    state, start, nxt = (out.split("|") + ["", "", ""])[:3]
    m = re.search(r"T(\d{2}:\d{2})", start)
    return jsonify({"enabled": state != "Disabled", "time": m.group(1) if m else "", "next": nxt})


@app.post("/api/schedule")
def schedule_set():
    body = request.get_json(force=True) or {}
    if body.get("enabled"):
        t = body.get("time", "07:00")
        if not re.fullmatch(r"\d{1,2}:\d{2}", t):
            return jsonify({"error": "Giờ không hợp lệ"}), 400
        r = _ps(f"& '{ROOT / 'register_task.ps1'}' -At '{t}'")
    else:
        r = _ps("Unregister-ScheduledTask -TaskName HoaiNiemStudio -Confirm:$false -ErrorAction SilentlyContinue")
    if r.returncode != 0:
        return jsonify({"error": (r.stderr or r.stdout)[-500:]}), 500
    return jsonify({"ok": True})


# ---------- tăng trưởng ----------

def _tiktok_slots(n: int, times: list[str]) -> list[str]:
    """Gợi ý giờ đăng TikTok cho n video tiếp theo theo các khung giờ."""
    out, now = [], dt.datetime.now()
    for day in range(0, 30):
        for t in sorted(times):
            hh, mm = (int(x) for x in t.split(":"))
            slot = (now + dt.timedelta(days=day)).replace(hour=hh, minute=mm, second=0, microsecond=0)
            if slot > now + dt.timedelta(minutes=15):
                out.append(slot.strftime("%a %d/%m %H:%M").replace("Mon", "T2").replace("Tue", "T3")
                           .replace("Wed", "T4").replace("Thu", "T5").replace("Fri", "T6").replace("Sat", "T7")
                           .replace("Sun", "CN"))
            if len(out) >= n:
                return out
    return out


@app.get("/api/growth")
def growth_get():
    from . import growth

    cfg = load_config()
    fb = cfg["publish"]["facebook"]
    tk_times = cfg["publish"].get("tiktok", {}).get("times", ["12:00", "20:30"])
    tiktok = growth.tiktok_all()
    queue = []
    if OUTPUT.exists():
        for d in sorted(OUTPUT.iterdir(), key=lambda p: p.stat().st_mtime):
            tk = tiktok.get(d.name, {})
            if (d / "video.mp4").exists() and not tk.get("posted") and not tk.get("skip"):
                meta = _read_json(d / "script.json", {})
                queue.append({"folder": d.name, "title": meta.get("title", d.name),
                              "cover": f"/media/{d.name}/cover.jpg" if (d / "cover.jpg").exists() else None,
                              "video": f"/media/{d.name}/video.mp4",
                              "caption": (d / "caption.txt").read_text(encoding="utf-8") if (d / "caption.txt").exists() else ""})
    for q, slot in zip(queue, _tiktok_slots(len(queue), tk_times)):
        q["suggest"] = slot
    posted = [{"folder": k, **v} for k, v in tiktok.items() if v.get("posted")]
    for q in queue:  # bản TikTok riêng (không nhạc, câu móc B)
        if (OUTPUT / q["folder"] / "video_tiktok.mp4").exists():
            q["video"] = f"/media/{q['folder']}/video_tiktok.mp4"
            q["tiktok_version"] = True
        tl = _read_json(OUTPUT / q["folder"] / "timeline.json", {})
        q["hook_tiktok"] = tl.get("hook_tiktok")
    comments = growth.comments_all()
    memories = [c for c in comments.values()
                if len(c.get("message", "")) >= 40 and c.get("status") not in ("used_for_episode", "memory_skip")]
    memories.sort(key=lambda c: len(c.get("message", "")), reverse=True)
    pending = [c for c in comments.values() if c.get("status") == "draft"]
    pending.sort(key=lambda c: c.get("created") or "", reverse=True)
    return jsonify({
        "seasons": [s["name"] for s in growth.active_seasons()],
        "fb_enabled": bool(fb.get("enabled")), "fb_times": fb.get("times") or [fb.get("time", "19:30")],
        "tiktok_times": tk_times, "videos_per_run": cfg.get("videos_per_run", 1),
        "auto_reply": bool(cfg.get("growth", {}).get("auto_reply")),
        "leaderboard": growth.leaderboard()[:30], "tiktok_queue": queue, "tiktok_posted": posted,
        "comments": pending[:100], "comments_replied": sum(1 for c in comments.values() if c.get("status") == "replied"),
        "memories": memories[:30], "upcoming": growth.upcoming(60), "lunar_today": growth.lunar_today(),
        "weekly": {"enabled": cfg.get("growth", {}).get("weekly_compilation", True),
                   "weekday": cfg.get("growth", {}).get("compilation_weekday", 6)},
    })


@app.post("/api/compile")
def compile_now():
    return jsonify(JOBS.add("Ghép video tổng hợp 7 ngày", ["compile", "--days", "7"]))


@app.post("/api/memories/<cid>/skip")
def memory_skip(cid: str):
    from . import growth

    growth.set_comment(cid, status="memory_skip")
    return jsonify({"ok": True})


@app.put("/api/growth/settings")
def growth_settings():
    body = request.get_json(force=True) or {}
    cfg = _read_json(ROOT / "config.json", {})
    pat = re.compile(r"^\d{1,2}:\d{2}$")
    if "fb_times" in body:
        times = [t.strip() for t in body["fb_times"] if pat.match(t.strip())]
        if times:
            cfg["publish"]["facebook"]["times"] = times
    if "tiktok_times" in body:
        times = [t.strip() for t in body["tiktok_times"] if pat.match(t.strip())]
        if times:
            cfg["publish"].setdefault("tiktok", {})["times"] = times
    if "videos_per_run" in body:
        cfg["videos_per_run"] = max(1, min(10, int(body["videos_per_run"])))
    if "auto_reply" in body:
        cfg.setdefault("growth", {})["auto_reply"] = bool(body["auto_reply"])
    if "weekly_compilation" in body:
        cfg.setdefault("growth", {})["weekly_compilation"] = bool(body["weekly_compilation"])
    if "compilation_weekday" in body:
        cfg.setdefault("growth", {})["compilation_weekday"] = max(0, min(6, int(body["compilation_weekday"])))
    if "loop" in body:
        cfg.setdefault("video", {})["loop"] = bool(body["loop"])
    _write_json(ROOT / "config.json", cfg)
    return jsonify({"ok": True})


@app.post("/api/growth/sync")
def growth_sync():
    return jsonify(JOBS.add("Đồng bộ số liệu & bình luận", ["sync"]))


@app.post("/api/tiktok/<folder>")
def tiktok_set(folder: str):
    from . import growth

    _safe(OUTPUT, folder)
    body = request.get_json(force=True) or {}
    clean = {}
    for k in ("views", "likes", "comments", "shares"):
        if k in body and str(body[k]).strip() != "":
            clean[k] = int(float(body[k]))
    if "posted" in body:
        clean["posted"] = bool(body["posted"])
    if "skip" in body:
        clean["skip"] = bool(body["skip"])
    if body.get("url"):
        clean["url"] = str(body["url"])[:300]
    return jsonify(growth.tiktok_update(folder, clean))


@app.post("/api/comments/<cid>/send")
def comment_send(cid: str):
    from . import growth

    text = ((request.get_json(force=True) or {}).get("text") or "").strip()
    if not text:
        return jsonify({"error": "Câu trả lời trống"}), 400
    try:
        growth.send_reply(cid, text, load_config())
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"ok": True})


@app.post("/api/comments/<cid>/skip")
def comment_skip(cid: str):
    from . import growth

    growth.set_comment(cid, status="skip")
    return jsonify({"ok": True})


# ---------- tác vụ ----------

@app.get("/api/jobs")
def jobs_list():
    return jsonify([_job_json(j) for j in reversed(JOBS.items)])


@app.get("/api/jobs/<int:jid>")
def job_get(jid: int):
    j = JOBS.get(jid)
    if not j:
        abort(404)
    return jsonify(_job_json(j, tail=int(request.args.get("tail", 200))))


@app.post("/api/jobs/<int:jid>/cancel")
def job_cancel(jid: int):
    return jsonify({"ok": JOBS.cancel(jid)})


def serve(open_browser: bool = True) -> None:
    url = f"http://127.0.0.1:{PORT}"
    print(f"Trang quản lý: {url}  (đóng cửa sổ này để tắt)")
    if open_browser and not os.environ.get("STUDIO_NO_BROWSER"):
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=PORT, debug=False, threaded=True)
