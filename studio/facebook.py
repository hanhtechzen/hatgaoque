"""Đăng Reels lên Facebook Page qua Graph API (miễn phí)."""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

import requests

from .util import log


def _check(r: requests.Response, step: str) -> dict:
    try:
        data = r.json()
    except ValueError:
        data = {}
    if r.status_code >= 400 or "error" in data:
        msg = data.get("error", {}).get("message") if isinstance(data.get("error"), dict) else r.text[:400]
        raise RuntimeError(f"Facebook lỗi ở bước {step}: {msg}")
    return data


def _creds() -> tuple[str, str]:
    page_id = os.environ.get("FB_PAGE_ID", "").strip()
    token = os.environ.get("FB_PAGE_TOKEN", "").strip()
    if not page_id or not token:
        raise RuntimeError("Thiếu FB_PAGE_ID / FB_PAGE_TOKEN trong file .env")
    return page_id, token


def next_slot(times: list[str] | str, taken: list[float] | float | None) -> int:
    """Khung giờ đăng trống gần nhất (vd ["11:30", "19:30"] = 2 video/ngày), bỏ qua giờ đã có video hẹn."""
    if isinstance(times, str):
        times = [times]
    taken = [taken] if isinstance(taken, (int, float)) else list(taken or [])
    now = dt.datetime.now()
    for day in range(0, 60):
        base = (now + dt.timedelta(days=day)).replace(second=0, microsecond=0)
        for t in sorted(times):
            hh, mm = (int(x) for x in t.split(":"))
            slot = base.replace(hour=hh, minute=mm)
            if slot < now + dt.timedelta(minutes=20):
                continue
            ts = slot.timestamp()
            if all(abs(ts - x) > 1800 for x in taken):
                return int(ts)
    raise RuntimeError("Không tìm được khung giờ trống trong 60 ngày tới")


def _get(path: str, cfg: dict, **params) -> dict:
    _, token = _creds()
    ver = cfg["publish"]["facebook"].get("graph_version", "v23.0")
    r = requests.get(f"https://graph.facebook.com/{ver}/{path}", params={**params, "access_token": token}, timeout=60)
    return _check(r, path)


def _post(path: str, cfg: dict, **data) -> dict:
    _, token = _creds()
    ver = cfg["publish"]["facebook"].get("graph_version", "v23.0")
    r = requests.post(f"https://graph.facebook.com/{ver}/{path}", data={**data, "access_token": token}, timeout=60)
    return _check(r, path)


REEL_METRICS = ["blue_reels_play_count", "fb_reels_total_plays", "post_impressions_unique",
                "post_video_avg_time_watched", "post_video_followers", "post_video_social_actions"]


def reel_insights(video_id: str, cfg: dict) -> dict:
    """Số liệu 1 Reel. Hỏi từng chỉ số riêng để chỉ số nào Facebook không hỗ trợ thì bỏ qua."""
    out: dict = {}
    for m in REEL_METRICS:
        try:
            data = _get(f"{video_id}/video_insights", cfg, metric=m).get("data", [])
        except RuntimeError:
            continue
        for item in data:
            val = (item.get("values") or [{}])[0].get("value")
            if isinstance(val, dict):  # vd social_actions: {"REACTION":.., "COMMENT":.., "SHARE":..}
                for k, v in val.items():
                    out[f"{m}.{k.lower()}"] = v
            elif val is not None:
                out[m] = val
    try:
        v = _get(video_id, cfg, fields="permalink_url,length,created_time,description")
        out.update({"permalink": v.get("permalink_url"), "length": v.get("length"), "created_time": v.get("created_time")})
    except RuntimeError:
        pass
    return out


def comments(object_id: str, cfg: dict) -> list[dict]:
    data = _get(f"{object_id}/comments", cfg, fields="id,from,message,created_time,comment_count",
                filter="toplevel", order="reverse_chronological", limit=50)
    return data.get("data", [])


def reply(comment_id: str, message: str, cfg: dict) -> str:
    return _post(f"{comment_id}/comments", cfg, message=message).get("id", "")


def comment(object_id: str, message: str, cfg: dict) -> str:
    return _post(f"{object_id}/comments", cfg, message=message).get("id", "")


def post_reel(video: Path, description: str, cfg: dict, publish_ts: int | None) -> str:
    page_id, token = _creds()
    ver = cfg["publish"]["facebook"].get("graph_version", "v23.0")
    base = f"https://graph.facebook.com/{ver}/{page_id}/video_reels"

    start = _check(requests.post(base, data={"upload_phase": "start", "access_token": token}, timeout=60), "start")
    video_id = start["video_id"]
    upload_url = start.get("upload_url") or f"https://rupload.facebook.com/video-upload/{ver}/{video_id}"

    size = video.stat().st_size
    with open(video, "rb") as f:
        up = requests.post(
            upload_url,
            headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)},
            data=f,
            timeout=900,
        )
    _check(up, "upload")

    data = {"upload_phase": "finish", "video_id": video_id, "description": description, "access_token": token}
    if publish_ts:
        data.update(video_state="SCHEDULED", scheduled_publish_time=publish_ts)
    else:
        data.update(video_state="PUBLISHED")
    _check(requests.post(base, data=data, timeout=120), "finish")

    when = dt.datetime.fromtimestamp(publish_ts).strftime("%d/%m %H:%M") if publish_ts else "ngay bây giờ"
    log(f"Facebook: đã tải lên Reel {video_id}, đăng lúc {when}")
    return video_id


def check_token(cfg: dict) -> str:
    page_id, token = _creds()
    ver = cfg["publish"]["facebook"].get("graph_version", "v23.0")
    r = requests.get(f"https://graph.facebook.com/{ver}/{page_id}", params={"fields": "name", "access_token": token}, timeout=30)
    return _check(r, "kiểm tra token").get("name", page_id)
