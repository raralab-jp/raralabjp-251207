#!/usr/bin/env python3
import json, html, re, csv
from pathlib import Path

# ---- WebP 変換用ライブラリ (Pillow) の読み込み ----
try:
    from PIL import Image
except ImportError:
    Image = None

# ---- Paths / Policy ----
ROOT = Path(__file__).parent.resolve()
DATA = ROOT / "assets" / "data" / "items.json"
OUT_GALLERY = ROOT / "gallery"
OUT_GALLERY.mkdir(parents=True, exist_ok=True)
PAGE_SIZE = 24

NEWS_CSV      = ROOT / "data" / "news.csv"
NEWS_BODY_DIR = ROOT / "data" / "news_body"
OUT_NEWS      = ROOT / "news"
OUT_NEWS.mkdir(parents=True, exist_ok=True)

TOP_HERO     = ROOT / "assets" / "partials" / "top_hero.html"
TOP_SECTIONS = ROOT / "assets" / "partials" / "top_sections.html"

def read_file(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""

def read_top_hero() -> str:
    return read_file(TOP_HERO)

def read_top_sections() -> str:
    return read_file(TOP_SECTIONS)

def ensure_webp_thumbs():
    """
    assets/images/thumb/ 以下の JPG/PNG から、同名の .webp を自動生成する。
    ・すでに .webp がある場合は何もしない
    ・Pillow が無い場合も何もしない
    """
    if Image is None:
        # Pillow 未インストールの場合はスキップ
        return

    thumb_dir = ROOT / "assets" / "images" / "thumb"
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
            continue  # もう作ってある

        try:
            img = Image.open(p)
            # 必要なら quality は好みで調整（80〜90くらいが無難）
            img.save(webp_path, format="WEBP", quality=85)
            print(f"[webp] generated: {webp_path.name}")
        except Exception as e:
            print(f"[webp] failed to convert {p.name}: {e}")

def ensure_webp_news_images():
    """
    news/images 以下の JPG/PNG から、同名の .webp を自動生成する。
    ・すでに .webp がある場合は何もしない
    ・Pillow が無い場合も何もしない
    """
    if Image is None:
        return

    news_dir = ROOT / "news" / "images"
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
            continue  # すでに作ってある

        try:
            img = Image.open(p)
            img.save(webp_path, format="WEBP", quality=85)
            print(f"[webp-news] generated: {webp_path.name}")
        except Exception as e:
            print(f"[webp-news] failed to convert {p.name}: {e}")


# 表示ポリシー
SHOW_BREADCRUMB = False
SHOW_SPECS      = True   # Stone / Carat / Design の3点のみ表示

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
    data/news.csv を読み込んで、日付降順に並べた dict のリストを返す。
    カラム: slug,date,title,summary,body_file,image_file
    """
    items = []
    if not NEWS_CSV.exists():
        return items

    with NEWS_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 軽くトリム
            row["slug"]       = (row.get("slug") or "").strip()
            row["date"]       = (row.get("date") or "").strip()
            row["title"]      = (row.get("title") or "").strip()
            row["summary"]    = (row.get("summary") or "").strip()
            row["body_file"]  = (row.get("body_file") or "").strip()
            row["image_file"] = (row.get("image_file") or "").strip()

            if row["slug"]:
                items.append(row)

    # 日付降順（新しい順）
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

    # "news/images/xxx.jpg" / "/news/images/xxx.jpg" / "xxx.jpg" どれでも受ける
    if "/" in image_file:
        rel = image_file.lstrip("/")  # 例: "news/images/DSC_1777.jpg"
    else:
        rel = f"news/images/{image_file}"  # CSV がファイル名だけの場合

    p = ROOT / rel

    # もともと .webp 指定ならそのまま返す
    if p.suffix.lower() == ".webp":
        if p.exists():
            return "/" + rel
        return "/" + rel  # まだファイルを置いてないだけのケース

    folder = p.parent
    stem   = p.stem

    # 同じフォルダに .webp があれば優先
    webp_path = folder / (stem + ".webp")
    if webp_path.exists():
        rel_webp = str(webp_path.relative_to(ROOT)).replace("\\", "/")
        return "/" + rel_webp

    # なければ元の拡張子を使う
    if p.exists():
        rel_orig = str(p.relative_to(ROOT)).replace("\\", "/")
        return "/" + rel_orig

    # まだ画像をコピーしていない等のケースでも、とりあえず組み立てたパスを返す
    return "/" + rel

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
        url     = f"/news/{slug}.html" if slug else "#"

        # summary が空なら <p> ごと出さないようにする
        summary_html = f'\n            <p class="news-summary">{summary}</p>' if summary else ""

        lis.append(
f'''          <li class="news-item">
            <span class="news-date">{date}</span>
            <a class="news-title" href="{url}">{title}</a>{summary_html}
          </li>'''
        )
    return "\n".join(lis)

def news_card_html(n: dict) -> str:
    """
    ニュース一覧用：ギャラリーと同じカード構造（rl-item / rl-link / rl-caption）
    画像サムネ＋タイトル＋日付＋要約を表示する。
    """
    slug    = (n.get("slug") or "").strip()
    date    = (n.get("date") or "").strip()
    title   = (n.get("title") or "").strip()
    summary = (n.get("summary") or "").strip()
    image   = (n.get("image_file") or "").strip()

    # 詳細ページURL
    url = f"/news/{slug}.html" if slug else "#"

    # 表示テキスト
    title_text   = title or slug
    title_html   = html.escape(title_text)
    date_html    = html.escape(date)
    summary_html = html.escape(summary)

    # 画像パス（WebP優先・ファイル名だけでもOK）
    img_src = resolve_news_image_src(image) if image else ""

    img_tag = ""
    if img_src:
        img_tag = (
            f'<img src="{img_src}" alt="{title_html}" '
            f'loading="lazy" decoding="async">'
        )

    # 要約は空なら出さない
    summary_block = f'\n      <p class="news-summary">{summary_html}</p>' if summary_html else ""

    return f'''<figure class="rl-item">
  <a href="{url}" class="rl-link">
    {img_tag}
    <figcaption class="rl-caption">
      <span class="rl-title">{title_html}</span>
      <span class="news-date">{date_html}</span>{summary_block}
    </figcaption>
  </a>
</figure>'''

def news_index_html(cards: str, prev_link: str = None, next_link: str = None) -> str:
    """
    ニュース一覧ページ全体のHTML。
    ギャラリーと同じ .gallery-head / .rl-gallery / .gallery-pager を使う。
    """
    # ページャーHTML（ギャラリーと同じクラス名）
    pager_parts = []
    if prev_link or next_link:
        pager_parts.append('<nav class="gallery-pager">')
        # 前のページ
        if prev_link:
            pager_parts.append(f'<a class="pager-prev" href="{prev_link}">前のページ</a>')
        else:
            pager_parts.append('<span class="pager-prev"></span>')
        # 次のページ
        if next_link:
            pager_parts.append(f'<a class="pager-next" href="{next_link}">次のページ</a>')
        else:
            pager_parts.append('<span class="pager-next"></span>')
        pager_parts.append('</nav>')

    pager_html = "\n".join(pager_parts)

    intro_html = read_intro()

    return f'''<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>News | Rara Lab</title>
<link rel="stylesheet" href="/assets/css/site.css">
<body>
{intro_html}
<main class="news-index">

  <section class="gallery-head">
    <h1>News</h1>
    <p class="gallery-note">
      Rara Lab からのお知らせをまとめています。
    </p>
  </section>

  <section class="rl-gallery news-gallery">
{cards}
  </section>

{pager_html}

</main>
</body>
'''

def news_detail_html(news: dict, body_html: str) -> str:
    """
    個別NewsページのフルHTMLを返す。
    body_html は data/news_body/... に書いた本文スニペット。
    ※ ギャラリー個別ページの構造に寄せて、
       「画像ブロック（news-hero）」と「本文ブロック（news-body）」に分割する。
    """
    intro_html = read_intro()  # 上部の共通リンクなど
    date  = html.escape(news.get("date") or "")
    title = html.escape(news.get("title") or "")

    # 画像ブロック（image_file から WebP 優先でパスを決定）
    hero_block = ""
    image_file = (news.get("image_file") or "").strip()
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

    # body_html 内の </h1> の直後に日付を差し込む
    if "</h1>" in body_html:
        body_with_date = re.sub(
            r"</h1>",
            '</h1>\n<p class="news-date">' + date + "</p>",
            body_html,
            count=1,
        )
    else:
        # 念のため <h1> が無い場合は本文の先頭に日付を置く
        body_with_date = f'<p class="news-date">{date}</p>\n{body_html}'

    # 本文ブロック（タイトル〜本文〜戻るリンクをまとめる）
    body_block = f'''
      <section class="news-body">
        {body_with_date}
        <p class="news-back"><a href="/news/">News 一覧へ戻る</a></p>
      </section>'''

    return f'''<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} | Rara Lab</title>
<link rel="stylesheet" href="/assets/css/site.css">
<body>
  {intro_html}
  <main class="news-detail">
    <article>
{hero_block}{body_block}
    </article>
  </main>
</body>'''

# ---- Image helpers ----
def image_suffixes(slug: str, kind: str):
    """
    対応パターン:
      slug-cover.jpg / .webp
      slug-DSC_4975.jpg, slug-DSC4975.jpg, slug-IMG_1234.JPG など
      旧: slug.jpg / slug.webp
    """
    folder = ROOT / "assets" / "images" / kind
    if not folder.exists():
        return []

    # プレフィックス許容（Nikon等のアンダースコアに対応）
    prefixes = [slug, slug.replace("-", "_")]

    # 受け入れる拡張子
    exts = (".webp", ".jpg", ".jpeg", ".png", ".WEBP", ".JPG", ".JPEG", ".PNG")

    found = []
    for p in folder.iterdir():
        if not p.is_file():
            continue
        name = p.name
        low  = name.lower()
        if not low.endswith(tuple(e.lower() for e in exts)):
            continue
        # prefix マッチ
        if any(low.startswith(pref.lower()+"-") or low == (pref.lower()+low[ len(pref): ]) for pref in prefixes):
            # suffix を抽出（slug-XXXX.ext → XXXX）
            # ハイフン区切り：slug-xxxx.ext
            for pref in prefixes:
                if name.startswith(pref + "-"):
                    suf = name[len(pref)+1:name.rfind(".")]
                    found.append(suf)
                    break
            else:
                # 旧: suffix なし（slug.jpg）
                if name.lower().startswith(slug.lower()+".") or name.lower().startswith(slug.replace("-", "_").lower()+"."):
                    found.append("")  # suffix なし
    if not found:
        return []
    # cover を先頭、それ以外は辞書順
    found = sorted(found, key=lambda s: (s.lower() != "cover", s.lower()))
    # 重複除去（順序保持）
    seen, uniq = set(), []
    for s in found:
        if s not in seen:
            seen.add(s); uniq.append(s)
    return uniq

def img_path(slug: str, folder: str, suf: str) -> str:
    # folder: "thumb" or "4k"
    base = f"/assets/images/{folder}"
    return f"{base}/{slug}{suf}"

def primary_images(slug: str):
    """一覧カード用thumbと、詳細での最初の4Kを返す（拡張子付き絶対パス）"""
    exts = (".webp", ".jpg", ".jpeg", ".png", ".WEBP", ".JPG", ".JPEG", ".PNG")
    base_names = [
        f"{slug}-cover",
        f"{slug.replace('-', '_')}-cover",
        slug,
        slug.replace("-", "_"),
    ]
    thumb_dir = ROOT / "assets" / "images" / "thumb"
    fourk_dir = ROOT / "assets" / "images" / "4k"

    thumb = None
    fourk = None

    # thumb 探索
    for base in base_names:
        for ext in exts:
            p = thumb_dir / f"{base}{ext}"
            if p.exists():
                thumb = f"/assets/images/thumb/{p.name}"
                break
        if thumb:
            break

    # 4K 探索
    for base in base_names:
        for ext in exts:
            p = fourk_dir / f"{base}{ext}"
            if p.exists():
                fourk = f"/assets/images/4k/{p.name}"
                break
        if fourk:
            break

    return thumb, fourk

from pathlib import Path

def thumb_to_4k(thumb_path: str) -> str:
    """
    サムネのパス (/assets/images/thumb/xxx.ext) から、
    実際に存在する 4K 画像 (/assets/images/4k/xxx.*) を探して返す。
    なければ拡張子そのままで /4k/ に置き換えたものを返す（後方互換用）。
    """
    name = Path(thumb_path).name       # seafoam-....-DSC_9991.webp
    stem = Path(name).stem             # seafoam-....-DSC_9991

    fourk_dir = ROOT / "assets" / "images" / "4k"
    exts = (".webp", ".jpg", ".jpeg", ".png", ".WEBP", ".JPG", ".JPEG", ".PNG")

    for ext in exts:
        candidate = fourk_dir / f"{stem}{ext}"
        if candidate.exists():
            return f"/assets/images/4k/{candidate.name}"

    # 4K 側に対応ファイルがない場合の保険
    return thumb_path.replace("/thumb/", "/4k/")

def all_images(slug: str, image_order: str = ""):
    """
    サムネ用フォルダから slug で始まるファイルを列挙する。
    WebP と JPG/PNG が重複している場合、WebP を優先して採用し、JPG/PNG は除外する。
    """
    thumb_dir = ROOT / "assets" / "images" / "thumb"
    if not thumb_dir.exists():
        return []

    # slug と slug のアンダースコア版の両方に対応
    want_prefixes = [slug, slug.replace("-", "_")]
    exts = (".webp", ".jpg", ".jpeg", ".png", ".WEBP", ".JPG", ".JPEG", ".PNG")

    # 1. 候補ファイルをすべて収集
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
        path = f"/assets/images/thumb/{name}"
        candidates.append((name, path, is_cover))

    if not candidates:
        return []

    # 2. 重複除外処理 (WebP優先)
    # ファイル名（拡張子なし）をキーにしてグループ化する
    grouped = {}
    for name, path, is_cover in candidates:
        stem = Path(name).stem  # 拡張子を除いた名前 (例: stone-01)
        if stem not in grouped:
            grouped[stem] = []
        grouped[stem].append((name, path, is_cover))

    unique_candidates = []
    for stem, group in grouped.items():
        # グループ内に .webp があればそれを探す
        selected = None
        for item in group:
            if item[0].lower().endswith(".webp"):
                selected = item
                break
        
        # WebPがなければ最初のもの(JPG等)を採用
        if not selected:
            selected = group[0]
        
        unique_candidates.append(selected)

    # 3. ソート処理（cover優先 ＋ image_order 対応）
    covers  = [path for (name, path, is_cover) in unique_candidates if is_cover]
    normals = [(name, path) for (name, path, is_cover) in unique_candidates if not is_cover]

    def extract_id(name: str) -> str:
        base = Path(name).stem # 拡張子を除く
        # prefix除去
        for pref in [slug, slug.replace("-", "_")]:
            if base.startswith(pref):
                suf = base[len(pref):]
                return suf.lstrip("-_")
        return base

    normals_with_id = [(extract_id(name), path) for (name, path) in normals]

    order_ids = []
    if image_order:
        import re as _re
        for token in _re.split(r"[,\s]+", image_order):
            t = token.strip()
            if t:
                order_ids.append(t)

    ordered_normals = []
    used = set()

    # 指定順序に追加
    for oid in order_ids:
        for nid, path in normals_with_id:
            if nid == oid and path not in used:
                ordered_normals.append(path)
                used.add(path)

    # 残りをファイル名順に追加
    remaining = [path for (nid, path) in normals_with_id if path not in used]
    remaining.sort()
    ordered_normals.extend(remaining)

    covers_sorted = sorted(covers)
    paths = covers_sorted + ordered_normals

    # primary_thumb（-cover）を最優先にする
    primary_thumb, _ = primary_images(slug)
    if primary_thumb and primary_thumb in paths:
        paths.remove(primary_thumb)
        paths.insert(0, primary_thumb)

    return paths

    want_prefixes = [slug.lower(), slug.lower().replace("-", "_")]
    exts = (".webp", ".jpg", ".jpeg", ".png", ".WEBP", ".JPG", ".JPEG", ".PNG")

    found = []
    for p in thumb_dir.iterdir():
        if not p.is_file():
            continue
        name = p.name
        low = name.lower()
        if low.endswith(exts) and any(low.startswith(pref) for pref in want_prefixes):
            # 生成物からの参照は常にルート起点
            found.append(f"/assets/images/thumb/{name}")

    # primary を先頭に（重複は除く）
    primary_thumb, _ = primary_images(slug)
    if primary_thumb and primary_thumb in found:
        found.remove(primary_thumb)
        found.insert(0, primary_thumb)

    return found

def card_html(it):
    """ギャラリー／トップ用の一覧カード（画像＋日本語タイトル1本）"""
    slug = it["slug"]

    # 日本語タイトル（なければ従来の stone/carat/design から組み立て）
    title_jp = it.get("title_jp", "").strip()
    if not title_jp:
        stone  = it.get("stone", "").strip()
        carat  = it.get("carat", "").strip()
        design = it.get("design_name", "").strip()

        primary = f"{stone} – {carat}ct" if stone and carat else (stone or slug)
        secondary = f" “{design}”" if design else ""
        title_jp = (primary + secondary).strip()

    # サムネイル（primary_images は slug-cover を最優先で探す）
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

def gallery_index_html(cards: str, prev_link: str = None, next_link: str = None) -> str:
    # ページャーHTML
    pager_parts = []
    if prev_link or next_link:
        pager_parts.append('<nav class="gallery-pager">')
        # 前のページ
        if prev_link:
            pager_parts.append(f'<a class="pager-prev" href="{prev_link}">前のページ</a>')
        else:
            pager_parts.append('<span></span>')
        # 次のページ
        if next_link:
            pager_parts.append(f'<a class="pager-next" href="{next_link}">次のページ</a>')
        pager_parts.append('</nav>')

    pager_html = "\n".join(pager_parts)

    return f'''<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gallery – Rara Lab</title>
<link rel="stylesheet" href="/assets/css/site.css">

<section class="gallery-head">
  <h1>Gallery</h1>
  <p class="gallery-note">
    このギャラリーには、現在は販売を終了している作品も含まれています。
    販売状況はショップの商品ページでご確認ください。
  </p>
</section>

<section class="rl-gallery">
{cards}
</section>

{pager_html}
'''

def top_index_html(new_cards: str, news_list_html: str) -> str:
    intro_html = read_intro() if 'read_intro' in globals() else ""
    hero_html  = read_top_hero() if 'read_top_hero' in globals() else ""

    return f'''<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rara Lab</title>
<link rel="stylesheet" href="/assets/css/site.css">
<body>
  {intro_html}
  {hero_html}
  <main class="top">

    <!-- ① 新着ギャラリー -->
    <section class="top-section top-gallery">
      <h2 class="section-doubleline">New</h2>
      <section class="rl-gallery">
{new_cards}
      </section>
    </section>

    <!-- ② News -->
    <section class="top-section top-news">
      <h2 class="section-doubleline">News</h2>
      <div class="news-list">
        <ul>
{news_list_html}
        </ul>
      </div>
      <div class="news-more">
        <a href="/news/">News 一覧を見る</a>
      </div>
    </section>

    <!-- ③ Note / GemDiary / About -->
    <section class="top-section top-links">
      <h2 class="section-doubleline">More</h2>
      <div class="home-link-list">
        <article class="home-link-card">
          <h3 class="home-link-title">
            <a href="https://note.com/raralab" target="_blank" rel="noopener">
              Note
            </a>
          </h3>
          <p class="home-link-text">
            制作記録やコラムなど、ゆるい読みものはこちら。
          </p>
        </article>

        <article class="home-link-card">
          <h3 class="home-link-title">
            <a href="/gemdiary/">
              Gem Diary（アーカイブ）
            </a>
          </h3>
          <p class="home-link-text">
            旧サイト時代の Gem Diary 記事をまとめています。
          </p>
        </article>

        <article class="home-link-card">
          <h3 class="home-link-title">
            <a href="/about/">
              About
            </a>
          </h3>
          <p class="home-link-text">
            Rara Lab と運営者について。
          </p>
        </article>
      </div>
    </section>

  </main>
</body>'''

def detail_html(it):
    slug   = it["slug"]
    stone  = it.get("stone","")
    carat  = it.get("carat","")
    design = it.get("design_name","")

    title    = f'{stone} – {carat}ct' if stone and carat else (stone or slug)
    subtitle = f'“{design}”' if design else ''

    breadcrumb = '' if not SHOW_BREADCRUMB else '<nav class="breadcrumb"><a href="/gallery/">← Back to Gallery</a></nav>'

    # ---- 画像 ----
    hero_thumb, hero_4k = primary_images(slug)
    image_order = it.get("image_order", "")
    thumbs = all_images(slug, image_order=image_order)

    hero_img  = hero_4k or hero_thumb or ""
    hero_href = hero_4k or hero_thumb or ""

    hero_html = ""
    if hero_img:
        hero_html = f'''
        <a href="#" class="hero-link" data-full="{hero_href}">
          <img class="hero" src="{hero_img}" alt="{html.escape(title)}">
        </a>'''.strip()

    # ---- 動画ブロック ----
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

# ---- サムネ一覧 ----
    thumbs_html = ""
    if thumbs:
        items = []
        for t in thumbs:
            f4k = thumb_to_4k(t)  # ← ここだけ変更
            active = "active" if (t == hero_thumb) else ""
            img_class_attr = f' class="{active}"' if active else ""
            
            items.append(
                f'<a class="thumb" href="#" data-full="{f4k}">'
                f'<img src="{t}"{img_class_attr} alt="{html.escape(title)}" loading="lazy" decoding="async"></a>'
            )
            
        thumbs_html = '<div class="thumbs">\n' + "\n".join(items) + "\n</div>"

    # ---- プレート＋CTA ----
    plate_html = ""
    cta_html   = ""

    if SHOW_SPECS:
        title_jp  = it.get("title_jp", "").strip()
        stone_en  = it.get("stone", "").strip()
        carat     = it.get("carat", "")
        design_en = it.get("design_name", "").strip()
        faceter   = it.get("faceted_by", "").strip()
        origin_en = it.get("origin_en", "").strip()
        product_url = (it.get("product_url") or "").strip() or "#"

        # プレート
        plate_lines = []
        if title_jp:
            plate_lines.append(f'  <p class="jp">{html.escape(title_jp)}</p>')

        block_b = []
        if stone_en and carat:
            block_b.append(f'  <p class="en">{html.escape(stone_en)} {html.escape(str(carat))}ct</p>')
        elif stone_en:
            block_b.append(f'  <p class="en">{html.escape(stone_en)}</p>')

        if design_en:
            block_b.append(f'  <p class="en">Design: “{html.escape(design_en)}”</p>')

        block_c = []
        if faceter:
            block_c.append(f'  <p class="meta">Faceted by {html.escape(faceter)}</p>')
        if origin_en:
            block_c.append(f'  <p class="meta">Origin: {html.escape(origin_en)}</p>')

        final_lines = []
        if plate_lines:
            final_lines.extend(plate_lines)
        if block_b:
            final_lines.extend(block_b)
        if block_c:
            final_lines.extend(block_c)

        if final_lines:
            plate_html = '<section class="plate">\n' + "\n".join(final_lines) + "\n</section>"

        # CTA
        if product_url:
            cta_html = f'''<section class="cta-block">
  <a href="{html.escape(product_url)}" class="cta-link">ご購入はこちら →</a>
</section>'''

    # ---- 出力 ----
    return f'''<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} – Rara Lab</title>
<link rel="stylesheet" href="/assets/css/site.css">
<main class="detail">
  {breadcrumb}
  <h1 class="title">{html.escape(title)}</h1>
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
'''

# ---- Build ----
def build():
    # サムネ & ニュース画像の WebP を事前に揃えておく
    ensure_webp_thumbs()
    ensure_webp_news_images()

    items = read_items()  # date 降順（新しい順）でソート済み


    # ---- ギャラリー一覧（ページ分割）----
    pages = []
    for i in range(0, len(items), PAGE_SIZE):
        pages.append(items[i:i + PAGE_SIZE])

    page_count = len(pages)

    for idx, page_items in enumerate(pages):
        page_num = idx + 1

        # カードHTML
        cards = "\n".join([card_html(it) for it in page_items])

        # 出力パス
        if page_num == 1:
            out_path = OUT_GALLERY / "index.html"
        else:
            out_path = OUT_GALLERY / f"page-{page_num}.html"

        # 前後ページリンク
        prev_link = None
        next_link = None

        if page_num > 1:
            if page_num == 2:
                prev_link = "/gallery/"
            else:
                prev_link = f"/gallery/page-{page_num-1}.html"

        if page_num < page_count:
            next_link = f"/gallery/page-{page_num+1}.html"

        out_path.write_text(
            gallery_index_html(cards, prev_link=prev_link, next_link=next_link),
            encoding="utf-8"
        )

    # ---- 各詳細ページ ----
    for it in items:
        d = OUT_GALLERY / it["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(detail_html(it), encoding="utf-8")

    # ---- News 251204----
news_items = read_news_items()

# ニュース一覧 /news/index.html ＋ /news/page-2.html ... （ギャラリーと同じノリで分割）
if news_items:
    pages = []
    for i in range(0, len(news_items), PAGE_SIZE):  # PAGE_SIZE はギャラリーと共通の想定
        pages.append(news_items[i:i + PAGE_SIZE])

    page_count = len(pages)

    for idx, page_items in enumerate(pages):
        page_num = idx + 1

        # カードHTML（ギャラリーと同じ .rl-item 構造）
        cards = "\n".join([news_card_html(n) for n in page_items])

        # 出力パス
        if page_num == 1:
            out_path = OUT_NEWS / "index.html"
        else:
            out_path = OUT_NEWS / f"page-{page_num}.html"

        # 前後ページリンク
        prev_link = None
        next_link = None

        if page_num > 1:
            if page_num == 2:
                prev_link = "/news/"
            else:
                prev_link = f"/news/page-{page_num-1}.html"

        if page_num < page_count:
            next_link = f"/news/page-{page_num+1}.html"

        out_path.write_text(
            news_index_html(cards, prev_link=prev_link, next_link=next_link),
            encoding="utf-8"
        )

        # 個別ページ /news/[slug].html
        for n in news_items:
            slug = n["slug"]

            # -------- 本文ファイルを読み込む --------
            body_file = (n.get("body_file") or "").strip()
            if body_file:
                body_path = ROOT / body_file
                if body_path.exists():
                    body_html = body_path.read_text(encoding="utf-8")
                else:
                    print(f"[warn] 本文が見つかりません: {body_path}")
                    body_html = "<p>(本文が見つかりません)</p>"
            else:
                print(f"[warn] body_file が空です: slug={slug}")
                body_html = "<p>(本文が見つかりません)</p>"

            # -------- HTML生成（画像＋日付移動を含む）--------
            html_text = news_detail_html(n, body_html)

            # -------- 出力 --------
            (OUT_NEWS / f"{slug}.html").write_text(html_text, encoding="utf-8")

    # ---- トップ（新着12件＋最新ニュース数件）----
    items = read_items()
    newest = items[:12]
    new_cards = "\n".join([card_html(it) for it in newest])

    if news_items:
        top_news_list = render_news_list_items(news_items, limit=3)
    else:
        top_news_list = ""  # ニュースがない場合は空のまま

    (ROOT / "index.html").write_text(
        top_index_html(new_cards, top_news_list),
        encoding="utf-8"
    )

if __name__ == "__main__":
    build()
    print("✅ build complete: gallery, details, and top index generated.")