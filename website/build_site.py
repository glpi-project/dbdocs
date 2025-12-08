#!/usr/bin/env python3
"""Build a small static site from template and links.json.

Writes output to `website/dist/` ready for publishing (e.g. via gh-pages).
"""
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'src'
DIST = ROOT / 'dist'


def load_links():
    """Load and return links from `src/links.json` as a Python object.

    Returns:
        list|dict: Parsed JSON content from `links.json`.
    """
    path = SRC / 'links.json'
    return json.loads(path.read_text(encoding='utf-8'))


def build_index(links):
    """Render the index HTML from a template and a list of link entries.

    Args:
        links (list): Sequence of mapping objects containing link metadata.

    Returns:
        str: Rendered HTML for the index page.
    """
    tpl = (SRC / 'index.template.html').read_text(encoding='utf-8')
    items = []
    for l in links:
        name = l.get('name') or l.get('title') or l.get('label') or l.get('url')
        url = l.get('url')
        item = (
            f"<div class=\"link-row\">"
            f"<div class=\"link-title\">{name}</div>"
            f"<div class=\"link-url\"><a href=\"{url}\" target=\"_blank\">{url}</a></div>"
            f"</div>"
        )
        items.append(item)
    html = tpl.replace('<!-- LINKS_LIST_ROWS -->', '\n'.join(items))
    return html


def copy_assets():
    """Copy static assets and stylesheet from `src` into the `dist` folder.

    Ensures `dist` exists, copies `styles.css`, and copies the `assets`
    directory (replacing any existing one).
    """
    DIST.mkdir(parents=True, exist_ok=True)
    # copy styles (overwrite or create)
    styles_src = SRC / 'styles.css'
    styles_dst = DIST / 'styles.css'
    styles_dst.write_text(styles_src.read_text(encoding='utf-8'), encoding='utf-8')
    # copy assets directory if present
    assets_src = SRC / 'assets'
    assets_dst = DIST / 'assets'
    if assets_src.exists() and assets_src.is_dir():
        # remove existing assets dir to ensure fresh copy
        if assets_dst.exists():
            shutil.rmtree(assets_dst)
        shutil.copytree(assets_src, assets_dst)


def write_index(html):
    """Write the generated index HTML to `dist/index.html`.

    Args:
        html (str): HTML content to write.
    """
    DIST.mkdir(parents=True, exist_ok=True)
    (DIST / 'index.html').write_text(html, encoding='utf-8')


def main():
    """Main entry point: build the website into the `dist` directory."""
    links = load_links()
    html = build_index(links)
    copy_assets()
    write_index(html)
    print('Site built into', DIST)


if __name__ == '__main__':
    main()
