"""Tăng trưởng kênh: lịch theo mùa, số liệu, bình luận, vòng học từ các tập thắng.

Nguyên tắc: chỉ dùng cách được nền tảng cho phép (API chính thức, đăng đều, trả lời bình luận thật).
KHÔNG mua view/follow, KHÔNG bot follow/like/comment dạo - làm vậy kênh bị bóp hoặc khóa.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import requests

from . import state as st
from .util import DATA, log

METRICS = DATA / "metrics.json"
COMMENTS = DATA / "comments.json"
TIKTOK = DATA / "tiktok.json"
CALENDAR = DATA / "calendar.json"


def _load(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _save(p: Path, data) -> None:
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


# ---------------- lịch theo mùa ----------------

def active_seasons(today: dt.date | None = None) -> list[dict]:
    today = today or dt.date.today()
    md = today.strftime("%m-%d")
    out = []
    for s in _load(CALENDAR, {}).get("seasons", []):
        a, b = s["from"], s["to"]
        if (a <= md <= b) if a <= b else (md >= a or md <= b):  # khoảng vắt qua năm mới
            out.append(s)
    return out


# Ngày đặc biệt: ("âm"/"dương", tháng, ngày) hoặc hàm tính ngày. lead = đăng trước bao nhiêu ngày.
SPECIAL_DAYS = [
    {"name": "Tết Nguyên Đán", "lunar": (1, 1), "lead": 14, "scripts": ["dem-canh-banh-chung"],
     "topics": ["Tiền lì xì mừng tuổi", "Quần áo mới ngày Tết", "Mâm ngũ quả ngày Tết", "Đêm giao thừa đốt pháo hoa giấy"]},
    {"name": "Rằm tháng Giêng", "lunar": (1, 15), "lead": 3, "topics": ["Bà đi lễ chùa rằm tháng Giêng"]},
    {"name": "Tết Hàn thực", "lunar": (3, 3), "lead": 3, "topics": ["Nặn bánh trôi bánh chay cùng bà"]},
    {"name": "Tết Đoan Ngọ (giết sâu bọ)", "lunar": (5, 5), "lead": 3,
     "topics": ["Sáng mùng 5 ăn rượu nếp, hoa quả giết sâu bọ"]},
    {"name": "Rằm tháng Bảy - Vu Lan", "lunar": (7, 15), "lead": 5,
     "topics": ["Bông hồng cài áo mùa Vu Lan", "Trẻ con giành đồ cúng cô hồn"]},
    {"name": "Trung thu", "lunar": (8, 15), "lead": 14, "scripts": ["trung-thu-den-ong-sao"],
     "topics": ["Tò he nặn bằng bột gạo", "Phá cỗ trông trăng", "Đèn kéo quân của ông"]},
    {"name": "Ông Công Ông Táo", "lunar": (12, 23), "lead": 4, "topics": ["Thả cá chép tiễn ông Táo"]},
    {"name": "Quốc tế Phụ nữ 8/3", "solar": (3, 8), "lead": 3, "topics": ["Tặng bà bông hoa giấy ngày 8/3"]},
    {"name": "Quốc tế Thiếu nhi 1/6", "solar": (6, 1), "lead": 5,
     "topics": ["Chơi đồ hàng", "Gấp máy bay giấy, thuyền giấy", "Quà 1/6 ngày xưa"]},
    {"name": "Ngày Gia đình Việt Nam 28/6", "solar": (6, 28), "lead": 3, "topics": ["Cả nhà ăn cơm chung mâm"]},
    {"name": "Khai giảng 5/9", "solar": (9, 5), "lead": 10, "scripts": ["but-may-muc-tim"],
     "topics": ["Bao vở bằng giấy báo", "Khăn quàng đỏ", "Bố chở đi học bằng xe đạp"]},
    {"name": "Phụ nữ Việt Nam 20/10", "solar": (10, 20), "lead": 3, "topics": ["Món quà Bin tự làm tặng bà"]},
    {"name": "Nhà giáo Việt Nam 20/11", "solar": (11, 20), "lead": 10, "scripts": ["but-may-muc-tim"],
     "topics": ["Tặng hoa cô giáo ngày 20/11", "Lưu bút cuối năm"]},
    {"name": "Giáng sinh", "solar": (12, 24), "lead": 4, "topics": ["Đi xem hang đá đêm Giáng sinh"]},
    {"name": "Ngày của Mẹ", "nth_sunday": (5, 2), "lead": 4, "topics": ["Bin giúp mẹ rửa bát"]},
    {"name": "Ngày của Cha", "nth_sunday": (6, 3), "lead": 4, "topics": ["Bố chở Bin đi câu cá"]},
]


def _event_date(ev: dict, year: int) -> dt.date | None:
    try:
        if "lunar" in ev:
            from lunardate import LunarDate

            m, d = ev["lunar"]
            return LunarDate(year, m, d).to_solar_date()
        if "solar" in ev:
            m, d = ev["solar"]
            return dt.date(year, m, d)
        if "nth_sunday" in ev:
            m, n = ev["nth_sunday"]
            first = dt.date(year, m, 1)
            return first + dt.timedelta(days=(6 - first.weekday()) % 7 + 7 * (n - 1))
    except Exception:
        return None
    return None


def upcoming(days: int = 45, today: dt.date | None = None) -> list[dict]:
    """Các ngày đặc biệt sắp tới (kể cả hôm nay), sắp theo ngày."""
    today = today or dt.date.today()
    out = []
    for ev in SPECIAL_DAYS:
        for y in (today.year - 1, today.year, today.year + 1):
            d = _event_date(ev, y)
            if d and 0 <= (d - today).days <= days:
                out.append({**ev, "date": d.isoformat(), "days_left": (d - today).days,
                            "active": (d - today).days <= ev.get("lead", 3)})
    return sorted(out, key=lambda e: e["days_left"])


def lunar_today(today: dt.date | None = None) -> str:
    try:
        from lunardate import LunarDate

        ld = LunarDate.from_solar_date(*(today or dt.date.today()).timetuple()[:3])
        return f"{ld.day}/{ld.month} âm lịch"
    except Exception:
        return ""


def seasonal_preferences() -> tuple[list[str], list[str]]:
    """Kịch bản / chủ đề nên ưu tiên lúc này: ngày lễ sắp tới (đăng trước vài ngày) rồi tới mùa."""
    scripts, topics = [], []
    for ev in upcoming(30):
        if ev["active"]:
            scripts += ev.get("scripts", [])
            topics += ev.get("topics", [])
    for s in active_seasons():
        scripts += s.get("scripts", [])
        topics += s.get("topics", [])
    return list(dict.fromkeys(scripts)), list(dict.fromkeys(topics))


# ---------------- số liệu & xếp hạng ----------------

def score(m: dict) -> float:
    """Điểm 1 video: lượt xem FB + TikTok, cộng thêm tương tác (bình luận, chia sẻ nặng ký hơn)."""
    fb = m.get("fb", {})
    tk = m.get("tiktok", {})
    plays = (fb.get("blue_reels_play_count") or fb.get("fb_reels_total_plays") or 0) + (tk.get("views") or 0)
    inter = (fb.get("post_video_social_actions.comment", 0) * 3 + fb.get("post_video_social_actions.share", 0) * 5
             + fb.get("post_video_social_actions.reaction", 0) + (tk.get("likes") or 0)
             + (tk.get("comments") or 0) * 3 + (tk.get("shares") or 0) * 5)
    return plays + inter * 10


def leaderboard() -> list[dict]:
    from .util import OUTPUT

    metrics = _load(METRICS, {})
    tiktok = _load(TIKTOK, {})
    rows = []
    folders = [d for d in OUTPUT.iterdir() if (d / "video.mp4").exists()] if OUTPUT.exists() else []
    for d in folders:
        folder = d.name
        m = dict(metrics.get(folder, {}))
        if folder in tiktok:
            m["tiktok"] = tiktok[folder]
        meta = _load(d / "script.json", {})
        rows.append({"folder": folder, "title": meta.get("title", folder), "hook": meta.get("hook"),
                     "topic": meta.get("topic"), "id": meta.get("id"),
                     "created": dt.datetime.fromtimestamp((d / "video.mp4").stat().st_mtime).isoformat(timespec="minutes"),
                     "fb": m.get("fb", {}), "tiktok": m.get("tiktok", {}), "score": score(m)})
    return sorted(rows, key=lambda r: r["score"], reverse=True)


def winners(n: int = 5) -> list[dict]:
    return [r for r in leaderboard() if r["score"] > 0][:n]


def winners_prompt() -> str:
    """Đoạn chèn vào prompt viết kịch bản: học theo câu móc / chủ đề của các tập được xem nhiều nhất."""
    w = winners(5)
    if not w:
        return ""
    lines = "\n".join(f'- "{r["hook"]}" (chủ đề: {r["topic"]}, điểm {int(r["score"])})' for r in w)
    return ("\nCÁC TẬP ĐƯỢC XEM NHIỀU NHẤT CỦA KÊNH (học theo kiểu câu móc, nhịp và kiểu tình huống của chúng, "
            f"nhưng KHÔNG lặp lại nội dung):\n{lines}\n")


# ---------------- TikTok (nhập tay) ----------------

def tiktok_update(folder: str, data: dict) -> dict:
    all_ = _load(TIKTOK, {})
    cur = all_.get(folder, {})
    for k in ("posted", "skip", "url", "views", "likes", "comments", "shares"):
        if k in data:
            cur[k] = data[k]
    if data.get("posted") and not cur.get("posted_at"):
        cur["posted_at"] = dt.datetime.now().isoformat(timespec="minutes")
    all_[folder] = cur
    _save(TIKTOK, all_)
    return cur


def tiktok_all() -> dict:
    return _load(TIKTOK, {})


# ---------------- bình luận ----------------

REPLY_PROMPT = """Bạn là admin trang Facebook "Hạt gạo quê" - phim hoạt hình hoài niệm tuổi thơ 8x 9x với bé Bin và ông bà.
Hãy viết câu trả lời cho từng bình luận dưới video "<<TITLE>>".
Giọng: ấm áp, thân thiện, xưng "Bin" hoặc "mình", gọi người bình luận là "bạn"; ngắn 1-2 câu; nếu họ kể kỷ niệm thì
đồng cảm và hỏi thêm một câu nhỏ để họ kể tiếp; có thể dùng 1 emoji. Không quảng cáo, không xin follow, không hứa hẹn gì.
Bình luận tục tĩu, spam, công kích thì trả về reply rỗng "".
Chỉ trả về JSON: {"replies": [{"id": "...", "reply": "..."}]}

Các bình luận:
<<COMMENTS>>
"""


def _draft_replies(title: str, items: list[dict], cfg: dict) -> dict[str, str]:
    from . import polli

    if not items or not polli.key():
        return {}
    body = {"model": cfg["script"].get("pollinations_model", "openai/gpt-5.4-mini"),
            "messages": [{"role": "user", "content": REPLY_PROMPT.replace("<<TITLE>>", title).replace(
                "<<COMMENTS>>", "\n".join(f'- id={c["id"]}: {c["message"]}' for c in items))}],
            "response_format": {"type": "json_object"}}
    r = requests.post(f"{polli.GEN}/v1/chat/completions", json=body, headers=polli._auth(), timeout=180)
    if r.status_code >= 400:
        raise RuntimeError(f"AI lỗi {r.status_code}: {r.text[:200]}")
    data = json.loads(r.json()["choices"][0]["message"]["content"])
    return {x["id"]: x.get("reply", "") for x in data.get("replies", [])}


def comments_all() -> dict:
    return _load(COMMENTS, {})


def set_comment(cid: str, **fields) -> dict:
    all_ = _load(COMMENTS, {})
    if cid in all_:
        all_[cid].update(fields)
        _save(COMMENTS, all_)
    return all_.get(cid, {})


def send_reply(cid: str, text: str, cfg: dict) -> None:
    from . import facebook

    facebook.reply(cid, text, cfg)
    set_comment(cid, status="replied", reply=text, replied_at=dt.datetime.now().isoformat(timespec="minutes"))


# ---------------- đồng bộ (chạy mỗi ngày / bấm nút) ----------------

def sync(cfg: dict) -> dict:
    from . import facebook

    s = st.load()
    metrics = _load(METRICS, {})
    comments = _load(COMMENTS, {})
    gcfg = cfg.get("growth", {})
    now = dt.datetime.now().timestamp()
    n_metrics = n_new = n_sent = 0

    for v in s["videos"]:
        fb = v.get("facebook") or {}
        vid = fb.get("video_id")
        if not vid or (fb.get("publish_ts") and fb["publish_ts"] > now):
            continue  # chưa đăng (đang hẹn giờ)
        folder = Path(v["folder"]).name
        # bình luận đầu chưa đăng được lúc hẹn giờ -> đăng bây giờ
        if fb.get("first_comment_pending"):
            try:
                fb["first_comment_id"] = facebook.comment(vid, fb.pop("first_comment_pending"), cfg)
            except Exception as e:
                log(f"  bình luận đầu lỗi: {e}")
        try:
            metrics[folder] = {**metrics.get(folder, {}), "fb": facebook.reel_insights(vid, cfg),
                               "fetched": dt.datetime.now().isoformat(timespec="minutes")}
            n_metrics += 1
        except Exception as e:
            log(f"  số liệu {folder} lỗi: {e}")
        try:
            new = []
            for c in facebook.comments(vid, cfg):
                if c["id"] in comments or c["id"] == fb.get("first_comment_id"):
                    continue
                comments[c["id"]] = {"id": c["id"], "folder": folder, "title": v.get("title"),
                                     "from": (c.get("from") or {}).get("name", "Ai đó"), "message": c.get("message", ""),
                                     "created": c.get("created_time"), "status": "new"}
                new.append(comments[c["id"]])
            if new:
                drafts = _draft_replies(v.get("title", ""), new, cfg)
                for c in new:
                    d = drafts.get(c["id"], "")
                    c["draft"] = d
                    c["status"] = "draft" if d else "skip"
                    if d and gcfg.get("auto_reply"):
                        try:
                            send_reply(c["id"], d, cfg)
                            c.update(status="replied", reply=d)
                            n_sent += 1
                        except Exception as e:
                            log(f"  gửi trả lời lỗi: {e}")
                n_new += len(new)
        except Exception as e:
            log(f"  bình luận {folder} lỗi: {e}")

    st.save(s)
    _save(METRICS, metrics)
    _save(COMMENTS, comments)
    log(f"Đồng bộ: số liệu {n_metrics} video, {n_new} bình luận mới, đã tự trả lời {n_sent}")
    return {"metrics": n_metrics, "new_comments": n_new, "auto_replied": n_sent}
