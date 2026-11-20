from __future__ import annotations

import json

from .util import DATA

STATE_FILE = DATA / "state.json"


def load() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            s = json.load(f)
    else:
        s = {}
    s.setdefault("used_bank", [])
    s.setdefault("used_topics", [])
    s.setdefault("videos", [])
    return s


def save(s: dict) -> None:
    DATA.mkdir(exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)
    tmp.replace(STATE_FILE)
