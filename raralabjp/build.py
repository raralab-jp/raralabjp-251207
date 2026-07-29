#!/usr/bin/env python3
import json, html, re, csv, argparse
from pathlib import Path
import shutil
import sys

from labels import (
    STONE_LABELS,
    ORIGIN_LABELS,
    TREATMENT_LABELS,
    CLARITY_LABELS,
    CERT_LABELS,
    PERSON_LABELS,
    MODIFICATION_LABELS,
    label,
)

# ---- WebP 変換用ライブラリ (Pillow) の読み込み ----
try:
    from PIL import Image
except ImportError:
    Image = None

# ---- Paths / Policy ----
ROOT = Path(__file__).parent.resolve()

# 公開用ルート（ここが Cloudflare Pages の "Build output directory" = site になる）
SITE_ROOT = ROOT / "site"
SITE_ROOT.mkdir(parents=True, exist_ok=True)

DATA = ROOT / "assets" / "data" / "items.json"
MASTER_CSV = ROOT / "assets" / "data" / "items_master.csv"

# ギャラリー・ニュースは site/ 以下に出力
OUT_GALLERY = SITE_ROOT / "gallery"
OUT_GALLERY.mkdir(parents=True, exist_ok=True)
PAGE_SIZE = 24

NEWS_CSV        = ROOT / "assets" / "news" / "news.csv"
NEWS_BODY_DIR   = ROOT / "assets" / "news" / "body"
NEWS_IMAGES_DIR = ROOT / "assets" / "news" / "images"

OUT_NEWS = SITE_ROOT / "news"
OUT_NEWS.mkdir(parents=True, exist_ok=True)

TOP_HERO     = ROOT / "assets" / "partials" / "top_hero.html"
TOP_SECTIONS = ROOT / "assets" / "partials" / "top_sections.html"
PARTIALS_DIR = ROOT / "assets" / "partials"

GEMDIARY_RAW_DIR  = ROOT / "assets" / "gemdiary" / "raw"
GEMDIARY_BODY_DIR = ROOT / "assets" / "gemdiary" / "body"

OUT_GEMDIARY = SITE_ROOT / "gemdiary"

SITE_ORIGIN = "https://raralab.jp"  # 本番ドメインを固定

def build_gallery_canonical(slug: str) -> str:
    return f"{SITE_ORIGIN}/gallery/{slug}/"

def _s(v) -> str:
    """None/float/int などが来ても安全に文字列化してstripする。"""
    if v is None:
        return ""
    return str(v).strip()

def build_gallery_description(it: dict) -> str:
    stone  = _s(it.get("stone"))
    carat  = _s(it.get("carat"))
    origin = _s(it.get("origin_en"))

    base = []
    if stone and carat:
        base.append(f"Rara Labが研磨した{stone} {carat}ctのルース。")
    elif stone:
        base.append(f"Rara Labが研磨した{stone}のルース。")
    else:
        base.append("Rara Labのギャラリー詳細ページです。")

    if origin:
        base.append(f"産地：{origin}。")
    base.append("写真、制作過程、スペック、購入ページへのリンクを掲載しています。")

    return " ".join(base)

def build_news_canonical(slug: str) -> str:
    return f"{SITE_ORIGIN}/news/{slug}/"

def build_news_description(body_html: str, fallback_title: str = "") -> str:
    # HTMLタグを落として、空白を潰して、短くする（だいたい120〜160文字）
    txt = re.sub(r"<[^>]+>", " ", body_html)
    txt = re.sub(r"\s+", " ", txt).strip()
    if not txt:
        txt = fallback_title or "Rara LabのNews記事です。"
    return txt[:160]

def render_head(*, title: str, description: str, canonical: str, og_image: str = "", twitter_site: str = "@raralab") -> str:
    # og_image は絶対URLを推奨
    og_type = "article"  # ギャラリー詳細はとりあえず article でOK（後でProductでも可）
    parts = [
        '<head>',
        '  <meta charset="utf-8">',
        '  <meta name="viewport" content="width=device-width,initial-scale=1">',
        f"  <title>{html.escape(title)}</title>",
        f'  <meta name="description" content="{html.escape(description)}">',
        f'  <link rel="canonical" href="{html.escape(canonical)}">',
        '  <link rel="stylesheet" href="/assets/css/site.css">',
    ]

    if og_image:
        parts += [
            f'  <meta property="og:type" content="{og_type}">',
            '  <meta property="og:site_name" content="Rara Lab">',
            f'  <meta property="og:title" content="{html.escape(title)}">',
            f'  <meta property="og:description" content="{html.escape(description)}">',
            f'  <meta property="og:url" content="{html.escape(canonical)}">',
            f'  <meta property="og:image" content="{html.escape(og_image)}">',
            '  <meta name="twitter:card" content="summary_large_image">',
            f'  <meta name="twitter:site" content="{html.escape(twitter_site)}">',
            f'  <meta name="twitter:title" content="{html.escape(title)}">',
            f'  <meta name="twitter:description" content="{html.escape(description)}">',
            f'  <meta name="twitter:image" content="{html.escape(og_image)}">',
        ]

    parts.append("</head>")
    return "\n".join(parts)

def render_partial(name: str) -> str:
    """
    assets/partials/ 以下の HTML partial を読み込んで文字列として返す。
    例: render_partial("top_logo.html")
    """
    p = PARTIALS_DIR / name.strip()
    return p.read_text(encoding="utf-8") if p.exists() else ""


def inject_footer(html_text: str) -> str:
    footer_html = render_partial("footer.html")
    footer_html = footer_html.strip()
    if not footer_html:
        return html_text

    # 1) </main> の直後（指示どおり）
    if "</main>" in html_text:
        return html_text.replace("</main>", "</main>\n" + footer_html + "\n", 1)

    # 2) main がないページ向けの保険： </body> 直前
    if "</body>" in html_text:
        return html_text.replace("</body>", footer_html + "\n</body>", 1)

    # 3) それも無いなら何もしない
    return html_text


def read_file(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def read_top_hero() -> str:
    return read_file(TOP_HERO)


def read_top_sections() -> str:
    return read_file(TOP_SECTIONS)


def ensure_webp_thumbs():
    """
    assets/images/1200px/ 以下の JPG/PNG から、同名の .webp を自動生成する。
    ・すでに .webp がある場合は何もしない
    ・Pillow が無い場合も何もしない
    """
    if Image is None:
        return

    thumb_dir = ROOT / "assets" / "images" / "1200px"
    if not thumb_dir.exists():
        return

    for p in thumb_dir.iterdir():
        if not p.is_file():
            continue

        ext = p.suffix.lower()
        if ext not in {".jpg", ".jpeg", ".png"}:
            continue

        webp_path = p.with_suffix(".webp")
        if webp_path.exists():
            continue

        try:
            img = Image.open(p)
            img.save(webp_path, format="WEBP", quality=85)
            print(f"[webp] generated: {webp_path.name}")
        except Exception as e:
            print(f"[webp] failed to convert {p.name}: {e}")


def ensure_webp_large():
    """
    assets/images/2500px/ 以下の JPG/PNG から、assets/images/large/ に表示用 WebP を生成する。
    - 差分ビルド（mtimeで新しいものだけ）
    - 長辺 max_long_edge に収める
    """
    if Image is None:
        return

    src_dir = ROOT / "assets" / "images" / "2500px"
    dst_dir = ROOT / "assets" / "images" / "large"
    if not src_dir.exists():
        return

    dst_dir.mkdir(parents=True, exist_ok=True)

    max_long_edge = 1600
    quality = 82

    # EXIF回転対策（縦横事故を防ぐ）
    try:
        from PIL import ImageOps
    except Exception:
        ImageOps = None

    valid_exts = {".jpg", ".jpeg", ".png"}

    for p in src_dir.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in valid_exts:
            continue

        out = dst_dir / (p.stem + ".webp")

        # 差分ビルド
        if out.exists() and out.stat().st_mtime >= p.stat().st_mtime:
            continue

        try:
            img = Image.open(p)
            if ImageOps is not None:
                img = ImageOps.exif_transpose(img)
            if img.mode != "RGB":
                img = img.convert("RGB")

            w, h = img.size
            long_edge = max(w, h)
            if long_edge > max_long_edge:
                scale = max_long_edge / long_edge
                new_size = (round(w * scale), round(h * scale))
                img = img.resize(new_size, resample=Image.Resampling.LANCZOS)

            img.save(out, format="WEBP", quality=quality, method=6, optimize=True)
            print(f"[large] generated: {out.name}")
        except Exception as e:
            print(f"[large] failed: {p.name}: {e}")


def ensure_webp_news_images():
    """
    assets/news/images/ 以下の JPG/PNG から、同名の .webp を自動生成する。
    ・すでに .webp がある場合は何もしない
    ・Pillow が無い場合も何もしない
    """
    if Image is None:
        return

    news_dir = NEWS_IMAGES_DIR
    if not news_dir.exists():
        return

    for p in news_dir.iterdir():
        if not p.is_file():
            continue

        ext = p.suffix.lower()
        if ext not in {".jpg", ".jpeg", ".png"}:
            continue

        webp_path = p.with_suffix(".webp")
        if webp_path.exists():
            continue

        try:
            img = Image.open(p)
            img.save(webp_path, format="WEBP", quality=85)
            print(f"[webp-news] generated: {webp_path.name}")
        except Exception as e:
            print(f"[webp-news] failed to convert {p.name}: {e}")


# 表示ポリシー
SHOW_BREADCRUMB = False
SHOW_SPECS      = True   # Stone / Carat / Design の3点のみ表示（＋追加行は許容）

# ---- Partials ----
INTRO = ROOT / "assets" / "partials" / "top_intro.html"
CTA   = ROOT / "assets" / "partials" / "top_cta.html"


def read_intro():
    return INTRO.read_text(encoding="utf-8") if INTRO.exists() else ""


def read_cta():
    return CTA.read_text(encoding="utf-8") if CTA.exists() else ""


# ---- Data ----
def read_items():
    items = json.loads(DATA.read_text(encoding="utf-8"))
    # 新しい順（date がない場合は末尾）
    items.sort(key=lambda x: x.get("date", ""), reverse=True)
    return items


def read_news_items():
    """
    assets/news/news.csv を読み込んで、日付降順に並べた dict のリストを返す。
    カラム: slug,date,title,summary,body_file,image_file
    """
    items = []
    if not NEWS_CSV.exists():
        return items

    with NEWS_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["slug"]       = (row.get("slug") or "").strip()
            row["date"]       = (row.get("date") or "").strip()
            row["title"]      = (row.get("title") or "").strip()
            row["summary"]    = (row.get("summary") or "").strip()
            row["body_file"]  = (row.get("body_file") or "").strip()
            row["image_file"] = (row.get("image_file") or "").strip()

            if row["slug"]:
                items.append(row)

    items.sort(key=lambda x: x.get("date", ""), reverse=True)
    return items


def resolve_news_image_src(image_file: str) -> str:
    """
    news.csv の image_file から、WebP 優先の画像パスを決める。

    - CSV が "DSC_1777.jpg" のようにファイル名だけの場合:
        → "news/images/DSC_1777.jpg" を基準に探す
    - "news/images/DSC_1777.jpg" や "/news/images/DSC_1777.jpg" でもOK
    - 同じ場所に .webp があればそちらを優先
    """
    if not image_file:
        return ""

    image_file = image_file.strip()
    if not image_file:
        return ""

    if image_file.upper() in {"NO_IMAGE", "NONE", "N/A", "-"}:
        return ""

    if "/" in image_file:
        rel = image_file.lstrip("/")  # "news/images/DSC_1777.jpg"
    else:
        rel = f"news/images/{image_file}"

    p = SITE_ROOT / rel

    if p.suffix.lower() == ".webp":
        return "/" + rel

    folder = p.parent
    stem   = p.stem

    webp_path = folder / (stem + ".webp")
    if webp_path.exists():
        rel_webp = f"news/images/{webp_path.name}"
        return "/" + rel_webp

    if p.exists():
        rel_orig = f"news/images/{p.name}"
        return "/" + rel_orig

    return "/" + rel


def render_news_index_card(n: dict) -> str:
    """
    ニュース一覧用：ギャラリー寄せのカード構造（.rl-item）
    画像サムネ＋タイトル＋日付＋要約を表示する。
    """
    slug    = (n.get("slug") or "").strip()
    date    = (n.get("date") or "").strip()
    title   = (n.get("title") or "").strip()
    summary = (n.get("summary") or "").strip()
    image   = (n.get("image_file") or "").strip()

    url = f"/news/{slug}/" if slug else "#"

    title_text   = title or slug
    title_html   = html.escape(title_text)
    date_html    = html.escape(date)
    summary_html = html.escape(summary)

    img_src = resolve_news_image_src(image) if image else ""

    img_tag = ""
    if img_src:
        img_tag = (
            f'<img src="{img_src}" alt="{title_html}" '
            f'loading="lazy" decoding="async">'
        )

    summary_block = f'\n      <p class="news-summary">{summary_html}</p>' if summary else ""

    return f'''<figure class="rl-item">
  <a href="{url}" class="rl-link">
    {img_tag}
    <figcaption class="rl-caption">
      <span class="rl-title">{title_html}</span>
      <span class="news-date">{date_html}</span>{summary_block}
    </figcaption>
  </a>
</figure>'''


def render_news_list_items(news_items, limit=None) -> str:
    """
    トップページ用のテキストリスト（既存仕様を維持）
    """
    rows = news_items
    if limit is not None:
        rows = news_items[:limit]

    lis = []
    for n in rows:
        date    = html.escape(n.get("date") or "")
        title   = html.escape(n.get("title") or "")
        summary = html.escape(n.get("summary") or "")
        slug    = n.get("slug") or ""
        url     = f"/news/{slug}/" if slug else "#"

        summary_html = f'\n            <p class="news-summary">{summary}</p>' if summary else ""

        lis.append(
f'''          <li class="news-item">
            <span class="news-date">{date}</span>
            <a class="news-title" href="{url}">{title}</a>{summary_html}
          </li>'''
        )
    return "\n".join(lis)


def top_news_card_html(n: dict) -> str:
    """
    トップページ用ニュースカード（.news-card 依存）。
    - サムネあり: <img>
    - サムネなし: .news-card-thumb--empty を出す（CSSでグレー枠）
    """
    slug    = (n.get("slug") or "").strip()
    date    = (n.get("date") or "").strip()
    title   = (n.get("title") or "").strip()
    summary = (n.get("summary") or "").strip()
    image   = (n.get("image_file") or "").strip()

    url = f"/news/{slug}/" if slug else "#"

    title_html   = html.escape(title or slug)
    date_html    = html.escape(date)
    summary_html = html.escape(summary)

    img_src = resolve_news_image_src(image) if image else ""

    if img_src:
        thumb_html  = f'<img src="{img_src}" alt="{title_html}" loading="lazy" decoding="async">'
        thumb_class = "news-card-thumb"
    else:
        thumb_html  = ""
        thumb_class = "news-card-thumb news-card-thumb--empty"

    summary_block = f'<p class="news-card-summary">{summary_html}</p>' if summary else ""

    return f'''<article class="news-card">
  <a class="news-card-link" href="{url}">
    <div class="{thumb_class}">
      {thumb_html}
    </div>
    <div class="news-card-body">
      <h3 class="news-card-title">{title_html}</h3>
      <p class="news-card-date">{date_html}</p>
      {summary_block}
    </div>
  </a>
</article>'''

def news_index_html(cards: str, prev_link: str = None, next_link: str = None, canonical: str = "") -> str:
    """
    ニュース一覧ページ全体のHTML。
    ヘッダーは「ロゴ → メニュー」を共通で表示する。
    canonical は呼び出し側で、そのページの絶対URLを渡す（推奨）。
    """
    pager_parts = []
    if prev_link or next_link:
        pager_parts.append('<nav class="gallery-pager">')
        if prev_link:
            pager_parts.append(f'<a class="pager-prev" href="{prev_link}">前のページ</a>')
        else:
            pager_parts.append('<span class="pager-prev"></span>')
        if next_link:
            pager_parts.append(f'<a class="pager-next" href="{next_link}">次のページ</a>')
        else:
            pager_parts.append('<span class="pager-next"></span>')
        pager_parts.append('</nav>')

    pager_html = "\n".join(pager_parts)

    logo_html = render_partial("top_logo.html")
    nav_html  = render_partial("nav_main.html")

    seo_title = "News | Rara Lab"
    description = "Rara Labの活動に関する更新情報をまとめています。出品やサイト更新など、節目となる内容を掲載しています。"

    # canonical 未指定なら /news/ を使う（最低限の安全策）
    can = canonical.strip() or f"{SITE_ORIGIN}/news/"

    head_html = render_head(
        title=seo_title,
        description=description,
        canonical=can,
        og_image=f"{SITE_ORIGIN}/assets/images/top/raralab-logo-l.png",  # 画像は無難に固定（任意）
    )

    return f'''<!doctype html>
<html lang="ja">
{head_html}
<body>
{logo_html}
{nav_html}
<main class="news-index">

  <section class="gallery-head">
    <h1>News</h1>
    <div class="gallery-note">
      <p>
        Rara Labの活動に関する更新情報をまとめています。
      </p>
      <p>
        出品やサイト更新など、節目となる内容を掲載しています。
      </p>
    </div>
  </section>

  <section class="rl-gallery news-gallery">
{cards}
  </section>

{pager_html}

</main>
</body>
</html>
'''

def extract_gemdiary_meta(raw_index_path: Path) -> dict:
    text = raw_index_path.read_text(encoding="utf-8", errors="replace")

    def m1(pattern: str) -> str:
        m = re.search(pattern, text, flags=re.I)
        return m.group(1).strip() if m else ""

    title = m1(r"<title>\s*(.*?)\s*</title>")
    date  = m1(r'<meta\s+name="date"\s+content="([^"]+)"')
    canonical = m1(r'<link\s+rel="canonical"\s+href="([^"]+)"')

    return {"title": title, "date": date, "canonical": canonical}

def gemdiary_detail_html(meta: dict, body_html: str) -> str:
    slug = (meta.get("slug") or "").strip()

    title_raw = (meta.get("title") or "")
    date_raw  = (meta.get("date") or "")

    title = html.escape(title_raw)
    date  = html.escape(date_raw)

    # dateは本文の上に軽く出す（不要なら消してOK）
    date_block = f'<p class="post-date">{date}</p>' if date_raw else ""

    body_block = f'''
      <section class="post-body">
        {date_block}
        {body_html}
      </section>'''

    seo_title = f"{title_raw} | Rara Lab" if title_raw else "Gem Diary | Rara Lab"

    # canonical は基本ここで生成。rawにあるcanonicalと一致するので安心。
    canonical = f"{SITE_ORIGIN}/gemdiary/{slug}/" if slug else f"{SITE_ORIGIN}/gemdiary/"

    description = build_news_description(body_html, fallback_title=title_raw)  # 既存関数流用

    head_html = render_head(
        title=seo_title,
        description=description,
        canonical=canonical,
        og_image=""
    )

    logo_html = render_partial("top_logo.html")
    nav_html  = render_partial("nav_main.html")

    return f'''<!doctype html>
<html lang="ja">
{head_html}
<body>
{logo_html}
{nav_html}
  <main class="detail gemdiary-detail">
    <article>
      <h1>{title}</h1>
{body_block}
      <p class="post-back"><a href="/news/">Newsへ</a></p>
    </article>
  </main>
</body>
</html>'''


def news_detail_html(news: dict, body_html: str) -> str:
    """
    個別NewsページのフルHTMLを返す。
    body_html は assets/news/body/<slug>.html に書いた本文スニペット。
    """
    slug = (news.get("slug") or "").strip()

    date_raw  = (news.get("date") or "")
    title_raw = (news.get("title") or "")

    date  = html.escape(date_raw)
    title = html.escape(title_raw)

    # ---- hero image block ----
    hero_block = ""
    image_file = (news.get("image_file") or "").strip()
    og_image = ""
    if image_file:
        src = resolve_news_image_src(image_file)
        if src:
            src_attr = html.escape(src)
            hero_block = f'''
      <section class="news-hero">
        <p class="news-image">
          <img src="{src_attr}" alt="{title}">
        </p>
      </section>'''
            # og:image は絶対URL推奨
            og_image = src if src.startswith("http") else (SITE_ORIGIN + src)

    # ---- body with date injection ----
    if "</h1>" in body_html:
        body_with_date = re.sub(
            r"</h1>",
            '</h1>\n<p class="news-date">' + date + "</p>",
            body_html,
            count=1,
        )
    else:
        body_with_date = f'<p class="news-date">{date}</p>\n{body_html}'

    body_block = f'''
      <section class="news-body">
        {body_with_date}
        <p class="news-back"><a href="/news/">News 一覧へ戻る</a></p>
      </section>'''

    # ---- SEO/head ----
    seo_title = f"{title_raw} | Rara Lab" if title_raw else "News | Rara Lab"
    canonical = build_news_canonical(slug) if slug else f"{SITE_ORIGIN}/news/"
    description = build_news_description(body_html, fallback_title=title_raw)

    head_html = render_head(
        title=seo_title,
        description=description,
        canonical=canonical,
        og_image=og_image
    )

    logo_html = render_partial("top_logo.html")
    nav_html  = render_partial("nav_main.html")

    return f'''<!doctype html>
<html lang="ja">
{head_html}
<body>
{logo_html}
{nav_html}
  <main class="detail news-detail">
    <article>
{hero_block}{body_block}
    </article>
  </main>
</body>
</html>'''

# ---- Image helpers ----
def primary_images(slug: str):
    """一覧カード用thumbと、詳細での最初の4Kを返す（coverのみ）"""
    exts = (".webp", ".jpg", ".jpeg", ".png", ".WEBP", ".JPG", ".JPEG", ".PNG")
    base_names = [
        f"{slug}-cover",
        f"{slug.replace('-', '_')}-cover",
    ]

    thumb_dir = ROOT / "assets" / "images" / "1200px"
    fourk_dir = ROOT / "assets" / "images" / "2500px"

    thumb = None
    fourk = None

    for base in base_names:
        for ext in exts:
            p = thumb_dir / f"{base}{ext}"
            if p.exists():
                thumb = f"/assets/images/1200px/{p.name}"
                break
        if thumb:
            break

    for base in base_names:
        for ext in exts:
            p = fourk_dir / f"{base}{ext}"
            if p.exists():
                fourk = f"/assets/images/2500px/{p.name}"
                break
        if fourk:
            break

    return thumb, fourk

def thumb_to_4k(thumb_path: str) -> str:
    """
    サムネのパス (/assets/images/1200px/xxx.ext) から、
    実際に存在する 4K 画像 (/assets/images/2500px/xxx.*) を探して返す。
    なければ拡張子そのままで /4k/ に置き換えたものを返す（後方互換用）。
    """
    name = Path(thumb_path).name
    stem = Path(name).stem

    fourk_dir = ROOT / "assets" / "images" / "2500px"
    exts = (".webp", ".jpg", ".jpeg", ".png", ".WEBP", ".JPG", ".JPEG", ".PNG")

    for ext in exts:
        candidate = fourk_dir / f"{stem}{ext}"
        if candidate.exists():
            return f"/assets/images/2500px/{candidate.name}"

    return thumb_path.replace("/1200px/", "/2500px/")


def path_to_large(src_path: str) -> str:
    """
    /assets/images/2500px/xxx.jpg or /assets/images/1200px/xxx.webp などから
    /assets/images/large/xxx.webp を返す（表示用）。
    """
    name = Path(src_path).name
    stem = Path(name).stem
    return f"/assets/images/large/{stem}.webp"


def all_images(slug: str, image_order: str = ""):
    """
    サムネ用フォルダから slug で始まるファイルを列挙する。
    WebP と JPG/PNG が重複している場合、WebP を優先して採用し、JPG/PNG は除外する。
    """
    thumb_dir = ROOT / "assets" / "images" / "1200px"
    if not thumb_dir.exists():
        return []

    want_prefixes = [slug, slug.replace("-", "_")]
    exts = (".webp", ".jpg", ".jpeg", ".png", ".WEBP", ".JPG", ".JPEG", ".PNG")

    candidates = []
    for p in thumb_dir.iterdir():
        if not p.is_file():
            continue
        name = p.name
        low  = name.lower()

        if not any(low.endswith(ext.lower()) for ext in exts):
            continue
        if not any(low.startswith(pref.lower()) for pref in want_prefixes):
            continue

        is_cover = "-cover." in low or "_cover." in low
        path = f"/assets/images/1200px/{name}"
        candidates.append((name, path, is_cover))

    if not candidates:
        return []

    # 重複除外（WebP優先）
    grouped = {}
    for name, path, is_cover in candidates:
        stem = Path(name).stem
        grouped.setdefault(stem, []).append((name, path, is_cover))

    unique_candidates = []
    for stem, group in grouped.items():
        selected = None
        for item in group:
            if item[0].lower().endswith(".webp"):
                selected = item
                break
        if not selected:
            selected = group[0]
        unique_candidates.append(selected)

    covers  = [path for (name, path, is_cover) in unique_candidates if is_cover]
    normals = [(name, path) for (name, path, is_cover) in unique_candidates if not is_cover]

    def extract_id(name: str) -> str:
        base = Path(name).stem
        for pref in [slug, slug.replace("-", "_")]:
            if base.startswith(pref):
                suf = base[len(pref):]
                return suf.lstrip("-_")
        return base

    normals_with_id = [(extract_id(name), path) for (name, path) in normals]

    order_ids = []
    if image_order:
        for token in re.split(r"[,\s]+", image_order):
            t = token.strip()
            if t:
                order_ids.append(t)

    ordered_normals = []
    used = set()

    for oid in order_ids:
        for nid, path in normals_with_id:
            if nid == oid and path not in used:
                ordered_normals.append(path)
                used.add(path)

    remaining = [path for (nid, path) in normals_with_id if path not in used]
    remaining.sort()
    ordered_normals.extend(remaining)

    covers_sorted = sorted(covers)
    paths = covers_sorted + ordered_normals

    primary_thumb, _ = primary_images(slug)
    if primary_thumb and primary_thumb in paths:
        paths.remove(primary_thumb)
        paths.insert(0, primary_thumb)

    return paths

def is_truthy(v) -> bool:
    s = (v or "").strip().lower()
    return s in ("1", "true", "yes", "y", "on")

def design_display(design: str, is_named: bool) -> str:
    d = (design or "").strip()
    if not d:
        return ""
    return f'“{d}”' if is_named else d

def render_gallery_card(it):
    """ギャラリー／トップ用の一覧カード（画像＋日本語タイトル1本）"""
    slug = it["slug"]

    title_jp = (it.get("title_jp") or "").strip()
    if not title_jp:
        stone  = (it.get("stone") or "").strip()
        carat  = (it.get("carat") or "").strip()
        design = (it.get("design_name") or "").strip()

        primary = f"{stone} – {carat}ct" if stone and carat else (stone or slug)

        design_named = is_truthy(it.get("design_is_named"))
        secondary = f" {design_display(design, design_named)}" if design else ""

        title_jp = (primary + secondary).strip()

    thumb, _ = primary_images(slug)

    img_tag = ""
    if thumb:
        alt_text = title_jp or slug
        img_tag = (
            f'<img src="{thumb}" alt="{html.escape(alt_text)}" '
            f'loading="lazy" decoding="async">'
        )

    caption_html = ""
    if title_jp:
        caption_html = (
            f'<figcaption class="rl-caption">'
            f'<span class="rl-title">{html.escape(title_jp)}</span>'
            f'</figcaption>'
        )

    return f'''<figure class="rl-item">
  <a href="/gallery/{slug}/" class="rl-link">
    {img_tag}
    {caption_html}
  </a>
</figure>'''

# ---- Compatibility wrappers (avoid "missing function" confusion) ----
def card_html(it: dict) -> str:
    return render_gallery_card(it)


def news_card_html(n: dict) -> str:
    return render_news_index_card(n)


def gallery_index_html(cards: str, prev_link: str = None, next_link: str = None, canonical: str = "") -> str:
    """
    ギャラリー一覧ページ全体のHTML。
    ヘッダーは「ロゴ → メニュー」を共通で表示する。
    canonical は呼び出し側で、そのページの絶対URLを渡す（推奨）。
    """
    pager_parts = []
    if prev_link or next_link:
        pager_parts.append('<nav class="gallery-pager">')
        if prev_link:
            pager_parts.append(f'<a class="pager-prev" href="{prev_link}">前のページ</a>')
        else:
            pager_parts.append('<span></span>')
        if next_link:
            pager_parts.append(f'<a class="pager-next" href="{next_link}">次のページ</a>')
        pager_parts.append('</nav>')

    pager_html = "\n".join(pager_parts)

    logo_html = render_partial("top_logo.html")
    nav_html  = render_partial("nav_main.html")

    seo_title = "Gallery | Rara Lab"
    description = "Rara Labがこれまでに制作した作品ギャラリーです。写真、制作過程、スペック、購入ページへのリンクを掲載しています。販売状況はショップの商品ページでご確認いただけます。"

    can = canonical.strip() or f"{SITE_ORIGIN}/gallery/"

    head_html = render_head(
        title=seo_title,
        description=description,
        canonical=can,
        og_image=f"{SITE_ORIGIN}/assets/images/top/raralab-logo-l.png",  # 固定でOK（任意）
    )

    return f'''<!doctype html>
<html lang="ja">
{head_html}
<body>
{logo_html}
{nav_html}
<main class="gallery-index">

  <section class="gallery-head">
    <h1>Gallery</h1>
    <div class="gallery-note">
      <p>
      このギャラリーでは、Rara Labがこれまでに制作した作品をご紹介しています。
      </p>
      <p>
      一部に販売を終了している作品も含まれます。現在の販売状況は、ショップの商品ページでご確認いただけます。
      </p>
    </div>
  </section>

  <section class="rl-gallery">
{cards}
  </section>

{pager_html}

</main>
</body>
</html>
'''


def top_index_html(new_cards: str, top_news_cards_html: str) -> str:
    """
    トップページ（/index.html）のHTML。
    News は「画像の下にテキスト」カードを3件表示する（追加のテキスト一覧は出さない）。
    """
    logo_html      = render_partial("top_logo.html")
    hero_html      = read_top_hero()
    nav_html       = render_partial("nav_main.html")
    intro_html     = read_intro()
    sections_html  = read_file(ROOT / "assets" / "partials" / "top_sections.html")
    more_html      = read_file(ROOT / "assets" / "partials" / "top_more.html")
    cta_html       = read_cta()

    gallery_block = f'''
<section class="top-section top-gallery">
  <h2 class="section-doubleline">Current Works</h2>
  <section class="rl-gallery">
{new_cards}
  </section>
</section>
'''

    news_block = f'''
<section class="top-section top-news">
  <h2 class="section-doubleline">News</h2>
  <div class="news-cards">
{top_news_cards_html}
  </div>
  <div class="news-more">
    <a href="/news/">News 一覧を見る</a>
  </div>
</section>
'''

    # ---- SEO / head ----
    seo_title = "Rara Lab | Faceted Gemstones and Gallery"
    description = (
        "Rara Labは、ファセットカットによる宝石ルースを制作・展示するギャラリーサイトです。"
        "研磨作品の写真、制作過程、スペック、販売情報を掲載しています。"
    )

    canonical = f"{SITE_ORIGIN}/"
    og_image = f"{SITE_ORIGIN}/assets/images/top/raralab-logo-l.png"
    # ※ ヒーロー画像をOGPに使いたくなったら、ここを差し替えるだけ

    head_html = render_head(
        title=seo_title,
        description=description,
        canonical=canonical,
        og_image=og_image,
    )

    return f'''<!doctype html>
<html lang="ja">
{head_html}
<body class="home">
{logo_html}
{hero_html}
{nav_html}
{intro_html}
{sections_html}
{gallery_block}
{news_block}
{more_html}
{cta_html}
</body>
</html>'''


def detail_html(it):
    """ギャラリー／詳細ページ（1石）のフルHTMLを返す。"""
    slug   = it["slug"]
    stone  = it.get("stone","")
    carat = _s(it.get("carat"))
    design = it.get("design_name","")

    title    = f'{stone} – {carat}ct' if stone and carat else (stone or slug)

    # Quote control for design name
    design_named = is_truthy(it.get("design_is_named"))
    subtitle = design_display(design, design_named) if design else ''

    breadcrumb = '' if not SHOW_BREADCRUMB else '<nav class="breadcrumb"><a href="/gallery/">← Back to Gallery</a></nav>'

    hero_thumb, hero_4k = primary_images(slug)
    if not hero_thumb:
        print(f"WARN: hero cover image missing for slug={slug}", file=sys.stderr)

    raw_image_order = it.get("image_order", "") or ""

    # "process_image_order:" が混入していたら除去（保険）
    raw_image_order = re.sub(r"\bprocess_image_order\s*:\s*", "", str(raw_image_order), flags=re.IGNORECASE)

    # IDっぽいもの（DSC_#### など）だけ抽出して並べ直す
    order_ids = re.findall(r"(?:DSC_\d+|IMG_\d+|IMGP_\d+|\d{4,})", raw_image_order)

    image_order = " ".join(order_ids)
    thumbs_all = all_images(slug, image_order=image_order)

    process_order = (it.get("process_image_order", "") or "").strip()
    process_ids = [t for t in re.split(r"[,\s]+", process_order) if t.strip()]

    def _thumb_id(path: str) -> str:
        stem = Path(path).stem
        for pref in (slug, slug.replace("-", "_")):
            if stem.startswith(pref + "-"):
                return stem[len(pref) + 1 :]
            if stem.startswith(pref + "_"):
                return stem[len(pref) + 1 :]
            if stem == pref:
                return ""
        return stem

    process_set = set(process_ids)
    order_index = {pid: i for i, pid in enumerate(process_ids)}

    process_thumbs = [p for p in thumbs_all if _thumb_id(p) in process_set]
    process_thumbs.sort(key=lambda p: order_index.get(_thumb_id(p), 10**9))

    thumbs = [p for p in thumbs_all if _thumb_id(p) not in process_set]

    hero_display = ""
    hero_full = ""

    if hero_4k:
        hero_display = path_to_large(hero_4k)
        hero_full    = hero_4k
    elif hero_thumb:
        hero_display = path_to_large(hero_thumb)
        hero_full    = thumb_to_4k(hero_thumb)

    hero_html = ""
    if hero_display:
        hero_html = f'''
        <a href="#" class="hero-link" data-full="{hero_full}">
          <img class="hero"
               src="{hero_display}"
               alt="{html.escape(title)}"
               loading="eager"
               fetchpriority="high"
               decoding="async">
        </a>'''.strip()

    video_html = ""
    video_url = it.get("video_url")
    if video_url:
        video_html = f'''
  <section class="hero-video">
    <div class="hero-video-inner">
      <iframe
        src="{html.escape(video_url)}"
        allow="autoplay; encrypted-media"
        allowfullscreen
      ></iframe>
    </div>
  </section>
'''

    def render_thumbs_block(th_list, label_text=None, kind="photos"):
        if not th_list:
            return ""

        items = []
        for t in th_list:
            f4k = thumb_to_4k(t)
            active = "active" if (t == hero_thumb) else ""
            img_class_attr = f' class="{active}"' if active else ""
            items.append(
                f'<a class="thumb" href="#" data-full="{f4k}">'
                f'<img src="{t}"{img_class_attr} alt="" loading="lazy" decoding="async"></a>'
            )

        label_html = f'<p class="thumbs-label">{html.escape(label_text)}</p>\n' if label_text else ""
        return label_html + f'<div class="thumbs thumbs--{kind}">\n' + "\n".join(items) + "\n</div>"

    blocks = []
    if thumbs:
        blocks.append(render_thumbs_block(thumbs, "", kind="photos"))
    if process_thumbs:
        blocks.append(render_thumbs_block(process_thumbs, "Making", kind="process"))

    thumbs_html = ""
    if blocks:
        thumbs_html = '<section class="thumbs-wrap">\n' + "\n".join(blocks) + "\n</section>"

    plate_html = ""
    cta_html   = ""

    if SHOW_SPECS:
        title_jp  = (it.get("title_jp") or "").strip()
        stone_en  = (it.get("stone") or "").strip()
        carat     = it.get("carat", "")
        design_en = (it.get("design_name") or "").strip()
        faceter   = (it.get("faceted_by") or "").strip()
        origin_en = (it.get("origin_en") or "").strip()
        product_url = (it.get("shop_url") or "").strip()

        mod_note = (it.get("modification_note") or "").strip()

        final_lines = []
        if title_jp:
            final_lines.append(f'  <p class="jp">{html.escape(title_jp)}</p>')

        if stone_en:
            final_lines.append(f'  <p class="en">{html.escape(stone_en)}</p>')

        if design_en:
            d = design_display(html.escape(design_en), design_named)
            final_lines.append(f'  <p class="en">Design: {d}</p>')

        if mod_note:
            final_lines.append(f'  <p class="en">Modification: {html.escape(mod_note)}</p>')

        if faceter:
            final_lines.append(f'  <p class="meta">Faceted by {html.escape(faceter)}</p>')
        if origin_en:
            final_lines.append(f'  <p class="meta">Origin: {html.escape(origin_en)}</p>')

        if final_lines:
            plate_html = '<section class="plate">\n' + "\n".join(final_lines) + "\n</section>"

        if product_url:
            cta_html = f'''<section class="cta-block">
  <a href="{html.escape(product_url)}" class="cta-link" target="_blank" rel="noopener">ご購入はこちら →</a>
</section>'''

    logo_html = render_partial("top_logo.html")
    nav_html  = render_partial("nav_main.html")

    # ---- SEO values ----
    h1_title = title  # 既存の見出し用
    seo_title = f"{h1_title} | Rara Lab"

    canonical = build_gallery_canonical(slug)
    description = build_gallery_description(it)

    # og:image は「ヒーロー画像があれば使う」。Xの見栄え重視なら jpg(4k) 推奨
    og_image = ""
    if hero_4k:
        og_image = SITE_ORIGIN + hero_4k  # hero_4k は "/assets/..." 形式なので絶対URL化
    elif hero_display:
        og_image = SITE_ORIGIN + hero_display

    head_html = render_head(
        title=seo_title,
        description=description,
        canonical=canonical,
        og_image=og_image
    )

    return f'''<!doctype html>
<html lang="ja">
{head_html}
<body>
{logo_html}
{nav_html}
<main class="detail">
  {breadcrumb}
  <h1 class="title">{html.escape(h1_title)}</h1>
  {'<h2 class="subtitle">'+html.escape(subtitle)+'</h2>' if subtitle else ''}
  <section class="hero">
    {hero_html}
  </section>
  {video_html}
  {thumbs_html}
  {plate_html}
  {cta_html}
</main>

<div class="lb-root" data-lb-root hidden>
  <div class="lb-backdrop" data-lb-close></div>
  <div class="lb-frame">
    <button type="button" class="lb-close" data-lb-close>×</button>
    <button type="button" class="lb-prev" data-lb-prev>‹</button>
    <img class="lb-img" data-lb-img src="" alt="">
    <button type="button" class="lb-next" data-lb-next>›</button>
  </div>
</div>

<script src="/assets/js/lightbox.js"></script>
</body>
</html>
'''

# ---- Master CSV / Listing renderer ----
MASTER_FIELDNAMES = [
    "slug", "stone", "design_name", "designer", "faceted_by", "carat",
    "size_mm", "origin_en", "treatment", "clarity_note_en",
    "title_jp", "date", "tags", "image_order", "process_image_order", "video_url", "shop_url",
    "modification_note", "design_is_named",
    "product_id", "stone_ja", "faceted_by_ja", "origin_ja", "treatment_ja", "clarity_note_ja",
    "cert_lab_ja", "cert_lab_en", "title_jp_override", "clarity_note_ja_override", "clarity_note_en_override", "gallery_url", "note_url", "cut_note",
]


def _mv(row: dict, key: str) -> str:
    return _s(row.get(key))

def display_value(row: dict, key: str, table: dict, lang: str, fallback_key: str = "") -> str:
    raw = _mv(row, key)
    if raw:
        return label(table, raw, lang)

    if fallback_key:
        return _mv(row, fallback_key)

    return ""

def read_master_csv(csv_path: Path):
    rows = []
    if not csv_path.exists():
        return rows
    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k: _s(v) for k, v in row.items()})
    return rows


def design_display_text(design_name: str, design_is_named: str) -> str:
    design_name = _s(design_name)
    if not design_name:
        return ""
    return f'“{design_name}”' if _s(design_is_named) == "1" else design_name


def resolve_title_jp(row: dict) -> str:
    override = _mv(row, "title_jp_override")
    if override:
        return override

    stone_ja = label(STONE_LABELS, _mv(row, "stone"), "ja")
    carat = _mv(row, "carat")
    design_name = _mv(row, "design_name")

    if stone_ja and carat and design_name:
        return f'{stone_ja} {carat}ct {design_display_text(design_name, row.get("design_is_named"))}'

    title_jp = _mv(row, "title_jp")
    if title_jp:
        return title_jp

    return ""


def resolve_clarity_note_ja(row: dict) -> str:
    return _mv(row, "clarity_note_ja_override") or _mv(row, "clarity_note_ja")


def resolve_clarity_note_en(row: dict) -> str:
    return _mv(row, "clarity_note_en_override") or _mv(row, "clarity_note_en")


def master_row_to_gallery_item(row: dict) -> dict:
    return {
        "slug": _mv(row, "slug"),
        "title": resolve_title_jp(row),
        "title_jp": resolve_title_jp(row),
        "stone": _mv(row, "stone"),
        "stone_ja": _mv(row, "stone_ja"),
        "carat": _mv(row, "carat"),
        "design_name": _mv(row, "design_name"),
        "designer": _mv(row, "designer"),
        "faceted_by": _mv(row, "faceted_by"),
        "faceted_by_ja": _mv(row, "faceted_by_ja"),
        "origin_en": _mv(row, "origin_en"),
        "origin_ja": _mv(row, "origin_ja"),
        "treatment": _mv(row, "treatment"),
        "treatment_ja": _mv(row, "treatment_ja"),
        "clarity_note_en": resolve_clarity_note_en(row),
        "clarity_note_ja": resolve_clarity_note_ja(row),
        "cert_lab_ja": _mv(row, "cert_lab_ja"),
        "cert_lab_en": _mv(row, "cert_lab_en"),
        "size_mm": _mv(row, "size_mm"),
        "product_id": _mv(row, "product_id"),
        "modification_note": _mv(row, "modification_note"),
        "design_is_named": _mv(row, "design_is_named"),
        "date": _mv(row, "date"),
        "image_order": _mv(row, "image_order"),
        "process_image_order": _mv(row, "process_image_order"),
        "video_url": _mv(row, "video_url"),
        "shop_url": _mv(row, "shop_url"),
        "tags": _mv(row, "tags"),
    }

def warn_unknown_label(table: dict, value: str, field_name: str):
    value = _s(value)
    if value and value not in table:
        print(
            f"WARN: Unknown {field_name} label: {value}",
            file=sys.stderr,
        )

def render_listing_blocks(row: dict) -> dict:
    warn_unknown_label(STONE_LABELS, _mv(row, "stone"), "stone")
    warn_unknown_label(ORIGIN_LABELS, _mv(row, "origin_en"), "origin")
    warn_unknown_label(TREATMENT_LABELS, _mv(row, "treatment"), "treatment")
    warn_unknown_label(CLARITY_LABELS, resolve_clarity_note_en(row), "clarity")
    warn_unknown_label(PERSON_LABELS, _mv(row, "designer"), "designer")
    warn_unknown_label(PERSON_LABELS, _mv(row, "faceted_by"), "faceted_by")
    warn_unknown_label(CERT_LABELS, _mv(row, "cert_lab_ja") or _mv(row, "cert_lab_en"), "cert_lab")
    warn_unknown_label(
        MODIFICATION_LABELS,
        _mv(row, "modification_note"),
        "modification_note",
    )
    title_jp = resolve_title_jp(row)
    clarity_raw = resolve_clarity_note_en(row)
    clarity_ja = label(CLARITY_LABELS, clarity_raw, "ja")
    clarity_en = label(CLARITY_LABELS, clarity_raw, "en")
    additional_note = _mv(row, "additional_note")

    stone_ja = label(STONE_LABELS, _mv(row, "stone"), "ja")
    stone_en = label(STONE_LABELS, _mv(row, "stone"), "en")

    origin_ja = label(ORIGIN_LABELS, _mv(row, "origin_en"), "ja")
    origin_en = label(ORIGIN_LABELS, _mv(row, "origin_en"), "en")

    treatment_ja = label(TREATMENT_LABELS, _mv(row, "treatment"), "ja")
    treatment_en = label(TREATMENT_LABELS, _mv(row, "treatment"), "en")

    design_jp = design_display_text(_mv(row, "design_name"), row.get("design_is_named"))
    design_en = design_display_text(_mv(row, "design_name"), row.get("design_is_named"))

    designer_ja = label(PERSON_LABELS, _mv(row, "designer"), "ja")
    designer_en = label(PERSON_LABELS, _mv(row, "designer"), "en")

    faceted_by_ja = label(PERSON_LABELS, _mv(row, "faceted_by"), "ja")
    faceted_by_en = label(PERSON_LABELS, _mv(row, "faceted_by"), "en")

    cert_lab_ja = label(CERT_LABELS, _mv(row, "cert_lab_ja") or _mv(row, "cert_lab_en"), "ja")
    cert_lab_en = label(CERT_LABELS, _mv(row, "cert_lab_en") or _mv(row, "cert_lab_ja"), "en")

    modification_ja = label(
        MODIFICATION_LABELS,
        _mv(row, "modification_note"),
        "ja",
    )

    modification_en = label(
        MODIFICATION_LABELS,
        _mv(row, "modification_note"),
        "en",
    )

    ja_basic_lines = []
    if stone_ja:
        ja_basic_lines.append(f"石種：{stone_ja}")
    if origin_ja:
        ja_basic_lines.append(f"産地：{origin_ja}")
    if _mv(row, "carat"):
        ja_basic_lines.append(f'重さ：{_mv(row, "carat")}ct')
    if _mv(row, "size_mm"):
        ja_basic_lines.append(f'サイズ：{_mv(row, "size_mm")}')

    ja_condition_lines = []
    if treatment_ja:
        ja_condition_lines.append(f"処理：{treatment_ja}")
    if clarity_ja:
        ja_condition_lines.append(f"クラリティ：{clarity_ja}")
    if cert_lab_ja:
        ja_condition_lines.append(f"鑑別：{cert_lab_ja}")

    ja_cut_lines = []
    if design_jp:
        ja_cut_lines.append(f"ファセットデザイン：{design_jp}")
    if designer_ja:
        ja_cut_lines.append(f"デザイナー：{designer_ja}")
    if _mv(row, "modification_note"):
        ja_cut_lines.append(
            f'デザイン改変：{_mv(row, "modification_note")}'
        )
    if additional_note:
        ja_cut_lines.append(f"カット備考：{additional_note}")
    if faceted_by_ja:
        ja_cut_lines.append(f"研磨：{faceted_by_ja}")

    ja_product_lines = []
    if modification_ja:
        ja_cut_lines.append(f"デザイン改変：{modification_ja}")

    ja_groups = [
        ja_basic_lines,
        ja_condition_lines,
        ja_cut_lines,
        ja_product_lines,
    ]

    ja_lines = []
    for group in ja_groups:
        if not group:
            continue
        if ja_lines:
            ja_lines.append("　")
        ja_lines.extend(group)

    en_basic_lines = []
    if stone_en:
        en_basic_lines.append(f"Stone: {stone_en}")
    if origin_en:
        en_basic_lines.append(f"Origin: {origin_en}")
    if _mv(row, "carat"):
        en_basic_lines.append(f'Weight: {_mv(row, "carat")}ct')
    if _mv(row, "size_mm"):
        en_basic_lines.append(f'Size: {_mv(row, "size_mm")}')

    en_condition_lines = []
    if treatment_en:
        en_condition_lines.append(f"Treatment: {treatment_en}")
    if clarity_en:
        en_condition_lines.append(f"Clarity: {clarity_en}")
    if cert_lab_en:
        en_condition_lines.append(f"Certification: {cert_lab_en}")

    en_cut_lines = []
    if design_en:
        en_cut_lines.append(f"Design: {design_en}")
    if designer_en:
        en_cut_lines.append(f"Designer: {designer_en}")
    if modification_en:
        en_cut_lines.append(f"Modification: {modification_en}")

    if additional_note:
        en_cut_lines.append(f"Additional Note: {additional_note}")
    if faceted_by_en:
        en_cut_lines.append(f"Faceted by: {faceted_by_en}")

    en_product_lines = []
    if _mv(row, "product_id"):
        en_product_lines.append(f'Product ID: {_mv(row, "product_id")}')

    en_groups = [
        en_basic_lines,
        en_condition_lines,
        en_cut_lines,
        en_product_lines,
    ]

    en_lines = []
    for group in en_groups:
        if not group:
            continue
        if en_lines:
            en_lines.append("　")
        en_lines.extend(group)

    return {
        "ja": "\n".join(ja_lines),
        "en": "\n".join(en_lines),
    }

def build_square_seo_description(row: dict) -> str:
    title = resolve_title_jp(row)

    stone_ja = label(STONE_LABELS, _mv(row, "stone"), "ja")
    carat = _mv(row, "carat")

    origin_ja = label(ORIGIN_LABELS, _mv(row, "origin_en"), "ja")
    treatment_ja = label(TREATMENT_LABELS, _mv(row, "treatment"), "ja")

    parts = []

    if title:
        parts.append(title)
    elif stone_ja and carat:
        parts.append(f"{stone_ja} {carat}ct")

    if origin_ja:
        parts.append(f"産地：{origin_ja}")

    if treatment_ja:
        parts.append(f"処理：{treatment_ja}")

    parts.append("Rara Labが研磨した宝石ルースです。")

    text = "。".join(p.strip("。") for p in parts if p).strip()
    if text and not text.endswith("。"):
        text += "。"

    return text[:160]


def render_square_output(row: dict) -> dict:
    title_jp = resolve_title_jp(row)
    blocks = render_listing_blocks(row)

    gallery_url = _mv(row, "gallery_url")
    note_url = _mv(row, "note_url")

    intro_lines = []

    if gallery_url:
        intro_lines.append("公式サイトのギャラリーページはこちらです。")
        intro_lines.append(gallery_url)
        intro_lines.append("")

    if note_url:
        intro_lines.append("この石の制作過程をノートで公開中です。")
        intro_lines.append(note_url)
        intro_lines.append("")

    description = "\n".join([
        *intro_lines,
        blocks["ja"],
        "　",
        "☆☆☆☆☆☆",
        "　",
        blocks["en"],
    ]).strip()

    return {
        "title": title_jp,
        "description": description,
        "seo_description": build_square_seo_description(row),
    }

def render_master_outputs(rows, target: str) -> str:
    parts = []
    for idx, row in enumerate(rows, start=1):
        slug = _mv(row, "slug") or f"row-{idx}"
        if target in ("gallery", "all"):
            parts.append(f"### gallery:{slug}")
            parts.append(json.dumps(master_row_to_gallery_item(row), ensure_ascii=False, indent=2))
        if target in ("listing", "all"):
            blocks = render_listing_blocks(row)
            parts.append(f"### listing:{slug}:ja")
            parts.append(blocks["ja"])
            parts.append(f"### listing:{slug}:en")
            parts.append(blocks["en"])
        if target in ("square", "all"):
            square = render_square_output(row)
            parts.append(f"### square:{slug}:title")
            parts.append(square["title"])
            parts.append(f"### square:{slug}:description")
            parts.append(square["description"])
            parts.append(f"### square:{slug}:seo_description")
            parts.append(square["seo_description"])
    return "\n\n".join(part for part in parts if part.strip()) + ("\n" if parts else "")

def run_master_renderer(csv_path: Path, target: str, slug: str = "", out_dir: str = ""):
    rows = read_master_csv(csv_path)

    if slug:
        rows = [row for row in rows if _mv(row, "slug") == slug]
        if not rows:
            print(f"ERROR: slug not found: {slug}", file=sys.stderr)
            raise SystemExit(1)

    output = render_master_outputs(rows, target=target)

    if out_dir:
        out_path = Path(out_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        if slug:
            filename = f"{slug}_{target}.txt"
        else:
            filename = f"all_{target}.txt"

        dest = out_path / filename
        dest.write_text(output, encoding="utf-8")
        print(f"✅ output written: {dest}")
    else:
        sys.stdout.write(output)

def build_site_css():
    """
    assets/css/src/*.css を名前順に結合して assets/css/site.css を生成する。
    ※ assets/css/site.css は生成物扱い（人間は編集しない）
    """
    src_dir = ROOT / "assets" / "css" / "src"
    out_css = ROOT / "assets" / "css" / "site.css"

    if not src_dir.exists():
        print("[css] skip: assets/css/src not found")
        return

    parts = []
    for p in sorted(src_dir.glob("*.css")):
        parts.append(f"/* ---- {p.name} ---- */\n")
        parts.append(p.read_text(encoding="utf-8", errors="ignore").rstrip() + "\n\n")

    out_css.write_text("".join(parts), encoding="utf-8")
    print(f"[css] generated: {out_css.relative_to(ROOT)}")


# ---- Build ----
def build():
    # 先に CSS を生成してから assets をコピーする（生成物を site 側に反映させるため）
    build_site_css()

    # サムネ & ニュース画像の WebP を事前に揃えておく
    ensure_webp_thumbs()
    ensure_webp_large()
    ensure_webp_news_images()

    # 公開用 assets を site/assets にコピー
    src_assets = ROOT / "assets"
    dst_assets = SITE_ROOT / "assets"

    if dst_assets.exists():
        for p in dst_assets.rglob(".DS_Store"):
            try:
                p.unlink()
            except Exception:
                pass

    if dst_assets.exists():
        shutil.rmtree(dst_assets, ignore_errors=True)

    if src_assets.exists():
        shutil.copytree(src_assets, dst_assets, dirs_exist_ok=True)

    # ニュース画像を site/news/images に集約コピー
    src_news_images = NEWS_IMAGES_DIR
    dst_news_images = SITE_ROOT / "news" / "images"
    if dst_news_images.exists():
        shutil.rmtree(dst_news_images)
    if src_news_images.exists():
        dst_news_images.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src_news_images, dst_news_images)

    items = read_items()  # date 降順（新しい順）でソート済み

    # ---- ギャラリー一覧（ページ分割）----
    pages = [items[i:i + PAGE_SIZE] for i in range(0, len(items), PAGE_SIZE)]
    page_count = len(pages)

    for idx, page_items in enumerate(pages):
        page_num = idx + 1

        cards = "\n".join(render_gallery_card(it) for it in page_items)

        if page_num == 1:
            out_path = OUT_GALLERY / "index.html"
        else:
            out_path = OUT_GALLERY / f"page-{page_num}.html"

        prev_link = None
        next_link = None

        if page_num > 1:
            prev_link = "/gallery/" if page_num == 2 else f"/gallery/page-{page_num-1}.html"

        if page_num < page_count:
            next_link = f"/gallery/page-{page_num+1}.html"

        # canonical（絶対URL）をページごとに作る
        if page_num == 1:
            canonical = f"{SITE_ORIGIN}/gallery/"
        else:
            canonical = f"{SITE_ORIGIN}/gallery/page-{page_num}.html"

        out_path.write_text(
            inject_footer(gallery_index_html(cards, prev_link=prev_link, next_link=next_link, canonical=canonical)),
            encoding="utf-8"
        )

    # ---- 各詳細ページ ----
    for it in items:
        d = OUT_GALLERY / it["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(inject_footer(detail_html(it)), encoding="utf-8")

    # ---- News ----
    news_items = read_news_items()

    # ---- News一覧（ページ分割）----
    if news_items:
        pages = [news_items[i:i + PAGE_SIZE] for i in range(0, len(news_items), PAGE_SIZE)]
        page_count = len(pages)

        for idx, page_items in enumerate(pages):
            page_num = idx + 1

            cards = "\n".join(render_news_index_card(n) for n in page_items)

            if page_num == 1:
                out_path = OUT_NEWS / "index.html"
            else:
                out_path = OUT_NEWS / f"page-{page_num}.html"

            prev_link = None
            next_link = None

            if page_num > 1:
                prev_link = "/news/" if page_num == 2 else f"/news/page-{page_num-1}.html"

            if page_num < page_count:
                next_link = f"/news/page-{page_num+1}.html"

            # canonical（絶対URL）をページごとに作る
            if page_num == 1:
                canonical = f"{SITE_ORIGIN}/news/"
            else:
                canonical = f"{SITE_ORIGIN}/news/page-{page_num}.html"

            out_path.write_text(
                inject_footer(news_index_html(cards, prev_link=prev_link, next_link=next_link, canonical=canonical)),
                encoding="utf-8"
            )
    else:
        (OUT_NEWS / "index.html").write_text(
            inject_footer(news_index_html("", canonical=f"{SITE_ORIGIN}/news/")),
            encoding="utf-8"
        )

    # ---- Top (Gallery new + News latest) ----
    TOP_GALLERY_COUNT = 6
    TOP_NEWS_COUNT = 3

    new_cards = "\n".join(render_gallery_card(it) for it in items[:TOP_GALLERY_COUNT])

    top_news_cards_html = ""
    if news_items:
        top_news_cards_html = "\n".join(
            top_news_card_html(n) for n in news_items[:TOP_NEWS_COUNT]
        )

    (SITE_ROOT / "index.html").write_text(
        inject_footer(top_index_html(new_cards, top_news_cards_html)),
        encoding="utf-8"
    )

    # ---- News detail pages (/news/<slug>/index.html) ----
    for n in news_items:
        slug = (n.get("slug") or "").strip()
        if not slug:
            continue

        body_path = NEWS_BODY_DIR / f"{slug}.html"
        if body_path.exists():
            body_html = body_path.read_text(encoding="utf-8")
        else:
            print(f"[warn] 本文が見つかりません: {body_path}")
            body_html = "<p>(本文が見つかりません)</p>"

        html_text = inject_footer(news_detail_html(n, body_html))
        out_dir = OUT_NEWS / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(html_text, encoding="utf-8")

    # ---- Gemdiary detail pages (/gemdiary/<slug>/index.html) ----
    # assets/gemdiary/body/<slug>.html を本文として使用
    if GEMDIARY_BODY_DIR.exists():
        for body_path in sorted(GEMDIARY_BODY_DIR.glob("*.html")):
            slug = body_path.stem.strip()
            if not slug or slug == "index":
                continue

            # raw の meta を読む（無ければ最低限で）
            raw_index = GEMDIARY_RAW_DIR / slug / "index.html"
            meta = {"slug": slug}
            if raw_index.exists():
                meta.update(extract_gemdiary_meta(raw_index))

            body_html = body_path.read_text(encoding="utf-8")

            html_text = inject_footer(gemdiary_detail_html(meta, body_html))
            out_dir = OUT_GEMDIARY / slug
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "index.html").write_text(html_text, encoding="utf-8")
    else:
        print("[gemdiary] skip: assets/gemdiary/body not found")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["gallery", "listing", "square", "all"], default="gallery")
    ap.add_argument("--master-csv", default="")
    ap.add_argument("--slug", default="")
    ap.add_argument("--out-dir", default="")
    args = ap.parse_args()

    if args.master_csv:
        run_master_renderer(
            Path(args.master_csv),
            target=args.target,
            slug=args.slug,
            out_dir=args.out_dir,
        )
    else:
        build()
        print("✅ build complete: gallery, news, details, and top index generated.")