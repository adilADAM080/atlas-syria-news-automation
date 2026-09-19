import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

SOURCES_FILE = "data/sources.json"
STATE_FILE = "data/state.json"
OUTPUT_DIR = "output"
DEFAULT_BASELINE = 13130

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

KEYWORDS = [
    "جامعة", "جامعات", "المعهد", "المعاهد", "التعليم العالي", "البحث العلمي",
    "طالب", "طلاب", "القبول", "المفاضلة", "مفاضلة", "منحة", "منح", "بعثة",
    "كلية", "كليات", "امتحان", "امتحانات", "نتائج", "دراسات عليا", "ماجستير",
    "دكتوراه", "مجلة", "مجلات", "بحث", "باحث", "أكاديمي", "أكاديمية",
    "تسجيل", "مقررات", "ترفع", "خريج", "خريجين", "اتفاقية", "مؤتمر",
]


def normalize(text):
    return re.sub(r"\s+", " ", text or "").strip()


def digest(text):
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def relevant(text):
    t = normalize(text)
    return bool(t) and any(k in t for k in KEYWORDS)


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_sources():
    data = load_json(SOURCES_FILE, {"sources": []})
    return [s for s in data.get("sources", []) if s.get("enabled", True)]


def load_state():
    old = load_json(STATE_FILE, {})
    if "sources" not in old:
        last = int(old.get("last_seen_post_id", old.get("last_processed_post_id", DEFAULT_BASELINE)))
        old = {
            "version": 2,
            "sources": {
                "symoheasr_telegram": {
                    "last_seen_post_id": max(last, DEFAULT_BASELINE),
                    "processed_post_ids": old.get("processed_post_ids", []),
                    "processed_hashes": old.get("processed_hashes", []),
                }
            },
        }
    old.setdefault("version", 2)
    old.setdefault("sources", {})
    return old


def source_state(state, source):
    sid = source["id"]
    baseline = int(source.get("baseline_post_id", 0))
    st = state["sources"].setdefault(sid, {})
    st.setdefault("last_seen_post_id", baseline)
    st.setdefault("processed_post_ids", [])
    st.setdefault("processed_hashes", [])
    return st


def fetch_telegram(source):
    session = requests.Session()
    session.trust_env = os.getenv("ATLAS_USE_SYSTEM_PROXY") == "1"
    r = session.get(
        source["url"],
        timeout=30,
        headers={"User-Agent": "AtlasSyriaNewsMonitor/2.2 (+https://atlas-sy.com)"},
    )
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    channel = source.get("channel") or source["url"].rstrip("/").split("/")[-1]
    posts = []
    for wrap in soup.select(".tgme_widget_message_wrap"):
        node = wrap.select_one("[data-post]")
        if not node:
            continue
        raw = node.get("data-post", "")
        m = re.search(r"/(\d+)$", raw)
        if not m:
            continue
        pid = int(m.group(1))
        text_node = wrap.select_one(".tgme_widget_message_text")
        text = text_node.get_text("\n", strip=True) if text_node else ""
        posts.append(
            {
                "source_id": source["id"],
                "source_name": source["name"],
                "source_type": "telegram",
                "post_id": pid,
                "text": text,
                "text_hash": digest(text),
                "source_url": f"https://t.me/{channel}/{pid}",
            }
        )
    return sorted(posts, key=lambda p: p["post_id"])


def fetch_source(source):
    if source.get("type") == "telegram":
        return fetch_telegram(source), None
    if source.get("type") == "facebook":
        return [], "facebook_direct_monitor_unavailable"
    return [], "unsupported_source_type"


def main():
    sources = load_sources()
    state = load_state()
    all_candidates = []
    reports = []

    for source in sources:
        st = source_state(state, source)
        try:
            posts, warning = fetch_source(source)
        except Exception as exc:
            reports.append(
                {
                    "source_id": source["id"],
                    "source_name": source["name"],
                    "status": "error",
                    "detail": str(exc)[:300],
                }
            )
            continue

        if warning:
            reports.append(
                {
                    "source_id": source["id"],
                    "source_name": source["name"],
                    "status": "skipped",
                    "detail": warning,
                }
            )
            continue

        baseline = int(source.get("baseline_post_id", 0))
        ids = set(map(int, st.get("processed_post_ids", [])))
        hashes = set(st.get("processed_hashes", []))
        eligible = [p for p in posts if p["post_id"] > baseline]
        candidates = [
            p
            for p in eligible
            if relevant(p["text"]) and p["post_id"] not in ids and p["text_hash"] not in hashes
        ]

        if eligible:
            st["last_seen_post_id"] = max(
                int(st.get("last_seen_post_id", baseline)),
                max(p["post_id"] for p in eligible),
            )

        all_candidates.extend(candidates)
        reports.append(
            {
                "source_id": source["id"],
                "source_name": source["name"],
                "status": "ok",
                "available_post_count": len(eligible),
                "candidate_count": len(candidates),
                "last_seen_post_id": st["last_seen_post_id"],
            }
        )

    result = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "monitor_version": "2.2",
        "source_count": len(sources),
        "candidate_count": len(all_candidates),
        "sources": reports,
        "posts": all_candidates,
    }
    save_json(f"{OUTPUT_DIR}/new_posts.json", result)
    save_json(STATE_FILE, state)
    print(f"Checked {len(sources)} sources | candidates: {len(all_candidates)}")
    for r in reports:
        print(f"- {r['source_name']}: {r['status']}")
    for p in all_candidates:
        print(f"  candidate {p['source_name']} #{p['post_id']}: {p['source_url']}")


if __name__ == "__main__":
    main()
