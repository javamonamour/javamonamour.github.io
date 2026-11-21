#!/usr/bin/env python3
"""Scarica dal feed pubblico di Blogger tutti i post, le pagine e i commenti
di www.javamonamour.org in _export/{posts,pages,comments}.json."""
import json, sys, time, urllib.request
from pathlib import Path

BASE = "https://www.javamonamour.org/feeds"
OUT = Path(__file__).resolve().parent.parent / "_export"


def fetch_all(kind):
    entries, start = [], 1
    while True:
        url = f"{BASE}/{kind}/default?alt=json&max-results=150&start-index={start}"
        for attempt in range(5):
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    feed = json.load(r)["feed"]
                break
            except Exception as e:  # noqa
                print(f"  retry {attempt}: {e}", file=sys.stderr)
                time.sleep(3 * (attempt + 1))
        else:
            sys.exit(f"impossibile scaricare {url}")
        batch = feed.get("entry", [])
        entries += batch
        total = int(feed["openSearch$totalResults"]["$t"])
        print(f"{kind}: {len(entries)}/{total}", file=sys.stderr)
        if not batch or len(entries) >= total:
            return entries
        start += len(batch)


OUT.mkdir(exist_ok=True)
for kind in ("posts", "pages", "comments"):
    data = fetch_all(kind)
    (OUT / f"{kind}.json").write_text(json.dumps(data, ensure_ascii=False))
