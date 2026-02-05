import re, pathlib, xml.etree.ElementTree as ET
from typing import Optional

SRC = "export.xml"
OUT_POSTS = pathlib.Path("slugs.blog.txt")   # ブログ記事
OUT_PAGES = pathlib.Path("slugs.pages.txt")  # 固定ページ（必要なら）

NS = {"wp": "http://wordpress.org/export/1.2/"}

def slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^\w\-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s

def tail_slug(link: str) -> Optional[str]:
    if not link:
        return None
    m = re.search(r"/([^/?#]+)/?$", link.strip())
    return m.group(1) if m else None

def looks_like_image(u: str) -> bool:
    return bool(re.search(r'(\.(jpe?g|png|gif|webp|svg)$|(-|_)jpe?g$|(-|_)png$|(-|_)gif$|(-|_)webp$|(-|_)svg$)', u))

tree = ET.parse(SRC)
root = tree.getroot()
items = root.findall("./channel/item")

posts, pages = set(), set()

for it in items:
    ptype = (it.findtext("wp:post_type", namespaces=NS) or "").strip()
    slug  = (it.findtext("wp:post_name", namespaces=NS) or "").strip()
    link  = (it.findtext("link") or "").strip()

    s = slugify(slug or tail_slug(link) or "")
    if not s:
        continue
    if looks_like_image(s):  # 画像名っぽいものは除外
        continue

    if ptype in {"post", "article"}:
        posts.add(s)
    elif ptype in {"page"}:
        pages.add(s)
    else:
        # attachment などは無視
        pass

OUT_POSTS.write_text("\n".join(sorted(posts)) + "\n", encoding="utf-8")
OUT_PAGES.write_text("\n".join(sorted(pages)) + "\n", encoding="utf-8")

print(f"posts: {len(posts)} -> {OUT_POSTS}")
print(f"pages: {len(pages)} -> {OUT_PAGES}")
