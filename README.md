# SciML Weekly

A weekly blog on new methods in AI for physics, fluids, and statistical learning, with cited sources and a dated model-release timeline.

Static site, built with one Python script (`markdown` + `pyyaml`, no Node). Output goes to `docs/`, which GitHub Pages serves.

## Layout

```
posts/YYYY-MM-DD-slug.md   one file per issue (front matter: title, date, issue, summary, tags)
posts/_template.md         copy this to start a new issue (files starting with _ are skipped)
posts/img/                 images for posts, referenced as img/name.png
data/releases.yaml         model timeline, rendered as releases.html with domain filters
about.md, site.yaml        About page and site settings
static/                    style.css, favicon (copied as-is)
build.py                   builds everything into docs/
```

## Weekly workflow

```bash
cp posts/_template.md posts/2026-10-07-issue-02.md   # write it; remove `draft: true`
python3 build.py --serve                             # preview at http://localhost:8000
git add -A && git commit -m "Issue #2" && git push   # Pages redeploys automatically
```

Also add any new model releases to `data/releases.yaml`.

Drafts (`draft: true`) are left out of the build. `python3 build.py --drafts --serve` previews them locally. Run a plain `python3 build.py` before committing, so drafts never end up in `docs/`.

A weekly cloud routine drafts the next issue every Monday and opens a PR on a `draft/issue-NN` branch. To publish it: review the PR, remove `draft: true`, run `python3 build.py`, commit, and merge.

### Writing features

- **Citations:** Markdown footnotes (`[^key]` in the text, `[^key]: Authors, "Title," venue, date. <url>` at the bottom). They render as a numbered **Sources** list.
- **Tables:** GitHub-style pipe tables.
- **Math:** `$inline$` and `$$display$$`, rendered with KaTeX (loaded only on posts that use math).
- **Callouts:** `<div class="box" markdown>…</div>`, or `class="box tldr"` for the summary box.
- **Figures:** `<figure><img src="img/x.png" alt="…"><figcaption>…Source: …</figcaption></figure>`. Only use images whose licence allows reuse (many arXiv papers are CC BY), and always credit them. Otherwise, redraw the figure and label it "Figure by the author". Footnotes don't work inside raw HTML such as `<figcaption>`, so use a plain `<a href>` there.

## Deploy (GitHub Pages)

1. Create the repo `meshram1/sciml-weekly` on GitHub and push.
2. Go to Settings → Pages → Source: *Deploy from a branch*, then choose `main` / `/docs`.
3. The site will be live at https://meshram1.github.io/sciml-weekly/
