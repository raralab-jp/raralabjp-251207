#!/usr/bin/env python3
import json, html, re, csv
from pathlib import Path
import shutil  # ← ここを追加

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

# ギャラリー・ニュースは site/ 以下に出力
OUT_GALLERY = SITE_ROOT / "gallery"
OUT_GALLERY.mkdir(parents=True, exist_ok=True)
PAGE_SIZE = 24

NEWS_CSV       = ROOT / "assets" / "news" / "news.csv"
NEWS_BODY_DIR  = ROOT / "assets" / "news" / "body"
NEWS_IMAGES_DIR = ROOT / "assets" / "news" / "images"

OUT_NEWS       = SITE_ROOT / "news"
OUT_NEWS.mkdir(parents=True, exist_ok=True)

TOP_HERO     = ROOT / "assets" / "partials" / "top_hero.html"
TOP_SECTIONS = ROOT / "assets" / "partials" / "top_sections.html"

PARTIALS_DIR = ROOT / "assets" / "partials"

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

def ensure_webp_large():
    """
    assets/images/4k/ 以下の JPG/PNG から、site/assets/images/large/ に表示用 WebP を生成する。
    - 差分ビルド（mtimeで新しいものだけ）
    - 長辺 max_long_edge に収める
    """
    if Image is None:
        return

    src_dir = ROOT / "assets" / "images" / "4k"
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

    if image_file.upper() in {"NO_IMAGE", "NONE", "N/A", "-"}:
        return ""

    # "news/images/xxx.jpg" / "/news/images/xxx.jpg" / "xxx.jpg" どれでも受ける
    if "/" in image_file:
        rel = image_file.lstrip("/")  # "news/images/DSC_1777.jpg"
    else:
        rel = f"news/images/{image_file}"

    # 実ファイルは site/ の下にある前提
    p = SITE_ROOT / rel

    # もともと .webp 指定ならそのまま
    if p.suffix.lower() == ".webp":
        return "/" + rel

    folder = p.parent
    stem   = p.stem

    webp_path = folder / (stem + ".webp")
    if webp_path.exists():
        # URL は /news/images/... 形式で返す
        rel_webp = f"news/images/{webp_path.name}"
        return "/" + rel_webp

    if p.exists():
        rel_orig = f"news/images/{p.name}"
        return "/" + rel_orig

    # まだ実ファイルが無くても URL だけは返しておく
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

    # 詳細ページURL
    url = f"/news/{slug}/" if slug else "#"

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

    title_html = html.escape(title or slug)
    date_html  = html.escape(date)
    summary_html = html.escape(summary)

    img_src = resolve_news_image_src(image) if image else ""

    if img_src:
        thumb_html = f'<img src="{img_src}" alt="{title_html}" loading="lazy" decoding="async">'
        thumb_class = "news-card-thumb"
    else:
        thumb_html = ""
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

def news_index_html(cards: str, prev_link: str = None, next_link: str = None) -> str:
    """
    ニュース一覧ページ全体のHTML。
    ヘッダーは「ロゴ → メニュー」を共通で表示する。
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

    # 共通ヘッダー
    logo_html = render_partial("top_logo.html")
    nav_html  = render_partial("nav_main.html")

    return f'''<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>News | Rara Lab</title>
<link rel="stylesheet" href="/assets/css/site.css">
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
'''

def news_detail_html(news: dict, body_html: str) -> str:
    """
    個別NewsページのフルHTMLを返す。
    body_html は data/news_body/... に書いた本文スニペット。
    ※ ギャラリー個別ページの構造に寄せて、
       「画像ブロック（news-hero）」と「本文ブロック（news-body）」に分割する。
    """
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

    # 共通ヘッダー
    logo_html = render_partial("top_logo.html")
    nav_html  = render_partial("nav_main.html")

    return f'''<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} | Rara Lab</title>
<link rel="stylesheet" href="/assets/css/site.css">
<body>
{logo_html}
{nav_html}
  <main class="detail news-detail">
    <article>
{hero_block}{body_block}
    </article>
  </main>
</body>'''

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

def path_to_large(src_path: str) -> str:
    """
    /assets/images/4k/xxx.jpg or /assets/images/thumb/xxx.webp などから
    /assets/images/large/xxx.webp を返す（表示用）。
    """
    name = Path(src_path).name
    stem = Path(name).stem
    return f"/assets/images/large/{stem}.webp"

def all_images(slug: str, image_order: str = ""):
    """
    サムネ用フォルダから slug で始まるファイルを列挙する。
    WebP と JPG/PNG が重複している場合、WebP を優先して採用し、JPG/PNG は除外する。
    image_order があれば、その順序を優先する（cover は別扱いで先頭寄せ）。
    """
    thumb_dir = ROOT / "assets" / "images" / "thumb"
    if not thumb_dir.exists():
        return []

    # slug と slug のアンダースコア版の両方に対応
    want_prefixes = [slug, slug.replace("-", "_")]
    exts = (".webp", ".jpg", ".jpeg", ".png", ".WEBP", ".JPG", ".JPEG", ".PNG")

    # 1) 候補ファイルを収集
    candidates = []
    for p in thumb_dir.iterdir():
        if not p.is_file():
            continue

        name = p.name
        low = name.lower()

        if not any(low.endswith(ext.lower()) for ext in exts):
            continue
        if not any(low.startswith(pref.lower()) for pref in want_prefixes):
            continue

        is_cover = ("-cover." in low) or ("_cover." in low)
        path = f"/assets/images/thumb/{name}"
        candidates.append((name, path, is_cover))

    if not candidates:
        return []

    # 2) 重複除外（WebP優先）
    #    拡張子を除いた stem をキーにして、同stemで webp があれば webp を採用
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

    # 3) cover と通常を分けてソート（cover優先＋image_order対応）
    covers = [path for (name, path, is_cover) in unique_candidates if is_cover]
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

def render_gallery_card(it):
    """ギャラリー／トップ用の一覧カード（画像＋日本語タイトル1本）"""
    slug = it["slug"]

    # 日本語タイトル（なければ従来の stone/carat/design から組み立て）
    title_jp = (it.get("title_jp") or "").strip()
    if not title_jp:
        stone  = (it.get("stone") or "").strip()
        carat  = (it.get("carat") or "").strip()
        design = (it.get("design_name") or "").strip()

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

# ---- Compatibility wrappers (avoid "missing function" confusion) ----
def card_html(it: dict) -> str:
    """
    旧コード互換：ギャラリー用カードHTMLを返す。
    以前の card_html(...) 呼び出しを生かすためのラッパー。
    """
    return render_gallery_card(it)

def news_card_html(n: dict) -> str:
    """
    旧コード互換：ニュース一覧ページ用カードHTMLを返す。
    以前の news_card_html(...) 呼び出しを生かすためのラッパー。
    """
    return render_news_index_card(n)

def gallery_index_html(cards: str, prev_link: str = None, next_link: str = None) -> str:
    """
    ギャラリー一覧ページ全体のHTML。
    ヘッダーは「ロゴ → メニュー」を共通で表示する。
    """
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

    # 共通ヘッダー
    logo_html = render_partial("top_logo.html")
    nav_html  = render_partial("nav_main.html")

    return f'''<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gallery – Rara Lab</title>
<link rel="stylesheet" href="/assets/css/site.css">
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

    return f'''<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rara Lab</title>
<link rel="stylesheet" href="/assets/css/site.css">
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
</body>'''

def detail_html(it):
    """ギャラリー／詳細ページ（1石）のフルHTMLを返す。"""
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
    thumbs_all = all_images(slug, image_order=image_order)

    process_order = it.get("process_image_order", "").strip()

    from pathlib import Path as _Path
    import re as _re

    def _thumb_id(path: str) -> str:
        """
        /assets/images/thumb/<slug>-DSC_9991.webp から 'DSC_9991' を取り出す
        cover は 'cover' になる（Photos側に残す想定）
        """
        stem = _Path(path).stem  # 拡張子なし
        for pref in (slug, slug.replace("-", "_")):
            if stem.startswith(pref + "-"):
                return stem[len(pref) + 1 :]
            if stem.startswith(pref + "_"):
                return stem[len(pref) + 1 :]
            if stem == pref:
                return ""
        return stem

    process_ids = []
    if process_order:
        for token in _re.split(r"[,\s]+", process_order):
            t = token.strip()
            if t:
                process_ids.append(t)

    process_set = set(process_ids)
    order_index = {pid: i for i, pid in enumerate(process_ids)}

    # Process は「指定IDだけ」に絞り込み（順序もCSV指定に合わせる）
    process_thumbs = [p for p in thumbs_all if _thumb_id(p) in process_set]
    process_thumbs.sort(key=lambda p: order_index.get(_thumb_id(p), 10**9))

    # Photos は Process 分を除外（cover は残る）
    thumbs = [p for p in thumbs_all if _thumb_id(p) not in process_set]

    hero_display = ""
    hero_full = ""

    if hero_4k:
        hero_display = path_to_large(hero_4k)   # 表示は large（軽い）
        hero_full    = hero_4k                 # 拡大は 4k のまま
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
                f'<img src="{t}"{img_class_attr} alt="{html.escape(title)}" loading="lazy" decoding="async"></a>'
            )

        label_html = f'<p class="thumbs-label">{html.escape(label_text)}</p>\n' if label_text else ""
        return label_html + f'<div class="thumbs thumbs--{kind}">\n' + "\n".join(items) + "\n</div>"

    blocks = []

    if thumbs:
        blocks.append(render_thumbs_block(
            thumbs,
            f"Photos ({len(thumbs)})",
            kind="photos"
        ))

    if process_thumbs:
        blocks.append(render_thumbs_block(
            process_thumbs,
            f"Making ({len(process_thumbs)})",
            kind="process"
        ))

    thumbs_html = ""
    if blocks:
        thumbs_html = '<section class="thumbs-wrap">\n' + "\n".join(blocks) + "\n</section>"

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

    # 共通ヘッダー
    logo_html = render_partial("top_logo.html")
    nav_html  = render_partial("nav_main.html")

    # ---- 出力 ----
    return f'''<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} – Rara Lab</title>
<link rel="stylesheet" href="/assets/css/site.css">
<body>
{logo_html}
{nav_html}
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
</body>
'''

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

    # まず消せるだけ消す（失敗しても致命傷にしない）
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
    pages = []
    for i in range(0, len(items), PAGE_SIZE):
        pages.append(items[i:i + PAGE_SIZE])

    page_count = len(pages)

    for idx, page_items in enumerate(pages):
        page_num = idx + 1

        # カードHTML
        cards = "\n".join(render_gallery_card(it) for it in page_items)

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
            inject_footer(gallery_index_html(cards, prev_link=prev_link, next_link=next_link)),
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
        pages = []
        for i in range(0, len(news_items), PAGE_SIZE):
            pages.append(news_items[i:i + PAGE_SIZE])

        page_count = len(pages)

        for idx, page_items in enumerate(pages):
            page_num = idx + 1

            cards = "\n".join(render_news_index_card(n) for n in page_items)

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
                inject_footer(news_index_html(cards, prev_link=prev_link, next_link=next_link)),
                encoding="utf-8"
            )
    else:
        # newsが0件でも index.html だけは作って Directory listing を回避
        (OUT_NEWS / "index.html").write_text(
            inject_footer(news_index_html("")),
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

    # 個別ページ /news/<slug>/index.html（本文は assets/news/body/<slug>.html 固定）
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

if __name__ == "__main__":
    build()
    print("✅ build complete: gallery, news, details, and top index generated.")