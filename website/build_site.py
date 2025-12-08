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
    path = SRC / 'links.json'
    return json.loads(path.read_text(encoding='utf-8'))


def build_index(links):
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
    DIST.mkdir(parents=True, exist_ok=True)
    (DIST / 'index.html').write_text(html, encoding='utf-8')


def main():
    links = load_links()
    html = build_index(links)
    copy_assets()
    write_index(html)
    print('Site built into', DIST)


if __name__ == '__main__':
    main()
