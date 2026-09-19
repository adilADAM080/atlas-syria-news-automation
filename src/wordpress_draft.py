import html
import json
import os
import re
import sys

import requests

INPUT = "output/new_posts.json"
STATE = "data/state.json"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def clean_title(text):
    lines = [re.sub(r"\s+", " ", x).strip(" -–—") for x in (text or "").splitlines() if x.strip()]
    return lines[0][:150] if lines else "خبر جامعي جديد"


def paragraph_html(text):
    blocks = [x.strip() for x in re.split(r"\n{2,}", text or "") if x.strip()]
    return "\n".join(f"<p>{html.escape(b).replace(chr(10), '<br>')}</p>" for b in blocks)


def normalize_excerpt(text):
    return re.sub(r"\s+", " ", text or "").strip()[:155]


def check_wordpress_user(session, site):
    url = f"{site}/wp-json/wp/v2/users/me?context=edit"
    r = session.get(url, timeout=30)
    if r.status_code != 200:
        print(f"WordPress auth check failed: HTTP {r.status_code}", file=sys.stderr)
        print(r.text[:500], file=sys.stderr)
        return False

    profile = r.json()
    capabilities = profile.get("capabilities") or {}
    name = profile.get("name") or profile.get("slug") or profile.get("id")
    role_names = ", ".join(profile.get("roles") or []) or "unknown"
    can_create = bool(capabilities.get("edit_posts"))
    can_publish = bool(capabilities.get("publish_posts"))
    print(
        "WordPress auth ok: "
        f"user={name}, roles={role_names}, "
        f"edit_posts={can_create}, publish_posts={can_publish}"
    )
    if not can_create:
        print(
            "WordPress user cannot create posts. Use an Administrator/Editor account "
            "or grant this user the edit_posts capability, then create a new Application Password.",
            file=sys.stderr,
        )
    return can_create


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

    state.setdefault("version", 2)
    state.setdefault("sources", {})
    session = requests.Session()
    session.trust_env = os.getenv("ATLAS_USE_SYSTEM_PROXY") == "1"
    session.auth = (user, password)
    session.headers.update(
        {
            "Accept": "application/json",
            "User-Agent": "AtlasSyriaNewsMonitor/2.4 (+https://atlas-sy.com)",
        }
    )

    if not check_wordpress_user(session, site):
        print("No WordPress drafts were created.")
        return

    created_any = False
    for post in payload.get("posts", []):
        sid = post["source_id"]
        st = state["sources"].setdefault(
            sid,
            {"last_seen_post_id": 0, "processed_post_ids": [], "processed_hashes": []},
        )
        processed_ids = set(map(int, st.get("processed_post_ids", [])))
        processed_hashes = set(st.get("processed_hashes", []))
        pid = int(post["post_id"])
        phash = post["text_hash"]
        if pid in processed_ids or phash in processed_hashes:
            continue

        source_url = post["source_url"]
        source_name = post.get("source_name", "المصدر الرسمي")
        body = {
            "title": clean_title(post["text"]),
            "content": (
                paragraph_html(post["text"])
                + f'\n<p><strong>المصدر:</strong> <a href="{html.escape(source_url, quote=True)}" rel="noopener">{html.escape(source_name)}</a></p>'
            ),
            "excerpt": normalize_excerpt(post["text"]),
            "status": "draft",
        }
        r = session.post(f"{site}/wp-json/wp/v2/posts", data=body, timeout=30)
        if r.status_code not in (200, 201):
            print(f"Draft failed for {sid} #{pid}: HTTP {r.status_code}", file=sys.stderr)
            print(r.text[:500], file=sys.stderr)
            continue

        created = r.json()
        print(f"Created WordPress draft {created.get('id')} from {sid} #{pid}.")
        processed_ids.add(pid)
        processed_hashes.add(phash)
        st["processed_post_ids"] = sorted(processed_ids)[-500:]
        st["processed_hashes"] = list(processed_hashes)[-500:]
        created_any = True

    if created_any:
        with open(STATE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    else:
        print("No WordPress drafts were created.")


if __name__ == "__main__":
    main()
