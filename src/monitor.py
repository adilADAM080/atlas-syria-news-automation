import json
import os
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

SOURCE = "https://t.me/s/symoheasr"
STATE_FILE = "data/state.json"
OUTPUT_DIR = "output"

def load_state():
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def fetch_posts():
    r = requests.get(SOURCE, timeout=30, headers={"User-Agent": "AtlasSyriaNewsMonitor/1.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    posts = []
    for wrap in soup.select(".tgme_widget_message_wrap"):
        node = wrap.select_one("[data-post]")
        if not node:
            continue
        data_post = node.get("data-post", "")
        m = re.search(r"/(\d+)$", data_post)
        if not m:
            continue
        post_id = int(m.group(1))
        text_node = wrap.select_one(".tgme_widget_message_text")
        text = text_node.get_text("\n", strip=True) if text_node else ""
        posts.append({
            "post_id": post_id,
            "text": text,
            "source_url": f"https://t.me/SyMOHEASR/{post_id}"
        })
    return sorted(posts, key=lambda x: x["post_id"])

def main():
    state = load_state()
    last_id = max(state.get("last_processed_post_id", 13130), 13130)
    processed = set(state.get("processed_post_ids", []))
    posts = fetch_posts()
    new_posts = [p for p in posts if p["post_id"] > last_id and p["post_id"] not in processed]

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    result = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE,
        "baseline_post_id": 13130,
        "last_processed_post_id": last_id,
        "new_post_count": len(new_posts),
        "posts": new_posts
    }
    with open(f"{OUTPUT_DIR}/new_posts.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    if new_posts:
        print(f"Found {len(new_posts)} new post(s) after {last_id}.")
        for p in new_posts:
            print(f"- {p['post_id']}: {p['source_url']}")
    else:
        print(f"No new posts after {last_id}.")

if __name__ == "__main__":
    main()
