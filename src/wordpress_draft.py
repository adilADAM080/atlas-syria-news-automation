import json
import os
import re
import sys

import requests

INPUT = "output/new_posts.json"
STATE = "data/state.json"

def clean_title(text):
    lines = [re.sub(r"\s+", " ", x).strip(" -–—") for x in (text or "").splitlines() if x.strip()]
    if not lines:
        return "خبر جديد من وزارة التعليم العالي والبحث العلمي"
    title = lines[0]
    return title[:150] if len(title) > 150 else title

def paragraph_html(text):
    blocks = [x.strip() for x in re.split(r"\n{2,}", text or "") if x.strip()]
    return "\n".join(f"<p>{b.replace(chr(10), '<br>')}</p>" for b in blocks)

def main():
    site = os.getenv("WP_SITE_URL", "").rstrip("/")
    user = os.getenv("WP_USERNAME", "")
    password = os.getenv("WP_APP_PASSWORD", "")
    if not (site and user and password):
        print("WordPress secrets are not configured; draft creation skipped safely.")
        return

    with open(INPUT, "r", encoding="utf-8") as f:
        payload = json.load(f)
    with open(STATE, "r", encoding="utf-8") as f:
        state = json.load(f)

    processed_ids = set(map(int, state.get("processed_post_ids", [])))
    processed_hashes = set(state.get("processed_hashes", []))
    session = requests.Session()
    session.auth = (user, password)

    for post in payload.get("posts", []):
        pid = int(post["post_id"])
        phash = post["text_hash"]
        if pid in processed_ids or phash in processed_hashes:
            continue

        title = clean_title(post["text"])
        source = post["source_url"]
        content = paragraph_html(post["text"])
        content += f'\n<p><strong>المصدر:</strong> <a href="{source}" rel="noopener">وزارة التعليم العالي والبحث العلمي السورية</a></p>'
        excerpt = re.sub(r"\s+", " ", post["text"]).strip()[:155]

        body = {
            "title": title,
            "content": content,
            "excerpt": excerpt,
            "status": "draft"
        }
        r = session.post(f"{site}/wp-json/wp/v2/posts", json=body, timeout=30)
        if r.status_code not in (200, 201):
            print(f"Failed to create draft for Telegram {pid}: HTTP {r.status_code}", file=sys.stderr)
            continue

        created = r.json()
        print(f"Created WordPress draft {created.get('id')} from Telegram {pid}.")
        processed_ids.add(pid)
        processed_hashes.add(phash)

    state["processed_post_ids"] = sorted(processed_ids)[-500:]
    state["processed_hashes"] = list(processed_hashes)[-500:]
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
