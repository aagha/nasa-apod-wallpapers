#!/usr/bin/env python3
"""Build a Projectivy/Overflight wallpaper list from NASA APOD.

Reads the keyless science.nasa.gov feed (no api.nasa.gov key needed) and writes a
JSON array in Overflight's media format.

Usage:
    python3 apod_wallpapers.py --out apod.json
    python3 apod_wallpapers.py --width 3840 --count 100 --newest 7

Notes that shaped this file (see ../docs/PLAN-overflight-wallpapers.md):
- Projectivy keeps only the first 100 entries, shuffles once, then iterates.
- hdurl is reliable for the recent posts this script fetches (verified 2026-11-23:
  0 empty and 0 placeholder across the last 200 days). basic_html is only a
  fallback for the rare empty hdurl the feed docs warn about.
"""

import argparse
import html
import json
import os
import random
import re
import urllib.request
from datetime import date

BASE = "https://science.nasa.gov/wp-json/wp/v2/apod-basic"
PER_PAGE = 25
LOCATION = "APOD"
MEDIA_HOST = "https://assets.science.nasa.gov/dynamicimage/assets/"
SKIP_MARKS = ("news-thumbnail", "nasa-logo")

# Fallback only: matches any NASA asset image when hdurl is empty. May also match a
# small thumbnail on the rare post, which is preferable to dropping the day.
IMAGE_RE = re.compile(
    r"https://assets\.science\.nasa\.gov/[^\"'\s\\)]+?\.(?:jpe?g|png|gif|webp|tiff?)",
    re.IGNORECASE,
)


def _clean_asset(url):
    """Strip a query string and reject known placeholder files."""
    if not url or not url.startswith("https://assets.science.nasa.gov/"):
        return ""
    if any(mark in url for mark in SKIP_MARKS):
        return ""
    return url.split("?")[0]


def pick_image(post):
    """Return a full-size image URL for an image post, or None."""
    if post.get("media_type") != "image":
        return None
    url = _clean_asset(post.get("hdurl"))
    if url:
        return url
    m = IMAGE_RE.search(post.get("basic_html") or "")
    return _clean_asset(m.group(0)) if m else None


def resize_image(url, width):
    """Rebuild a NASA asset URL at the dynamicimage host with a width cap.

    Two host paths exist: /content/dam/<path> and /dynamicimage/assets/<path>.
    The resizer accepts any path, not only our own APOD folder.
    """
    if "/content/dam/" in url:
        path = url.split("/content/dam/", 1)[1].split("?", 1)[0]
        return f"{MEDIA_HOST}{path}?w={width}"
    if "/dynamicimage/assets/" in url:
        path = url.split("/dynamicimage/assets/", 1)[1].split("?", 1)[0]
        return f"{MEDIA_HOST}{path}?w={width}"
    return url


def clean_text(value):
    """Strip the markup the APOD credit fields carry, e.g. <a href=...>Name</a>."""
    text = re.sub(r"<br\s*/?>", " ", value or "", flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip(" ,;")


def build_entries(posts, width=1920, count=100, newest_count=7, seed=None):
    """Newest `newest_count` image days, then `seed`-shuffled archive up to `count`."""
    seen = set()
    images = []
    for p in sorted(posts, key=lambda x: x.get("date", ""), reverse=True):
        d = p.get("date")
        if not d or d in seen:
            continue
        url = pick_image(p)
        if not url:
            continue
        seen.add(d)
        images.append(
            {
                "location": LOCATION,
                "title": p.get("title") or d,
                "author": clean_text(p.get("copyright") or p.get("credit") or ""),
                "url_img": resize_image(url, width),
            }
        )

    newest, archive = images[:newest_count], images[newest_count:]
    if seed is not None:
        random.Random(str(seed)).shuffle(archive)
    return (newest + archive)[:count]


def fetch_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "apod-wallpapers/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_posts(pages=8, per_page=PER_PAGE, base=BASE):
    """Newest-first APOD posts, a few pages deep."""
    out = []
    for page in range(1, pages + 1):
        url = f"{base}?per_page={per_page}&page={page}"
        try:
            batch = fetch_json(url)
        except urllib.error.HTTPError as e:
            if e.code == 400:  # past the last page
                break
            raise
        if not batch:
            break
        out.extend(batch)
    return out


def write_json(path, entries):
    # Atomic: never leave a half-written file for the TV to fetch mid-write.
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="apod.json")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--count", type=int, default=100)
    ap.add_argument("--newest", type=int, default=7)
    ap.add_argument("--seed", default=date.today().isoformat())
    ap.add_argument("--pages", type=int, default=8)
    args = ap.parse_args()
    # shortcut: count above ~180 image days needs more pages; raise --pages with --count.

    posts = fetch_posts(pages=args.pages)
    entries = build_entries(
        posts, width=args.width, count=args.count, newest_count=args.newest, seed=args.seed
    )
    if not entries:
        raise SystemExit("no image entries built; feed format may have changed")
    write_json(args.out, entries)
    print(f"{len(entries)} entries -> {args.out} (seed {args.seed}, width {args.width})")


if __name__ == "__main__":
    main()
