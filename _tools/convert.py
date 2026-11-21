#!/usr/bin/env python3
"""Converte _export/*.json (feed Blogger) in un sito Jekyll:
  _posts/AAAA-MM-GG-slug.html  con permalink identico all'URL Blogger
  search/label/<slug>.html     una pagina per etichetta
  images/                      immagini ospitate da Google, scaricate in locale
Uso: python3 _tools/convert.py [--no-images]"""
import concurrent.futures as cf
import hashlib, html, json, re, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXP = ROOT / "_export"
POSTS = ROOT / "_posts"
LABELS = ROOT / "search" / "label"
IMAGES = ROOT / "images"
GOOGLE_IMG = re.compile(
    r'https?://(?:blogger\.googleusercontent\.com|\d\.bp\.blogspot\.com|lh\d\.googleusercontent\.com)/[^"\'\s<>)]+')
SITE_HOSTS = re.compile(r'https?://(?:www\.)?javamonamour\.(?:org|blogspot\.com)(?=/\d{4}/\d{2}/)')


def yaml_str(s):
    return json.dumps(s, ensure_ascii=False)  # JSON string = YAML valido


def label_slug(term):
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", term.strip()).strip("-.")
    return s or hashlib.md5(term.encode()).hexdigest()[:8]


def alt_link(e):
    return next(l["href"] for l in e["link"] if l["rel"] == "alternate")


def post_id(e):
    return e["id"]["$t"].rsplit("post-", 1)[1]


# ---------- immagini ----------
def image_name(url):
    path = urllib.parse.urlparse(url).path
    ext = Path(path).suffix.lower()
    if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"):
        ext = ""
    return hashlib.sha1(url.encode()).hexdigest()[:16] + ext


def download(url):
    dest = IMAGES / image_name(url)
    if dest.exists() and dest.stat().st_size:
        return url, dest.name
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
            ctype = r.headers.get("Content-Type", "")
        if not dest.suffix:
            ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
                   "image/webp": ".webp"}.get(ctype.split(";")[0], "")
            if not ext:
                return url, None
            dest = dest.with_suffix(ext)
            if dest.exists():
                return url, dest.name
        dest.write_bytes(data)
        return url, dest.name
    except Exception as ex:  # noqa
        print(f"  immagine non scaricata: {url} ({ex})", file=sys.stderr)
        return url, None


def main():
    posts = json.loads((EXP / "posts.json").read_text())
    comments = json.loads((EXP / "comments.json").read_text())

    # commenti raggruppati per post
    by_post = {}
    for c in comments:
        m = re.search(r"post-(\d+)", c["id"]["$t"])
        ref = c.get("thr$in-reply-to", {}).get("ref", "")
        pid = re.search(r"post-(\d+)", ref)
        if not pid:
            continue
        by_post.setdefault(pid.group(1), []).append({
            "author": c["author"][0]["name"]["$t"],
            "date": c["published"]["$t"][:10],
            "html": c["content"]["$t"],
        })

    # immagini
    urlmap = {}
    if "--no-images" not in sys.argv:
        IMAGES.mkdir(exist_ok=True)
        urls = sorted({u for e in posts for u in GOOGLE_IMG.findall(e["content"]["$t"])})
        print(f"immagini da scaricare: {len(urls)}", file=sys.stderr)
        with cf.ThreadPoolExecutor(16) as ex:
            for url, name in ex.map(download, urls):
                if name:
                    urlmap[url] = "/images/" + name

    POSTS.mkdir(exist_ok=True)
    for f in POSTS.glob("*.html"):
        f.unlink()
    labels = {}
    seen = set()
    for e in posts:
        link = alt_link(e)
        permalink = urllib.parse.urlparse(link).path
        slug = Path(permalink).stem
        date = e["published"]["$t"]
        fname = f"{date[:10]}-{slug}.html"
        while fname in seen:
            fname = fname.replace(".html", "-1.html")
        seen.add(fname)
        title = e["title"]["$t"] or "(senza titolo)"
        terms = [t["term"] for t in e.get("category", [])]
        for t in terms:
            labels.setdefault(t, 0)
            labels[t] += 1

        body = e["content"]["$t"]
        body = GOOGLE_IMG.sub(lambda m: urlmap.get(m.group(0), m.group(0)), body)
        body = SITE_HOSTS.sub("", body)  # link interni → relativi
        if "{{" in body or "{%" in body:
            body = "{% raw %}" + body.replace("{% endraw %}", "{ % endraw % }") + "{% endraw %}"

        fm = [
            "---",
            "layout: post",
            f"title: {yaml_str(title)}",
            f"date: {date}",
            f"permalink: {permalink}",
            f"blogger_id: \"{post_id(e)}\"",
        ]
        if terms:
            fm.append("tags: [" + ", ".join(yaml_str(t) for t in terms) + "]")
        cms = by_post.get(post_id(e))
        if cms:
            cms.sort(key=lambda c: c["date"])
            fm.append("blogger_comments:")
            for c in cms:
                fm += [f"  - author: {yaml_str(c['author'])}",
                       f"    date: {c['date']}",
                       f"    html: {yaml_str(c['html'])}"]
        fm.append("---")
        (POSTS / fname).write_text("\n".join(fm) + "\n" + body + "\n")

    # pagine etichette
    if LABELS.exists():
        for f in LABELS.glob("*.html"):
            f.unlink()
    LABELS.mkdir(parents=True, exist_ok=True)
    slugs = {}
    for t in sorted(labels, key=str.lower):
        s = label_slug(t)
        while s.lower() in {x.lower() for x in slugs.values()}:
            s += "-"
        slugs[t] = s
        (LABELS / f"{s}.html").write_text(
            f"---\nlayout: label\nlabel: {yaml_str(t)}\ntitle: {yaml_str('Label: ' + t)}\n"
            f"permalink: /search/label/{s}\n---\n")
    data = ROOT / "_data"
    data.mkdir(exist_ok=True)
    (data / "labels.json").write_text(json.dumps(
        [{"name": t, "slug": slugs[t], "count": labels[t]} for t in sorted(labels, key=str.lower)],
        ensure_ascii=False, indent=0))

    # pagina statica "Dedicated"
    pages = json.loads((EXP / "pages.json").read_text())
    for p in pages:
        perm = urllib.parse.urlparse(alt_link(p)).path
        out = ROOT / "p" / Path(perm).name
        out.parent.mkdir(exist_ok=True)
        out.write_text(f"---\nlayout: page\ntitle: {yaml_str(p['title']['$t'])}\npermalink: {perm}\n---\n"
                       + GOOGLE_IMG.sub(lambda m: urlmap.get(m.group(0), m.group(0)), p["content"]["$t"]) + "\n")

    print(f"post: {len(posts)}, etichette: {len(labels)}, immagini: {len(urlmap)}, "
          f"post con commenti: {len(by_post)}", file=sys.stderr)


if __name__ == "__main__":
    main()
