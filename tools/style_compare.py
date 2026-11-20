"""So sánh phong cách ảnh: python tools/style_compare.py [style1 style2 ...]
Mỗi cột một phong cách (đã qua tông màu "xua_sang"). Kết quả: output/style_compare.jpg"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PIL import Image  # noqa: E402

from studio import images  # noqa: E402
from studio.util import OUTPUT, load_config  # noqa: E402

PROMPTS = [
    "{BIN} running down a sunny village alley hugging a big aluminum pot, mischievous grin",
    "{BA} gently fanning {BIN} with a bamboo fan on a straw mat in the courtyard, both smiling",
]
styles = sys.argv[1:] or ["hoat_hinh_3d", "anh_xua_sang"]
cfg = load_config()
cols = []
first = True
for st in styles:
    cfg["images"]["style"] = st
    col = []
    for i, p in enumerate(PROMPTS):
        if not first:
            time.sleep(46)
        first = False
        img = images._pollinations(p, 777 + i, cfg)
        col.append(images.finish(img, "xua_sang").resize((405, 720)))
        print("xong", st, i + 1, flush=True)
    cols.append(col)
sheet = Image.new("RGB", (415 * len(cols) - 10, 730 * len(PROMPTS) - 10), "white")
for c, col in enumerate(cols):
    for r, im in enumerate(col):
        sheet.paste(im, (c * 415, r * 730))
out = OUTPUT / "style_compare.jpg"
sheet.save(out, quality=90)
print("Đã lưu", out, "| các cột:", ", ".join(styles))
