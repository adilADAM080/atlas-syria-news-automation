import hashlib
import json
import os
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

SOURCE = "https://t.me/s/symoheasr"
BASELINE = 13130
STATE_FILE = "data/state.json"
OUTPUT_DIR = "output"

KEYWORDS = [
    "جامعة", "جامعات", "المعهد", "المعاهد", "التعليم العالي", "البحث العلمي",
    "طالب", "طلاب", "القبول", "المفاضلة", "مفاضلة", "منحة", "منح",
    "كلية", "كليات", "امتحان", "امتحانات", "دراسات عليا", "ماجستير",
    "دكتوراه", "مجلة", "مجلات", "بحث", "باحث", "أكاديمي", "أكاديمية"
]

def load_state():
    if not os.path.exists(STATE_FILE):
        return {"baseline_post_id": BASELINE, "last_seen_post_id": BASELINE,
                "processed_post_ids": [], "processed_hashes": []}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)
    state.setdefault("baseline_post_id", BASELINE)
    state.setdefault("last_seen_post_id", state.get("last_processed_post_id", BASELINE))
    state.setdefault("processed_post_ids", [])
    state.setdefault("processed_hashes", [])
    return state

def normalize(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text

def digest(text):
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()

def relevant(text):
    t = normalize(text)
    return bool(t) and any(k in t for k in KEYWORDS)

def fetch_posts():
    r = requests.get(SOURCE, timeout=30, headers={"User-Agent": "AtlasSyriaNewsMonitor/2.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    posts = []
    for wrap in soup.select(".tgme_widget_message_wrap"):
        node = wrap.select_one("[data-post]")
        if not node:
            continue
        m = re.search(r"/(\d+)$", node.get("data-post", ""))
        if not m:
            continue
        post_id = int(m.group(1))
        text_node = wrap.select_one(".tgme_widget_message_text")
        text = text_node.get_text("\n", strip=True) if text_node else ""
        posts.append({
            "post_id": post_id,
            "text": text,
            "text_hash": digest(text),
            "source_url": f"https://t.me/SyMOHEASR/{post_id}"
        })
    return sorted(posts, key=lambda x: x["post_id"])

def main():
    state = load_state()
    last_seen = max(int(state.get("last_seen_post_id", BASELINE)), BASELINE)
    processed_ids = set(map(int, state.get("processed_post_ids", [])))
    processed_hashes = set(state.get("processed_hashes", []))

    posts = fetch_posts()
    unseen = [p for p in posts if p["post_id"] > last_seen]
    candidates = [
        p for p in unseen
        if relevant(p["text"])
        and p["post_id"] not in processed_ids
        and p["text_hash"] not in processed_hashes
    ]

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    result = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE,
        "baseline_post_id": BASELINE,
        "previous_last_seen_post_id": last_seen,
        "new_post_count": len(unseen),
        "candidate_count": len(candidates),
        "posts": candidates
    }
    with open(f"{OUTPUT_DIR}/new_posts.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    if unseen:
        state["last_seen_post_id"] = max(p["post_id"] for p in unseen)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    print(f"Unseen: {len(unseen)} | relevant candidates: {len(candidates)}")
    for p in candidates:
        print(f"- {p['post_id']}: {p['source_url']}")

if __name__ == "__main__":
    main()
