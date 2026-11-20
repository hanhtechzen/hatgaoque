"""Video tổng hợp tuần (3-5 phút): ghép các tập trong tuần thành 1 video dài.

Facebook chỉ cho chèn quảng cáo kiếm tiền (in-stream) vào video từ 3 phút trở lên -> đây là đường kiếm tiền.
Mỗi tập được cắt bỏ cảnh kết (chỉ giữ cảnh kết ở cuối video tổng hợp), có màn mở đầu có chữ.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from .cover import make_cover
from .util import OUTPUT, ffmpeg_exe, log, run

PREFIX = "tonghop_"


def _episodes(days: int) -> list[Path]:
    since = dt.datetime.now() - dt.timedelta(days=days)
    eps = []
    for d in OUTPUT.iterdir() if OUTPUT.exists() else []:
        if d.name.startswith(PREFIX) or not (d / "video.mp4").exists() or not (d / "timeline.json").exists():
            continue
        if dt.datetime.fromtimestamp((d / "video.mp4").stat().st_mtime) >= since:
            eps.append(d)
    # mỗi kịch bản chỉ lấy bản mới nhất (tránh trùng khi dựng lại nhiều lần)
    latest: dict[str, Path] = {}
    for d in sorted(eps, key=lambda p: p.stat().st_mtime):
        sid = json.loads((d / "script.json").read_text(encoding="utf-8")).get("id", d.name) if (d / "script.json").exists() else d.name
        latest[sid] = d
    return sorted(latest.values(), key=lambda p: p.stat().st_mtime)


def build(cfg: dict, days: int = 7, min_sec: int = 180) -> Path | None:
    eps = _episodes(days)
    if len(eps) < 2:
        log(f"Tổng hợp: chỉ có {len(eps)} tập trong {days} ngày qua, chưa đủ để ghép")
        return None
    ff = ffmpeg_exe()
    out = OUTPUT / f"{PREFIX}{dt.date.today():%Y-%m-%d}"
    work = out / "work"
    work.mkdir(parents=True, exist_ok=True)
    tl = [json.loads((d / "timeline.json").read_text(encoding="utf-8")) for d in eps]
    titles = [json.loads((d / "script.json").read_text(encoding="utf-8")).get("title", d.name) for d in eps]
    total = 2.5 + sum(t["main_end"] for t in tl) + (tl[-1]["total"] - tl[-1]["main_end"])
    if total < min_sec:
        log(f"  (lưu ý: tổng {total:.0f}s < {min_sec}s - Facebook cần từ 3 phút để chèn quảng cáo)")

    # Màn mở đầu: ảnh Bin vẫy tay (không chữ) + tiêu đề to; chưa có ảnh đó thì lấy khung giữa tập 1
    from .util import ASSETS

    outro_png = ASSETS / "outro" / "outro.png"
    if outro_png.exists():
        import shutil as _sh

        _sh.copy(outro_png, work / "first.png")
    else:
        run([ff, "-y", "-ss", f"{tl[0]['main_end'] / 2:.2f}", "-i", str(eps[0] / "video.mp4"), "-frames:v", "1",
             str(work / "first.png")])
    title = f"{len(eps)} chuyện tuổi thơ tuần này"
    make_cover(work / "first.png", work / "intro.jpg", title, cfg)

    inputs = ["-loop", "1", "-t", "2.5", "-i", str(work / "intro.jpg"),
              "-f", "lavfi", "-t", "2.5", "-i", "anullsrc=r=44100:cl=stereo"]
    fc, labels = [], []
    fc.append("[0:v]scale=1080:1920,setsar=1,fps=30,format=yuv420p,fade=t=out:st=2.2:d=0.3[v0];[1:a]anull[a0]")
    labels.append("[v0][a0]")
    idx = 2
    for k, (d, t) in enumerate(zip(eps, tl)):
        last = k == len(eps) - 1
        dur = t["total"] if last else t["main_end"]  # tập cuối giữ cảnh kết mời theo dõi
        inputs += ["-t", f"{dur:.3f}", "-i", str(d / "video.mp4")]
        fc.append(f"[{idx}:v]scale=1080:1920,setsar=1,fps=30,format=yuv420p[v{k + 1}];"
                  f"[{idx}:a]aformat=sample_rates=44100:channel_layouts=stereo[a{k + 1}]")
        labels.append(f"[v{k + 1}][a{k + 1}]")
        idx += 1
    fc.append(f"{''.join(labels)}concat=n={len(labels)}:v=1:a=1[v][a]")
    final = out / "video.mp4"
    run([ff, "-y", *inputs, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-color_range", "tv",
         "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", str(final)])

    make_cover(work / "first.png", out / "cover.jpg", title, cfg)
    listing = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(titles))
    caption = (f"{title.capitalize()} 🌾 Xem liền một mạch cùng Bin và ông bà:\n{listing}\n\n"
               "Bạn thích chuyện nào nhất? Kể Bin nghe với nhé 👇\n\n#hatgaoque #8x9x #tuoitho #ongba #hoainiem")
    (out / "caption.txt").write_text(caption, encoding="utf-8")
    (out / "script.json").write_text(json.dumps({"id": out.name, "title": title.capitalize(), "hook": title,
                                                 "compilation": [d.name for d in eps]}, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    (out / "timeline.json").write_text(json.dumps({"total": round(total, 3), "main_end": round(total, 3),
                                                   "compilation": True}), encoding="utf-8")
    import shutil

    shutil.rmtree(work, ignore_errors=True)
    log(f"Tổng hợp: xong {final} ({len(eps)} tập, ~{total / 60:.1f} phút)")
    return out
