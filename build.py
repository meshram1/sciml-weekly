"""Build SciML Weekly: posts/*.md + data/releases.yaml -> docs/ (served by GitHub Pages).

Usage:  python3 build.py            # build into docs/
        python3 build.py --serve    # build, then serve on http://localhost:8000
        python3 build.py --drafts   # also render draft: true posts (preview only; don't commit that docs/)
"""
import html
import math
import re
import shutil
import sys
from datetime import date, datetime
from email.utils import format_datetime
from pathlib import Path

import markdown
import yaml

ROOT = Path(__file__).parent
POSTS = ROOT / "posts"
DATA = ROOT / "data"
STATIC = ROOT / "static"
OUT = ROOT / "docs"

SITE = yaml.safe_load((ROOT / "site.yaml").read_text())
BASE = SITE["base_url"].rstrip("/")

MD_EXT = ["tables", "footnotes", "fenced_code", "attr_list", "md_in_html", "toc", "abbr", "def_list"]
MD_CFG = {"footnotes": {"BACKLINK_TEXT": "↩"}, "toc": {"permalink": "#", "permalink_class": "anchor"}}

# ---------------------------------------------------------------- helpers

def esc(s):
    return html.escape(str(s), quote=True)


def fmt_date(d):
    return d.strftime("%b %-d, %Y")


def read_front_matter(text):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        raise ValueError("post is missing a --- front matter block")
    return yaml.safe_load(m.group(1)), m.group(2)


MATH_RE = re.compile(r"(\$\$.+?\$\$|(?<![\\$])\$(?!\s)[^$\n]+?(?<!\s)\$)", re.S)


def render_md(src):
    """Markdown -> HTML, shielding $...$ / $$...$$ from the Markdown parser so KaTeX sees raw TeX."""
    stash = []

    def keep(m):
        stash.append(m.group(0))
        return f"@@MATH{len(stash) - 1}@@"

    # don't touch math inside code fences / inline code
    parts = re.split(r"(```.*?```|`[^`\n]+`)", src, flags=re.S)
    src = "".join(p if p.startswith("`") else MATH_RE.sub(keep, p) for p in parts)
    md = markdown.Markdown(extensions=MD_EXT, extension_configs=MD_CFG)
    out = md.convert(src)
    out = re.sub(r"@@MATH(\d+)@@", lambda m: esc(stash[int(m.group(1))]).replace("&#x27;", "'"), out)
    return out, md.toc_tokens


def reading_time(text):
    words = len(re.findall(r"\w+", re.sub(r"<[^>]+>", " ", text)))
    return max(1, math.ceil(words / 220))


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# ---------------------------------------------------------------- layout

def page(title, body, root="", description="", extra_head=""):
    desc = esc(description or SITE["description"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{desc}">
<link rel="alternate" type="application/rss+xml" title="{esc(SITE['title'])}" href="{root}feed.xml">
<link rel="icon" href="{root}favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{root}style.css?v={SITE_VERSION}">
<script>try{{var t=localStorage.getItem('theme');if(t)document.documentElement.dataset.theme=t}}catch(e){{}}</script>
{extra_head}
</head>
<body>
<div class="wrap">
<header class="top">
  <a class="brand" href="{root}index.html"><span class="brand-mark">∇</span> {esc(SITE['title'])}</a>
  <nav>
    <a href="{root}index.html">Issues</a>
    <a href="{root}releases.html">Model timeline</a>
    <a href="{root}tags.html">Topics</a>
    <a href="{root}about.html">About</a>
    <button class="theme-toggle" type="button" aria-label="Toggle dark mode" onclick="toggleTheme()">◐</button>
  </nav>
</header>
<main>
{body}
</main>
<footer class="foot">
  <p>{esc(SITE['title'])} · written by <a href="{esc(SITE['author_url'])}">{esc(SITE['author'])}</a> ·
  <a href="{root}feed.xml">RSS</a> · Summaries are my own reading of the cited sources; always check the original.</p>
</footer>
</div>
<script>
function toggleTheme(){{
  var r=document.documentElement, dark=r.dataset.theme?r.dataset.theme==='dark':matchMedia('(prefers-color-scheme: dark)').matches;
  r.dataset.theme=dark?'light':'dark'; try{{localStorage.setItem('theme',r.dataset.theme)}}catch(e){{}}
}}
</script>
</body>
</html>
"""


KATEX = """<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"
  onload="renderMathInElement(document.querySelector('.post-body'),{delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false}],throwOnError:false})"></script>"""


def tag_links(tags, root):
    return " ".join(f'<a class="tag" href="{root}tags.html#{slugify(t)}">{esc(t)}</a>' for t in tags)


def toc_html(tokens):
    items = [t for t in tokens if t["level"] == 2]
    if len(items) < 3:
        return ""
    lis = "".join(f'<li><a href="#{t["id"]}">{t["name"]}</a></li>' for t in items)
    return f'<nav class="toc" aria-label="Contents"><p class="toc-title">In this issue</p><ol>{lis}</ol></nav>'


# ---------------------------------------------------------------- build steps

def load_posts():
    posts = []
    for f in sorted(POSTS.glob("*.md")):
        if f.name.startswith("_"):
            continue  # _template.md etc.
        meta, body = read_front_matter(f.read_text())
        if meta.get("draft") and "--drafts" not in sys.argv:
            continue
        d = meta["date"]
        if isinstance(d, str):
            d = date.fromisoformat(d)
        body_html, toc = render_md(body)
        posts.append({
            **meta,
            "date": d,
            "slug": meta.get("slug") or re.sub(r"^\d{4}-\d{2}-\d{2}-", "", f.stem),
            "tags": meta.get("tags", []),
            "html": body_html,
            "toc": toc,
            "minutes": reading_time(body_html),
            "has_math": "$" in body,
        })
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


def build_post(p, prev_p, next_p):
    root = "../"
    issue = f'<span class="issue">Issue #{p["issue"]}</span> · ' if p.get("issue") else ""
    nav = '<nav class="post-nav">'
    nav += f'<a href="{prev_p["slug"]}.html">← {esc(prev_p["title"])}</a>' if prev_p else "<span></span>"
    nav += f'<a href="{next_p["slug"]}.html">{esc(next_p["title"])} →</a>' if next_p else "<span></span>"
    nav += "</nav>"
    body = f"""<article class="post">
<header class="post-head">
  <p class="meta">{issue}<time datetime="{p['date'].isoformat()}">{fmt_date(p['date'])}</time> · {p['minutes']} min read</p>
  <h1>{esc(p['title'])}</h1>
  <p class="dek">{esc(p.get('summary', ''))}</p>
  <p class="tags">{tag_links(p['tags'], root)}</p>
</header>
{toc_html(p['toc'])}
<div class="post-body">
{p['html']}
</div>
</article>
{nav}"""
    head = KATEX if p["has_math"] else ""
    (OUT / "posts" / f"{p['slug']}.html").write_text(
        page(f"{p['title']} · {SITE['title']}", body, root, p.get("summary", ""), head))


def build_index(posts):
    latest, rest = (posts[0], posts[1:]) if posts else (None, [])
    hero = ""
    if latest:
        hero = f"""<section class="latest">
  <p class="kicker">Latest{f" · Issue #{latest['issue']}" if latest.get('issue') else ""} · {fmt_date(latest['date'])}</p>
  <h2><a href="posts/{latest['slug']}.html">{esc(latest['title'])}</a></h2>
  <p>{esc(latest.get('summary', ''))}</p>
  <p class="tags">{tag_links(latest['tags'], '')}</p>
  <a class="read" href="posts/{latest['slug']}.html">Read issue · {latest['minutes']} min →</a>
</section>"""
    items = "".join(
        f'<li><a href="posts/{p["slug"]}.html">{esc(p["title"])}</a>'
        f'<span class="date">{fmt_date(p["date"])}</span></li>' for p in rest)
    archive = f'<h2 class="section">Archive</h2><ul class="posts">{items}</ul>' if rest else ""
    body = f"""<section class="intro">
  <h1 class="tagline">{esc(SITE['tagline'])}</h1>
  <p>{esc(SITE['description'])}</p>
</section>
{hero}
{archive}"""
    (OUT / "index.html").write_text(page(SITE["title"], body))


def build_tags(posts):
    by_tag = {}
    for p in posts:
        for t in p["tags"]:
            by_tag.setdefault(t, []).append(p)
    sections = []
    for t in sorted(by_tag, key=str.lower):
        lis = "".join(f'<li><a href="posts/{p["slug"]}.html">{esc(p["title"])}</a>'
                      f'<span class="date">{fmt_date(p["date"])}</span></li>' for p in by_tag[t])
        sections.append(f'<h2 class="section" id="{slugify(t)}">{esc(t)} <span class="count">{len(by_tag[t])}</span></h2>'
                        f'<ul class="posts">{lis}</ul>')
    body = '<h1 class="page-title">Topics</h1>' + "".join(sections)
    (OUT / "tags.html").write_text(page(f"Topics · {SITE['title']}", body))


def build_releases():
    rel = yaml.safe_load((DATA / "releases.yaml").read_text())
    rows = sorted(rel, key=lambda r: str(r["date"]), reverse=True)
    domains = sorted({r["domain"] for r in rows})
    chips = '<button class="chip on" data-d="all">All</button>' + "".join(
        f'<button class="chip" data-d="{esc(d)}">{esc(d)}</button>' for d in domains)
    trs = []
    for r in rows:
        d = str(r["date"])
        shown = datetime.strptime(d, "%Y-%m-%d").strftime("%b %-d, %Y") if len(d) == 10 else \
            datetime.strptime(d, "%Y-%m").strftime("%b %Y")
        weights = {"open": "Open weights", "api": "API / product", "closed": "Paper only", "code": "Open code", "operational": "Operational"}.get(r.get("access", ""), "")
        trs.append(f"""<tr data-d="{esc(r['domain'])}">
<td class="nowrap"><time datetime="{d}">{shown}</time></td>
<td><strong>{esc(r['name'])}</strong><div class="sub">{esc(r['org'])}</div></td>
<td><span class="dom">{esc(r['domain'])}</span></td>
<td>{esc(r['what'])}</td>
<td class="nowrap">{esc(weights)}</td>
<td><a href="{esc(r['source'])}">{esc(r.get('source_label', 'source'))}</a></td>
</tr>""")
    body = f"""<h1 class="page-title">Model &amp; release timeline</h1>
<p class="lede">Dated releases of notable AI models, datasets, and tools for physics, fluids, and weather. The date is the first public
release (preprint, announcement, or software release), which can be earlier than journal publication. Every row links to its source.</p>
<div class="chips" role="group" aria-label="Filter by domain">{chips}</div>
<div class="table-wrap"><table class="releases">
<thead><tr><th>Date</th><th>Release</th><th>Domain</th><th>What it is</th><th>Access</th><th>Source</th></tr></thead>
<tbody>{''.join(trs)}</tbody></table></div>
<script>
document.querySelectorAll('.chip').forEach(function(b){{b.onclick=function(){{
  document.querySelectorAll('.chip').forEach(function(c){{c.classList.toggle('on',c===b)}});
  document.querySelectorAll('.releases tbody tr').forEach(function(tr){{
    tr.hidden=!(b.dataset.d==='all'||tr.dataset.d===b.dataset.d)}});
}}}});
</script>"""
    (OUT / "releases.html").write_text(page(f"Model timeline · {SITE['title']}", body,
                                            description="Dated timeline of AI models for physics, fluids and weather."))


def build_about():
    src = (ROOT / "about.md").read_text()
    body_html, _ = render_md(src)
    (OUT / "about.html").write_text(page(f"About · {SITE['title']}", f'<article class="post"><div class="post-body">{body_html}</div></article>'))


def build_feed(posts):
    items = []
    for p in posts[:20]:
        link = f"{BASE}/posts/{p['slug']}.html"
        dt = datetime.combine(p["date"], datetime.min.time()).astimezone()
        items.append(f"""<item><title>{esc(p['title'])}</title><link>{link}</link><guid>{link}</guid>
<pubDate>{format_datetime(dt)}</pubDate><description>{esc(p.get('summary', ''))}</description></item>""")
    (OUT / "feed.xml").write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>{esc(SITE['title'])}</title><link>{BASE}/</link>
<description>{esc(SITE['description'])}</description>{''.join(items)}</channel></rss>
""")


def main():
    global SITE_VERSION
    SITE_VERSION = int((STATIC / "style.css").stat().st_mtime)
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "posts").mkdir(parents=True)
    shutil.copytree(STATIC, OUT, dirs_exist_ok=True)
    if (POSTS / "img").exists():
        shutil.copytree(POSTS / "img", OUT / "posts" / "img")
    (OUT / ".nojekyll").write_text("")

    posts = load_posts()
    for i, p in enumerate(posts):
        build_post(p, posts[i + 1] if i + 1 < len(posts) else None, posts[i - 1] if i > 0 else None)
    build_index(posts)
    build_tags(posts)
    build_releases()
    build_about()
    build_feed(posts)
    print(f"built {len(posts)} post(s) -> {OUT}")

    if "--serve" in sys.argv:
        import functools
        import http.server
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(OUT))
        print("serving on http://localhost:8000  (Ctrl+C to stop)")
        http.server.ThreadingHTTPServer(("", 8000), handler).serve_forever()


SITE_VERSION = 0
if __name__ == "__main__":
    main()
