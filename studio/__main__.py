"""Cách dùng:
  python -m studio run [--count N] [--no-post]   Tạo N video (mặc định theo config) và lên lịch đăng
  python -m studio make <script.json>            Tạo video từ 1 file kịch bản bất kỳ
  python -m studio post <thư mục output>         Đăng (lại) một video đã tạo lên Facebook
  python -m studio check                         Kiểm tra cài đặt
  python -m studio status                        Xem các video đã tạo
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
import traceback
from pathlib import Path

from . import facebook, images, motion, outro, script_gen, state as st, tts, video
from .util import OUTPUT, ffmpeg_exe, load_config, log


def caption_text(script: dict, cfg: dict) -> str:
    parts = [script["title"]]
    if script.get("caption"):
        parts.append(script["caption"])
    parts.append(" ".join(script["hashtags"]))
    if cfg.get("ai_note"):
        parts.append(cfg["ai_note"])
    return "\n\n".join(parts)


def build(script: dict, cfg: dict) -> Path:
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    out = OUTPUT / f"{stamp}_{script['id']}"
    work = out / "work"
    work.mkdir(parents=True, exist_ok=True)
    with open(out / "script.json", "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in script.items() if not k.startswith("_")}, f, ensure_ascii=False, indent=2)

    log(f"=== Bắt đầu: {script['title']} ===")
    wavs = tts.synth_scenes(script["scenes"], work, cfg)
    imgs = images.generate(script, work, cfg)
    clips = motion.animate(script, imgs, work, cfg, wavs)
    end = outro.scene(cfg)
    if end:
        from PIL import Image

        owork = work / "outro"
        owork.mkdir(exist_ok=True)
        wavs.append(tts.synth_scenes([end], owork, cfg)[0])
        oimg = owork / "outro.jpg"
        grade = cfg["images"].get("color_grade", cfg["images"].get("retro_filter", False))
        images.finish(Image.open(end["_image"]), grade).save(oimg, quality=92)
        imgs.append([oimg])
        script["scenes"].append(end)
    video.assemble(script, wavs, imgs, out, work, cfg, clips)
    shutil.copy(imgs[0][0], out / "cover.jpg")
    (out / "caption.txt").write_text(caption_text(script, cfg), encoding="utf-8")
    cost = script.get("_cost_images", 0.0) + script.get("_cost_motion", 0.0)
    vnd = cost * float(cfg.get("usd_to_vnd", 26000))
    script["_cost_usd"] = round(cost, 4)
    (out / "cost.txt").write_text(f"{cost:.4f} USD ~ {vnd:,.0f} VND\n", encoding="utf-8")
    log(f"Chi phí video: {cost:.4f} USD ~ {vnd:,.0f}đ")
    if not cfg.get("keep_work_files"):
        shutil.rmtree(work, ignore_errors=True)
    return out


def _scheduled(s: dict) -> list[float]:
    return [v["facebook"]["publish_ts"] for v in s["videos"] if v.get("facebook") and v["facebook"].get("publish_ts")]


def publish(out: Path, cfg: dict, s: dict) -> dict | None:
    fb = cfg["publish"]["facebook"]
    if not fb.get("enabled"):
        log("Facebook: đang tắt (publish.facebook.enabled = false) -> chỉ tạo video")
        return None
    times = fb.get("times") or [fb.get("time", "19:30")]
    ts = facebook.next_slot(times, _scheduled(s)) if fb.get("mode") == "scheduled" else None
    caption = (out / "caption.txt").read_text(encoding="utf-8")
    vid = facebook.post_reel(out / "video.mp4", caption, cfg, ts)
    rec = {"video_id": vid, "publish_ts": ts}
    # Bình luận đầu tiên: câu hỏi gợi người xem kể kỷ niệm (tăng bình luận -> tăng phân phối)
    meta = json.loads((out / "script.json").read_text(encoding="utf-8")) if (out / "script.json").exists() else {}
    first = meta.get("first_comment") or (meta.get("scenes") or [{}])[-1].get("text")
    if first and fb.get("first_comment", True):
        try:
            rec["first_comment_id"] = facebook.comment(vid, f"📌 {first} Kể cho Bin nghe ở dưới nha 👇", cfg)
        except Exception as e:
            log(f"  (chưa đăng được bình luận đầu: {e} - sẽ thử lại khi đồng bộ)")
            rec["first_comment_pending"] = f"📌 {first} Kể cho Bin nghe ở dưới nha 👇"
    return rec


def cmd_run(args, cfg) -> int:
    s = st.load()
    count = args.count or int(cfg.get("videos_per_run", 1))
    failed = 0
    for _ in range(count):
        try:
            script = script_gen.next_script(cfg, s)
            script["_episode"] = len(s["videos"]) + 1
            out = build(script, cfg)
        except Exception as e:
            failed += 1
            log(f"LỖI khi tạo video: {e}")
            log(traceback.format_exc())
            continue

        if script.get("_source") == "bank":
            s["used_bank"].append(script["id"])
        s["used_topics"].append(script["topic"])
        rec = {"id": script["id"], "title": script["title"], "folder": str(out),
               "source": script.get("_source"), "created": dt.datetime.now().isoformat(timespec="seconds"),
               "facebook": None}
        s["videos"].append(rec)
        st.save(s)

        if not args.no_post:
            try:
                rec["facebook"] = publish(out, cfg, s)
            except Exception as e:
                rec["facebook_error"] = str(e)
                log(f"LỖI khi đăng Facebook: {e}")
            st.save(s)
        log(f"=== Xong: {out} ===")
    return 1 if failed else 0


def cmd_make(args, cfg) -> int:
    """Nhận đường dẫn file kịch bản .json, hoặc id của một kịch bản trong kho data/scripts."""
    if Path(args.script).is_file():
        with open(args.script, encoding="utf-8") as f:
            raw = json.load(f)
    else:
        raw = next((b for b in script_gen._bank() if b.get("id") == args.script), None)
        if raw is None:
            print(f"Không tìm thấy kịch bản '{args.script}'")
            return 1
    script = script_gen.validate(dict(raw))
    out = build(script, cfg)
    log(f"Xong: {out}")
    return 0


def cmd_post(args, cfg) -> int:
    s = st.load()
    out = Path(args.folder).resolve()
    res = publish(out, cfg, s)
    for v in s["videos"]:
        if Path(v["folder"]).resolve() == out:
            v["facebook"] = res
            v.pop("facebook_error", None)
    st.save(s)
    return 0


def cmd_check(args, cfg) -> int:
    import os

    ok = True
    print("ffmpeg:", ffmpeg_exe())
    try:
        import vieneu  # noqa: F401

        print("Giọng đọc VieNeu:", cfg.get("tts", {}).get("vieneu_voice"), "(đã cài)")
    except Exception as e:
        ok = False
        print("VieNeu LỖI:", e)
    print("GPU NVIDIA (torch CUDA):", "có" if images._has_cuda() else "không -> dùng Pollinations")
    print("GEMINI_API_KEY:", "có" if os.environ.get("GEMINI_API_KEY") else "chưa có (sẽ chỉ dùng kho kịch bản/Ollama)")
    if cfg["publish"]["facebook"].get("enabled"):
        try:
            print("Facebook Page:", facebook.check_token(cfg))
        except Exception as e:
            ok = False
            print("Facebook LỖI:", e)
    else:
        print("Facebook: đang tắt")
    s = st.load()
    bank_left = len([b for b in script_gen._bank() if b.get("id") not in s["used_bank"]])
    topics_left = len([t for t in script_gen._topics() if t not in s["used_topics"]])
    print(f"Còn {bank_left} kịch bản viết sẵn, {topics_left} chủ đề chờ AI viết")
    return 0 if ok else 1


def cmd_status(args, cfg) -> int:
    s = st.load()
    for v in s["videos"][-30:]:
        fb = v.get("facebook") or {}
        when = dt.datetime.fromtimestamp(fb["publish_ts"]).strftime("%d/%m %H:%M") if fb.get("publish_ts") else ""
        flag = "FB lỗi" if v.get("facebook_error") else (f"FB {when or 'đã đăng'}" if fb else "chưa đăng")
        print(f"{v['created'][:16]}  [{flag:>14}]  {v['title']}")
    if not s["videos"]:
        print("Chưa có video nào.")
    return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    p = argparse.ArgumentParser(prog="studio", description="Hoài Niệm Studio")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--count", type=int)
    r.add_argument("--no-post", action="store_true")
    m = sub.add_parser("make")
    m.add_argument("script")
    po = sub.add_parser("post")
    po.add_argument("folder")
    sub.add_parser("check")
    sub.add_parser("status")
    ch = sub.add_parser("characters", help="Vẽ ảnh mẫu nhân vật (cần POLLINATIONS_TOKEN)")
    ch.add_argument("keys", nargs="*", help="Chỉ vẽ lại các nhân vật này, ví dụ: BIN BA")
    w = sub.add_parser("write", help="Nhờ AI viết kịch bản cho một chủ đề (lưu vào data/scripts)")
    w.add_argument("topic")
    sp = sub.add_parser("sample", help="Tạo file nghe thử một giọng")
    sp.add_argument("provider", choices=["vieneu", "mai", "edge"])
    sp.add_argument("voice")
    sp.add_argument("out")
    sp.add_argument("--text", default="Trưa hè, tiếng rao ai đồng nát sắt vụn bán đi vang đầu ngõ. "
                                       "Bin bật dậy như lò xo, chạy ù ra cổng.")
    au = sub.add_parser("audio-ai", help="Dùng AI tạo nhạc nền + âm thanh không khí (tốn phí, tạo 1 lần)")
    au.add_argument("--only", choices=["music", "sfx"], help="Chỉ tạo nhạc hoặc chỉ âm thanh")
    au.add_argument("--redo", action="store_true", help="Tạo lại cả file đã có")
    sub.add_parser("sync", help="Lấy số liệu + bình luận Facebook, AI soạn trả lời")
    sub.add_parser("outro", help="Tạo (lại) ảnh cảnh kết: Bin vẫy tay")
    sub.add_parser("gpu-test", help="Kiểm tra card NVIDIA: tạo thử 1 ảnh + 1 clip trên máy")
    wb = sub.add_parser("web", help="Mở trang quản lý trên trình duyệt")
    wb.add_argument("--no-browser", action="store_true")
    args = p.parse_args()
    cfg = load_config()
    return {"run": cmd_run, "make": cmd_make, "post": cmd_post, "check": cmd_check, "status": cmd_status,
            "characters": cmd_characters, "write": cmd_write, "sample": cmd_sample, "web": cmd_web,
            "audio-ai": cmd_audio_ai, "sync": cmd_sync, "outro": cmd_outro, "gpu-test": cmd_gpu_test}[args.cmd](args, cfg)


def cmd_gpu_test(args, cfg) -> int:
    import time as _t

    from . import local_gpu

    gi = local_gpu.info()
    print("GPU:", gi)
    if not gi.get("cuda"):
        print("=> Chưa dùng được GPU. Cài driver NVIDIA mới nhất rồi chạy setup-gpu.bat.")
        return 1
    out = OUTPUT / "gpu_test"
    out.mkdir(parents=True, exist_ok=True)
    prompt = "{BIN} running happily along a sunny village lane holding a paper kite, {BA} smiling at the gate"
    t0 = _t.time()
    try:
        img = images._local(prompt, 1234, cfg)
        images.finish(img, False).save(out / "anh_thu.jpg", quality=92)
        print(f"Ảnh: OK sau {_t.time() - t0:.0f}s -> {out / 'anh_thu.jpg'}")
    except Exception:
        traceback.print_exc()
        return 1
    local_gpu.release()
    t1 = _t.time()
    try:
        local_gpu.video(out / "anh_thu.jpg", "3D animated cartoon, Bin runs happily and waves, grandma laughs, smooth motion",
                        out / "clip_thu.mp4", 4, cfg)
        print(f"Clip: OK sau {_t.time() - t1:.0f}s -> {out / 'clip_thu.mp4'}")
    except Exception:
        traceback.print_exc()
        print("=> Clip lỗi. Gửi log này để được sửa; video vẫn chạy được bằng ảnh tĩnh hoặc Seedance.")
        return 1
    print("=> GPU sẵn sàng: ảnh + cử động sẽ chạy trên máy, miễn phí, mọi cảnh đều có cử động.")
    return 0


def cmd_outro(args, cfg) -> int:
    p = outro.outro_image(cfg)
    print(f"Ảnh cảnh kết: {p}" if p else "Chưa tạo được ảnh cảnh kết (cần ảnh mẫu Bin hoặc key Pollinations)")
    return 0 if p else 1


def cmd_sync(args, cfg) -> int:
    from . import growth

    if not cfg["publish"]["facebook"].get("enabled"):
        print("Facebook đang tắt - chưa có gì để đồng bộ. (Số liệu TikTok nhập tay trong trang quản lý.)")
        return 0
    growth.sync(cfg)
    return 0


def cmd_audio_ai(args, cfg) -> int:
    from . import audio_ai

    music = None if args.only in (None, "music") else []
    sfx = None if args.only in (None, "sfx") else []
    res = audio_ai.generate(music, sfx, skip_existing=not args.redo)
    for f in res["failed"]:
        print("LỖI:", f)
    if any("402" in f for f in res["failed"]):
        print("=> Tài khoản Pollinations chưa đủ số dư trả phí. Nạp tại https://enter.pollinations.ai/top-up")
    return 1 if res["failed"] and not res["done"] else 0


def cmd_write(args, cfg) -> int:
    d = script_gen.write_for_topic(args.topic, cfg)
    print(f"Đã lưu kịch bản '{d['title']}' (id: {d['id']})")
    return 0


def cmd_sample(args, cfg) -> int:
    from pathlib import Path as _P

    out = _P(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tcfg = dict(cfg.get("tts", {}))
    raw = out.with_suffix(".raw.wav" if args.provider == "vieneu" else ".raw.mp3")
    if args.provider == "vieneu":
        tcfg["vieneu_voice"] = args.voice
        tts._vieneu_say(args.text, raw, tcfg)
    elif args.provider == "mai":
        tcfg["mai"] = {**tcfg.get("mai", {}), "voice": args.voice, "speakers": {}}
        tts._mai_say(args.text, raw, tcfg)
    else:
        tcfg["edge_voice"] = args.voice
        tts._edge_say(args.text, raw, tcfg)
    tts._to_wav(raw, out)
    raw.unlink(missing_ok=True)
    print(f"Đã tạo file nghe thử: {out}")
    return 0


def cmd_web(args, cfg) -> int:
    from . import web

    web.serve(open_browser=not args.no_browser)
    return 0


def cmd_characters(args, cfg) -> int:
    paths = images.make_character_refs(cfg, args.keys or None)
    print("Đã vẽ ảnh mẫu:\n  " + "\n  ".join(str(p) for p in paths))
    print("Xem các ảnh trên; không ưng nhân vật nào thì sửa mô tả trong data/characters.json rồi chạy lại cho nhân vật đó.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
