"""Lấy kịch bản: ưu tiên kho viết sẵn (data/scripts), hết thì nhờ AI miễn phí viết."""
from __future__ import annotations

import json
import os
import random

import requests

from .util import DATA, log, slugify

AMBIENCES = ["ve_sau", "mua", "bep_cui", "dem_que", "san_truong", "lang_que", "gio_dong", "pho_cu"]

PROMPT = """Bạn là biên kịch cho series hoạt hình 3D TikTok/Facebook Reels "Hạt gạo quê" - hoài niệm tuổi thơ 8x 9x ở làng quê Việt Nam thập niên 90.
Nhân vật: bé Bin (4-6 tuổi, mũm mĩm, nghịch ngợm, đáng yêu), ông nội, bà nội; nhân vật phụ quen thuộc: chó Vàng
(chú chó ta trung thành của nhà Bin), Tèo (bạn thân hàng xóm, gầy, láu lỉnh), cô giáo Hoa; đôi khi có bố, mẹ, bạn trong xóm.
Đây là phim hoạt hình kể CHUYỆN: người dẫn truyện kể ở ngôi thứ ba ("Bin...", "ông", "bà"), giọng ấm, dí dỏm.
Ông và bà có LỜI THOẠI riêng (được đọc bằng giọng khác). Mỗi tập là MỘT câu chuyện nhỏ có tình huống, đan chi tiết
đời sống 8x 9x (đồ vật, trò chơi, món quà vặt, phong tục) và luôn kết bằng khoảnh khắc ấm áp giữa Bin và ông/bà.

Viết kịch bản video 25-30 giây về chủ đề: "<<TOPIC>>".

CÔNG THỨC BẮT BUỘC (theo các kênh hoạt hình ông bà - cháu triệu view):
1. "hook": chữ to 3 giây đầu, tối đa 9 chữ, NÓI RÕ TÌNH HUỐNG gây tò mò (tắt tiếng vẫn hiểu), có thể viết HOA 1-2 chữ.
   Ví dụ: "Bin mang NỒI CƠM của bà đi đổi kẹo?!", "Đèn ông sao của Bin... BỐC CHÁY!"
   "hook_b": câu móc THỨ HAI cho cùng tập, khác kiểu hẳn để thử xem kiểu nào hút hơn (vd hook là câu hỏi
   thì hook_b là câu cảm thán / "chỉ 9x mới hiểu..." / con số), cũng tối đa 9 chữ.
2. "scenes": đúng 6 cảnh, mỗi cảnh 1 câu ngắn (5-18 chữ), tổng 55-80 chữ. Cấu trúc truyện:
   - Cảnh 1: Bin muốn làm một việc / một điều bắt đầu (vào thẳng tình huống, không chào hỏi).
   - Cảnh 2-3: Bin làm, rồi gặp rắc rối nhỏ hoặc chuyện buồn cười (nghịch dại, hỏng việc, thèm mà không có tiền...).
   - Cảnh 4: ông hoặc bà xuất hiện - thường là LỜI THOẠI của ông/bà.
   - Cảnh 5: cái kết ấm áp, bất ngờ nhẹ hoặc hài hước (ông bà thương cháu, nhường cháu, dỗ cháu).
   - Cảnh 6: câu hỏi cụ thể cho người xem kể kỷ niệm của họ.
   Cảnh là lời thoại thì thêm "speaker": "ba" hoặc "ong" (1-2 cảnh thoại mỗi tập). Lời thoại tự nhiên, kiểu ông bà miền Bắc.
   Chọn 3 cảnh có hành động rõ nhất, thêm "motion": mô tả cử động bằng tiếng Anh (vd "Bin jumps up and down cheering, grandpa laughs").
3. Mỗi cảnh có "images": 1-2 mô tả ảnh bằng TIẾNG ANH, mỗi mô tả là một khung hình cụ thể minh họa đúng câu thoại,
   bối cảnh làng quê Việt Nam thập niên 1990. BẮT BUỘC gọi nhân vật bằng mã: {BIN} (bé Bin), {ONG} (ông), {BA} (bà),
   {VANG} (chó Vàng), {TEO} (bạn Tèo), {CO} (cô giáo Hoa), {ME} (mẹ), {BO} (bố), {BANBE} (bạn trong xóm).
   Ví dụ: "{BA} gently fanning a sleepy {BIN} with a bamboo fan". Chó Vàng nên xuất hiện thỉnh thoảng cho vui.
   TUYỆT ĐỐI KHÔNG tả ngoại hình, tóc, quần áo của nhân vật có mã (đã có ảnh mẫu cố định) - chỉ tả hành động,
   biểu cảm, đồ vật và bối cảnh. Mỗi ảnh tối đa 2 nhân vật có mã. Nhân vật biểu cảm rõ, vui tươi, đáng yêu, hài hước; quần áo đầy đủ. Ánh sáng ấm áp, tươi sáng. Tình huống buồn thì vẽ theo
   kiểu hài hước, đáng yêu. TUYỆT ĐỐI KHÔNG cảnh u tối, đáng sợ, vắng vẻ, người đứng quay lưng trong bóng tối. Không có chữ.
4. "ambience": chọn 1 âm thanh nền hợp nhất trong: ve_sau, mua, bep_cui, dem_que, san_truong, lang_que, gio_dong, pho_cu.

Quy tắc: tiếng Việt chuẩn có dấu; không bịa số liệu, tên người thật, sự kiện lịch sử; không emoji trong lời thoại.
"title" dưới 60 ký tự. "caption" 1-2 câu đăng kèm, được dùng 1-2 emoji, kết thúc bằng câu hỏi. "hashtags" 5-7 cái.

Chỉ trả về đúng một JSON:
{"title": "...", "hook": "...", "hook_b": "...", "ambience": "...", "scenes": [{"text": "...", "images": ["..."], "motion": "..."}, {"speaker": "ba", "text": "...", "images": ["..."]}], "caption": "...", "hashtags": ["#hatgaoque", "#8x9x", "#tuoitho", "#ongba"]}
"""


TWO_PART = """
YÊU CẦU ĐẶC BIỆT - TRUYỆN 2 PHẦN: viết câu chuyện này thành 2 tập nối tiếp, mỗi tập đúng cấu trúc ở trên, NGOẠI TRỪ:
- Phần 1: cảnh 6 KHÔNG hỏi người xem mà kết LỬNG bằng một câu hồi hộp (chuyện gì sẽ xảy ra?) + "Xem phần 2 nhé!".
  Hook phần 1 gây tò mò mạnh.
- Phần 2: hook bắt đầu bằng "Phần 2:"; cảnh 1 tóm tắt phần 1 trong một câu rồi đi tiếp; cảnh 6 là câu hỏi người xem.
Chỉ trả về JSON: {"parts": [ {...phần 1...}, {...phần 2...} ]} (mỗi phần đủ các trường như mẫu).
"""

MEMORY = """
YÊU CẦU ĐẶC BIỆT - TẬP TỪ KỶ NIỆM KHÁN GIẢ: dựa trên kỷ niệm có thật do khán giả <<NAME>> kể:
"<<MEMORY>>"
Giữ đúng tinh thần, chi tiết đặc trưng và cảm xúc của kỷ niệm đó, chuyển thành câu chuyện của Bin và ông bà.
Không dùng tên thật của người kể trong lời thoại. "caption" phải bắt đầu bằng "Theo lời kể của bạn <<NAME>> 💛".
"""


def _prompt(topic: str, mode: str = "single", memory: str | None = None, name: str | None = None) -> str:
    """Prompt viết kịch bản + các tập thắng của kênh (vòng học: tập nào nhiều view thì học theo)."""
    from . import growth

    try:
        extra = growth.winners_prompt()
    except Exception:
        extra = ""
    p = PROMPT.replace("<<TOPIC>>", topic) + extra
    if memory:
        p += MEMORY.replace("<<NAME>>", name or "giấu tên").replace("<<MEMORY>>", memory.strip()[:1200])
    if mode == "two_part":
        p += TWO_PART
    return p


# ---------- kho kịch bản viết sẵn ----------

def _bank() -> list[dict]:
    items: list[dict] = []
    for p in sorted((DATA / "scripts").glob("*.json")):
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        items.extend(d if isinstance(d, list) else [d])
    return items


def _topics() -> list[str]:
    path = DATA / "topics.txt"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


# ---------- AI miễn phí ----------

def _gemini(prompt: str, cfg: dict) -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("chưa có GEMINI_API_KEY trong .env")
    model = cfg["script"].get("gemini_model", "gemini-flash-latest")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.9},
    }
    r = requests.post(url, json=body, headers={"x-goog-api-key": key}, timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(f"Gemini lỗi {r.status_code}: {r.text[:400]}")
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _pollinations(prompt: str, cfg: dict) -> str:
    """Viết kịch bản bằng model chữ của Pollinations (dùng chung key, rất rẻ ~ vài chục đồng/kịch bản)."""
    from . import polli

    if not polli.key():
        raise RuntimeError("chưa có POLLINATIONS_TOKEN")
    body = {
        "model": cfg["script"].get("pollinations_model", "openai/gpt-5.4-mini"),
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }
    r = requests.post(f"{polli.GEN}/v1/chat/completions", json=body, headers=polli._auth(), timeout=240)
    if r.status_code >= 400:
        raise RuntimeError(f"Pollinations lỗi {r.status_code}: {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"]


def write_for_topic(topic: str, cfg: dict, mode: str = "single", memory: str | None = None,
                    name: str | None = None, source: str | None = None) -> list[dict]:
    """Nhờ AI viết kịch bản và LƯU vào data/scripts để xem/sửa trước khi dựng.
    mode="two_part": truyện 2 phần (phần 1 kết lửng). memory: kỷ niệm khán giả kể -> viết thành tập."""
    prompt = _prompt(topic, mode, memory, name)
    errors = []
    for provider in [p for p in cfg["script"].get("order", []) if p != "bank"]:
        fn = {"pollinations": _pollinations, "gemini": _gemini, "ollama": _ollama}.get(provider)
        if not fn:
            continue
        try:
            raw = _parse(fn(prompt, cfg))
            parts = raw.get("parts") if mode == "two_part" else None
            if mode == "two_part" and (not isinstance(parts, list) or len(parts) < 2):
                raise ValueError("AI không trả đủ 2 phần")
            items = [validate(p, topic) for p in (parts[:2] if parts else [raw])]
            base = _unique_id(slugify(topic))
            for k, d in enumerate(items):
                d["topic"] = topic
                d["id"] = f"{base}-p{k + 1}" if len(items) > 1 else base
                if memory:
                    d["credit"] = name or "giấu tên"
                    if source:
                        d["source_comment"] = source
            if len(items) == 2:
                p1, p2 = items
                p1.update(part=1, parts_total=2, next=p2["id"],
                          outro_text="Theo dõi HẠT GẠO QUÊ\\Nđể xem PHẦN 2 nhé!",
                          outro_voice="Theo dõi Hạt Gạo Quê để xem phần 2 nha!")
                p2.update(part=2, parts_total=2, after=p1["id"])
            for d in items:
                save_script(d)
            log(f"AI ({provider}) đã viết: " + " | ".join(d["title"] for d in items))
            return items
        except Exception as e:
            errors.append(f"{provider}: {e}")
    raise RuntimeError("Không viết được kịch bản:\n  " + "\n  ".join(errors))


def _unique_id(base: str) -> str:
    sid, n = base, 2
    while (DATA / "scripts" / f"{sid}.json").exists():
        sid, n = f"{base}-{n}", n + 1
    return sid


def save_script(d: dict) -> None:
    folder = DATA / "scripts"
    folder.mkdir(parents=True, exist_ok=True)
    clean = {k: v for k, v in d.items() if not k.startswith("_")}
    (folder / f"{d['id']}.json").write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")


def _ollama(prompt: str, cfg: dict) -> str:
    base = cfg["script"].get("ollama_url", "http://localhost:11434").rstrip("/")
    body = {
        "model": cfg["script"].get("ollama_model", "qwen2.5:7b"),
        "messages": [{"role": "user", "content": prompt}],
        "format": "json",
        "stream": False,
        "options": {"temperature": 0.8},
    }
    try:
        r = requests.post(f"{base}/api/chat", json=body, timeout=900)
    except requests.ConnectionError as e:
        raise RuntimeError("Ollama chưa chạy (chưa cài hoặc chưa mở)") from e
    if r.status_code >= 400:
        raise RuntimeError(f"Ollama lỗi {r.status_code}: {r.text[:400]}")
    return r.json()["message"]["content"]


def _parse(raw: str) -> dict:
    raw = raw.strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("AI không trả về JSON")
    return json.loads(raw[start : end + 1])


def validate(d: dict, topic: str | None = None) -> dict:
    scenes = d.get("scenes") or []
    scenes = [s for s in scenes if str(s.get("text", "")).strip()]
    if not (3 <= len(scenes) <= 14):
        raise ValueError(f"số cảnh không hợp lệ: {len(scenes)}")
    for s in scenes:
        s["text"] = str(s["text"]).strip()
        imgs = s.get("images") or [s.get("image_prompt") or d.get("title") or topic or ""]
        if isinstance(imgs, str):
            imgs = [imgs]
        s["images"] = [str(x).strip() for x in imgs if str(x).strip()][:3]
        s.pop("image_prompt", None)
        if s.get("speaker") not in ("ba", "ong", "me", "bo"):
            s.pop("speaker", None)
    d["scenes"] = scenes
    d["title"] = str(d.get("title") or topic or "Ký ức 8x 9x").strip()
    d["hook"] = str(d.get("hook") or d["title"]).strip()
    if d.get("ambience") not in AMBIENCES:
        d["ambience"] = None
    d["topic"] = d.get("topic") or topic or d["title"]
    d["id"] = d.get("id") or slugify(d["topic"])
    d["caption"] = str(d.get("caption") or "").strip()
    tags = d.get("hashtags") or []
    tags = [t if str(t).startswith("#") else "#" + str(t) for t in tags]
    for must in ("#8x9x", "#tuoitho", "#hoainiem"):
        if must not in tags:
            tags.append(must)
    d["hashtags"] = tags
    return d


def next_script(cfg: dict, state: dict) -> dict:
    order = cfg["script"].get("order", ["bank", "gemini", "ollama"])

    from . import growth

    season_ids, season_topics = growth.seasonal_preferences()
    if "bank" in order:
        bank = _bank()
        used_b = set(state["used_bank"])

        def prio(b: dict) -> int:
            if b.get("after") and b["after"] in used_b:
                return 0  # phần 2 của truyện đã đăng phần 1 -> đăng ngay tập kế
            if b.get("part") == 2:
                return 9  # phần 2 không bao giờ đăng trước phần 1
            if b.get("id") in season_ids:
                return 1  # đúng mùa / sắp tới ngày lễ
            if b.get("credit"):
                return 2  # tập từ kỷ niệm khán giả
            return 3

        # Đúng mùa (Tết, Trung thu, khai giảng...) thì ưu tiên tập hợp mùa - dễ lên xu hướng nhất
        bank.sort(key=prio)
        bank = [b for b in bank if not (b.get("part") == 2 and b.get("after") not in used_b)]
        for item in bank:
            sid = item.get("id") or slugify(item.get("topic", item.get("title", "")))
            if sid not in state["used_bank"]:
                d = validate(dict(item))
                d["_source"] = "bank"
                log(f"Kịch bản: lấy từ kho -> {d['title']}" + (" (đúng mùa)" if sid in season_ids else ""))
                return d

    used = set(state["used_topics"])
    remaining = [t for t in _topics() if t not in used]
    seasonal = [t for t in season_topics if t not in used]
    if seasonal:
        topic = random.choice(seasonal)
        log(f"Kịch bản: chủ đề theo mùa -> {topic}")
    elif remaining:
        topic = random.choice(remaining)
    else:
        raise RuntimeError("Đã dùng hết chủ đề trong data/topics.txt và kho kịch bản. Hãy thêm chủ đề mới.")

    errors = []
    for provider in order:
        if provider == "bank":
            continue
        fn = {"pollinations": _pollinations, "gemini": _gemini, "ollama": _ollama}.get(provider)
        if not fn:
            continue
        for attempt in range(2):
            try:
                log(f"Kịch bản: nhờ {provider} viết chủ đề '{topic}' (lần {attempt + 1})")
                d = validate(_parse(fn(_prompt(topic), cfg)), topic)
                d["topic"] = topic
                d["id"] = slugify(topic)
                d["_source"] = provider
                return d
            except Exception as e:  # thử tiếp nhà cung cấp khác
                errors.append(f"{provider}: {e}")
                log(f"  -> lỗi: {e}")
                if "chưa" in str(e):
                    break
    raise RuntimeError("Không lấy được kịch bản:\n  " + "\n  ".join(errors))
