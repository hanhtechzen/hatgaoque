"""Dựng video dọc 9:16 theo công thức video ngắn đang lên xu hướng:

- 0-3s: câu "móc" chữ to giữa màn hình + giọng đọc vào ngay, không màn đen.
- Cắt cảnh nhanh (2-4 giây/cảnh), ảnh luôn chuyển động (zoom/lia/cận cảnh).
- Phụ đề kiểu CapCut: 2-4 chữ một lần, chữ đang đọc sáng màu vàng, bật nảy.
- Âm thanh 3 lớp: giọng đọc + nhạc nền tự nhỏ lại khi có giọng + âm thanh không khí (ve, mưa, bếp củi...).
"""
from __future__ import annotations

import random
import re
import shutil
import wave
from pathlib import Path

from .tts import SAMPLE_RATE, wav_samples
from .util import ASSETS, ffmpeg_exe, log, run

W, H = 1080, 1920
YELLOW = "&H005AD6FF&"
CLOSEUPS = False  # đặt từ config video.closeup_shots
WHITE = "&H00FFFFFF&"
AUDIO_EXT = {".mp3", ".m4a", ".wav", ".ogg"}


# ---------- phụ đề ASS ----------

def _t(sec: float) -> str:
    sec = max(0.0, sec)
    return f"{int(sec // 3600)}:{int(sec % 3600 // 60):02d}:{sec % 60:05.2f}"


def _clean(text: str) -> str:
    text = re.sub(r"\[[^\]]*\]", "", text)  # thẻ cảm xúc VieNeu như [cười]
    return text.replace("{", "(").replace("}", ")").replace("\\", "/").strip()


def _chunks(text: str, max_words: int) -> list[list[str]]:
    words = _clean(text).split()
    out, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= max_words or re.search(r"[,.!?…:;]$", w):
            out.append(cur)
            cur = []
    if cur:
        if out and len(cur) == 1 and len(out[-1]) < max_words + 1:
            out[-1].extend(cur)
        else:
            out.append(cur)
    return out


def _weights(words: list[str]) -> list[float]:
    ws = []
    for w in words:
        x = len(w) + 1.5
        if re.search(r"[,;:]$", w):
            x += 2.5
        if re.search(r"[.!?…]$", w):
            x += 4
        ws.append(x)
    return ws


def build_ass(script: dict, speech: list[tuple[float, float]], total: float, out: Path, cfg: dict) -> None:
    vcfg = cfg["video"]
    font = vcfg.get("font_name", "Arial")
    max_words = int(vcfg.get("caption_words", 4))
    header = vcfg.get("series_name", "KÝ ỨC 8X 9X")
    if script.get("_episode"):
        header = f"{header}  •  TẬP {script['_episode']}"

    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding",
        f"Style: Cap,{font},80,&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,-1,0,0,0,100,100,0,0,1,7,3,2,80,80,560,1",
        f"Style: Hook,{font},100,&H005AD6FF,&H005AD6FF,&H00101010,&H78000000,-1,0,0,0,100,100,0,0,1,10,5,5,70,70,0,1",
        f"Style: Head,{font},40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,-1,0,0,0,100,100,2,0,1,4,0,8,40,40,210,1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    if header:
        lines.append(f"Dialogue: 0,{_t(0)},{_t(total)},Head,,0,0,0,,{{\\alpha&H30&}}{_clean(header)}")

    hook = _clean(script.get("hook") or script["title"]).upper()
    hook_end = min(3.0, total)
    lines.append(
        f"Dialogue: 2,{_t(0)},{_t(hook_end)},Hook,,0,0,0,,"
        f"{{\\pos(540,760)\\fad(0,250)\\fscx65\\fscy65\\t(0,160,\\fscx106\\fscy106)\\t(160,260,\\fscx100\\fscy100)}}{hook}"
    )

    names = {"ba": "BÀ", "ong": "ÔNG", "me": "MẸ", "bo": "BỐ"}
    for si, (scene, (start, end)) in enumerate(zip(script["scenes"], speech)):
        if scene.get("_outro"):
            # Cảnh kết: chữ mời theo dõi to ở nửa trên, hiện từ đầu đến hết cảnh, không dùng phụ đề từng chữ
            stop = total
            lines.append(
                f"Dialogue: 2,{_t(start - 0.05)},{_t(stop)},Hook,,0,0,0,,"
                f"{{\\pos(540,520)\\fs88\\fscx70\\fscy70\\t(0,180,\\fscx104\\fscy104)\\t(180,280,\\fscx100\\fscy100)}}"
                f"{_clean(scene.get('_cta', '')).replace('/N', chr(92) + 'N')}"
            )
            continue
        if scene.get("speaker") in names:
            # Nhãn người nói phía trên phụ đề, như phim có thoại
            lines.append(
                f"Dialogue: 1,{_t(start)},{_t(end + 0.35)},Cap,,0,0,0,,"
                f"{{\\pos(540,1230)\\fs52\\c&H00B4C8FF&}}{names[scene['speaker']]}:"
            )
        chunks = _chunks(scene["text"], max_words)
        allw = [w for c in chunks for w in c]
        if not allw:
            continue
        ws = _weights(allw)
        unit = (end - start) / sum(ws)
        t = start
        k = 0
        for ci, chunk in enumerate(chunks):
            times = []
            for _ in chunk:
                d = ws[k] * unit
                times.append((t, t + d))
                t += d
                k += 1
            for wi, (a, b) in enumerate(times):
                if ci == len(chunks) - 1 and wi == len(chunk) - 1:
                    b = b + 0.35  # giữ câu cuối thêm chút trong khoảng nghỉ
                pop = "{\\fscx82\\fscy82\\t(0,90,\\fscx100\\fscy100)}" if wi == 0 else ""
                words = [
                    f"{{\\c{YELLOW}}}{w}{{\\c{WHITE}}}" if j == wi else w for j, w in enumerate(chunk)
                ]
                lines.append(f"Dialogue: 1,{_t(a)},{_t(b)},Cap,,0,0,0,,{pop}{' '.join(words)}")
    out.write_text("\ufeff" + "\n".join(lines) + "\n", encoding="utf-8")


# ---------- cảnh quay ----------

def _shot_clip(ff: str, img: Path, frames: int, fps: int, kind: str, out: Path) -> None:
    n = max(frames, 1)
    if kind == "in":
        z, x, y = f"1+0.13*on/{n}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif kind == "out":
        z, x, y = f"1.13-0.13*on/{n}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif kind == "pan_l":
        z, x, y = "1.15", f"(iw-iw/zoom)*on/{n}", "ih/2-(ih/zoom/2)"
    elif kind == "pan_r":
        z, x, y = "1.15", f"(iw-iw/zoom)*(1-on/{n})", "ih/2-(ih/zoom/2)"
    else:  # "close": cận cảnh một góc ảnh, zoom nhẹ (không phóng quá to để khỏi vỡ hạt)
        fx, fy = random.uniform(0.3, 0.7), random.uniform(0.3, 0.6)
        z, x, y = f"1.25+0.06*on/{n}", f"(iw-iw/zoom)*{fx:.2f}", f"(ih-ih/zoom)*{fy:.2f}"
    if kind == "video":
        # Clip AI 480p/720p: phóng lên 1080x1920, làm nét, thiếu thì giữ khung cuối
        fc = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},"
              f"unsharp=5:5:0.7,fps={fps},tpad=stop_mode=clone:stop_duration=30,format=yuv420p[v]")
    else:
        # Phóng 2x trước khi zoom để chuyển động mượt, không rung giật
        fc = (f"[0:v]scale={W * 2}:{H * 2}:flags=lanczos,zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={W}x{H}:fps={fps},"
              f"format=yuv420p[v]")
    run([ff, "-y", "-i", img, "-filter_complex", fc, "-map", "[v]", "-frames:v", n,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", "-r", fps, out])


def _plan_shots(images: list[list[Path]], scene_frames: list[int], fps: int,
                clips: dict[int, Path] | None = None) -> list[tuple[Path, int, str]]:
    motions = ["in", "pan_l", "out", "pan_r"]
    mi = random.randint(0, 3)
    shots = []
    clips = clips or {}
    for si, (imgs, fr) in enumerate(zip(images, scene_frames)):
        seq = list(imgs)
        if si in clips:
            # Cảnh có clip chuyển động thật: clip trước, ảnh thứ 2 (nếu có) sau
            seq = [(clips[si], "video")] + [(p, None) for p in seq[1:]]
            if len(seq) > 1 and fr < 5 * fps:
                seq = seq[:1]
        # Một ảnh mà cảnh dài -> tách 2 shot: toàn cảnh rồi cận cảnh, để nhịp cắt nhanh hơn
        # (tắt mặc định: phóng cận mặt làm lộ lỗi gương mặt AI, trông rất "ghê")
        elif CLOSEUPS and len(seq) == 1 and fr > 4.2 * fps:
            seq = [(seq[0], None), (seq[0], "close")]
        else:
            seq = [(p, None) for p in seq]
        base, rem = divmod(fr, len(seq))
        for j, (p, kind) in enumerate(seq):
            n = base + (1 if j < rem else 0)
            shots.append((p, n, kind or motions[mi % 4]))
            mi += 1
    return shots


# ---------- âm thanh ----------

def _pick(folder: Path, name: str | None = None) -> Path | None:
    if name:
        sub = folder / name
        cands = [p for p in sub.iterdir() if p.suffix.lower() in AUDIO_EXT] if sub.is_dir() else []
        cands += [p for p in folder.glob(f"{name}.*") if p.suffix.lower() in AUDIO_EXT]
    else:
        cands = [p for p in folder.iterdir() if p.suffix.lower() in AUDIO_EXT] if folder.is_dir() else []
    return random.choice(cands) if cands else None


def _write_narration(wavs: list[Path], lead: int, scene_frames: list[int], fps: int, out: Path) -> None:
    with wave.open(str(out), "wb") as dst:
        dst.setnchannels(1)
        dst.setsampwidth(2)
        dst.setframerate(SAMPLE_RATE)
        for wav, fr in zip(wavs, scene_frames):
            with wave.open(str(wav), "rb") as src:
                n = src.getnframes()
                data = src.readframes(n)
            target = round(fr / fps * SAMPLE_RATE)
            dst.writeframes(b"\x00\x00" * lead + data + b"\x00\x00" * max(0, target - n - lead))


def assemble(script: dict, wavs: list[Path], images: list[list[Path]], out_dir: Path, work: Path, cfg: dict,
             clips: dict[int, Path] | None = None) -> Path:
    ff = ffmpeg_exe()
    vcfg = cfg["video"]
    global CLOSEUPS
    CLOSEUPS = bool(vcfg.get("closeup_shots", False))
    fps = int(vcfg.get("fps", 30))
    gap = float(vcfg.get("scene_gap_sec", 0.3))
    lead_s = 0.06
    lead = int(lead_s * SAMPLE_RATE)

    # Thời lượng từng cảnh theo độ dài câu đọc
    scene_frames, speech, t = [], [], 0.0
    min_outro = float(vcfg.get("outro", {}).get("min_sec", 2.0))
    for wav, sc in zip(wavs, script["scenes"]):
        spoken = wav_samples(wav) / SAMPLE_RATE
        fr = max(int((lead_s + spoken + gap) * fps) + 1, int(1.6 * fps))
        if sc.get("_outro"):
            fr = max(fr + int(0.5 * fps), int(min_outro * fps))  # giữ cảnh kết thêm chút sau lời mời
        speech.append((t + lead_s, t + lead_s + spoken))
        scene_frames.append(fr)
        t += fr / fps
    total = sum(scene_frames) / fps

    # Hình
    shots = _plan_shots(images, scene_frames, fps, clips)
    clips = []
    for i, (img, n, kind) in enumerate(shots):
        clip = work / f"shot_{i:02d}.mp4"
        _shot_clip(ff, img, n, fps, kind, clip)
        clips.append(clip)
    log(f"  dựng {len(clips)} shot hình")
    (work / "clips.txt").write_text("".join(f"file '{c.name}'\n" for c in clips), encoding="utf-8")
    run([ff, "-y", "-f", "concat", "-safe", "0", "-i", "clips.txt", "-c", "copy", "video_silent.mp4"], cwd=work)

    # Phụ đề
    fonts = work / "fonts"
    fonts.mkdir(exist_ok=True)
    shutil.copy(vcfg.get("font", "C:/Windows/Fonts/arialbd.ttf"), fonts)
    build_ass(script, speech, total, work / "captions.ass", cfg)

    # Âm thanh
    _write_narration(wavs, lead, scene_frames, fps, work / "narration.wav")
    music = _pick(ASSETS / "music")
    amb = _pick(ASSETS / "sfx", script.get("ambience")) if script.get("ambience") else None

    inputs = ["-i", "video_silent.mp4", "-i", "narration.wav"]
    fmt = "aformat=sample_rates=44100:channel_layouts=stereo"
    parts = [f"[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,{fmt}" + (",asplit=2[voice][sc]" if music else "[voice]")]
    mix = ["[voice]"]
    idx = 2
    if music:
        inputs += ["-stream_loop", "-1", "-i", str(music)]
        mv = float(vcfg.get("music_volume", 0.22))
        parts.append(
            f"[{idx}:a]{fmt},volume={mv},afade=t=in:d=1,afade=t=out:st={max(0, total - 2):.2f}:d=2[mraw];"
            f"[mraw][sc]sidechaincompress=threshold=0.015:ratio=7:attack=20:release=450[music]"
        )
        mix.append("[music]")
        idx += 1
        log(f"  nhạc nền: {music.name}")
    else:
        log("  (chưa có nhạc nền - bỏ mp3 vào assets/music)")
    if amb:
        inputs += ["-stream_loop", "-1", "-i", str(amb)]
        av = float(vcfg.get("ambience_volume", 0.35))
        parts.append(
            f"[{idx}:a]{fmt},volume={av},afade=t=in:d=0.4,afade=t=out:st={max(0, total - 1.5):.2f}:d=1.5[amb]"
        )
        mix.append("[amb]")
        log(f"  âm thanh không khí: {amb.name}")
    elif script.get("ambience"):
        log(f"  (chưa có âm thanh '{script['ambience']}' - bỏ file vào assets/sfx)")
    if len(mix) > 1:
        parts.append(f"{''.join(mix)}amix=inputs={len(mix)}:duration=first:dropout_transition=0:normalize=0,"
                     f"alimiter=limit=0.95[a]")
    else:
        parts.append("[voice]alimiter=limit=0.95[a]")

    fc = "[0:v]ass=captions.ass:fontsdir=fonts[v];" + ";".join(parts)
    final = out_dir / "video.mp4"
    run([ff, "-y", *inputs, "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-t", f"{total:.3f}", "-movflags", "+faststart",
         final], cwd=work)
    log(f"Video: xong {final} ({total:.1f} giây, {len(clips)} shot)")
    return final
