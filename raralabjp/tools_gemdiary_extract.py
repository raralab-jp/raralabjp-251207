#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path
import html
from urllib.parse import urlparse, unquote   # ← これを追加

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
RAW_DIR  = ROOT / "assets" / "gemdiary" / "raw"
BODY_DIR = ROOT / "assets" / "gemdiary" / "body"

IMG_PUBLIC_PREFIX = "/assets/gemdiary/"   # ここは site/assets/gemdiary/ に画像を置く前提
IMG_EXT_RE = re.compile(r"\.(jpe?g|png|gif|webp|avif)$", re.I)

FILENAME_RE = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*\.(?:jpe?g|png|gif|webp|avif))", re.I)

from urllib.parse import urlparse, unquote

FILENAME_IN_STR_RE = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*\.(?:jpe?g|png|gif|webp|avif))", re.I)

def filename_from_any(s: str) -> str:
    """
    URLやパスや属性値っぽい文字列から画像ファイル名を抜く。
    例:
      - https://.../foo.jpg?format=original -> foo.jpg
      - /assets/x/foo.webp -> foo.webp
    """
    if not s:
        return ""
    s = s.strip()

    # URLっぽい場合は path の basename を優先
    try:
        u = urlparse(s)
        if u.scheme in ("http", "https") and u.path:
            base = u.path.rsplit("/", 1)[-1]
            base = unquote(base)
            if IMG_EXT_RE.search(base):
                return base
    except Exception:
        pass

    # それ以外は文字列中から最初の xxx.jpg を拾う
    m = FILENAME_IN_STR_RE.search(s)
    return m.group(1) if m else ""

def extract_filename_from_any(text: str) -> str:
    """
    URL/パス/属性値/JSONなど、どんな文字列からでも画像ファイル名を抜く。
    優先:
      1) URLとして解釈できるなら path の basename
      2) 文字列内の FILENAME_RE にマッチするもの
    """
    if not text:
        return ""
    s = text.strip()

    # 1) URLっぽければ path の末尾を取る（?format=original を無視）
    try:
        u = urlparse(s)
        if u.scheme in ("http", "https") and u.path:
            base = u.path.rsplit("/", 1)[-1]
            base = unquote(base)
            if IMG_EXT_RE.search(base):
                return base
    except Exception:
        pass

    # 2) それ以外は文字列中から拾う
    m = FILENAME_RE.search(s)
    return m.group(1) if m else ""

def guess_image_filename(block) -> str:
    """
    Squarespaceの image-block からファイル名を推測する。
    優先順:
    1) noscript 内の img の src / data-src
    2) 通常の img の src / data-src
    3) alt（最後の保険）
    """
    # 1) noscript優先
    ns = block.find("noscript")
    if ns:
        img = ns.find("img")
        if img:
            for key in ("src", "data-src"):
                fn = extract_filename_from_any((img.get(key) or "").strip())
                if fn:
                    return fn
            alt = (img.get("alt") or "").strip()
            fn = extract_filename_from_any(alt)
            if fn:
                return fn

    # 2) 通常の img（Squarespaceはこっちが本命）
    for img in block.find_all("img"):
        for key in ("src", "data-src"):
            fn = extract_filename_from_any((img.get(key) or "").strip())
            if fn:
                return fn

        alt = (img.get("alt") or "").strip()
        fn = extract_filename_from_any(alt)
        if fn:
            return fn

    return ""

def clean_fragment_html(html: str) -> str:
    """
    余計な外側ラッパーを削りたい場合の最低限クリーニング。
    今回は「危険なものは削らない」方針で軽め。
    """
    # 連続改行を少し整える
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()

def extract_body_from_raw(raw_index: Path) -> tuple[str, list[str]]:
    """
    raw/<slug>/index.html から本文スニペットHTMLを生成する。
    返り値: (body_html, warnings)
    """
    warnings: list[str] = []

    soup = BeautifulSoup(raw_index.read_text(encoding="utf-8", errors="replace"), "html.parser")

    raw_text = raw_index.read_text(encoding="utf-8", errors="replace")

    # ページ全体から画像ファイル名候補を拾う（出現順）
    all_names = re.findall(
        r"[A-Za-z0-9][A-Za-z0-9._-]*\.(?:jpe?g|png|gif|webp|avif)",
        raw_text,
        flags=re.I,
    )
    fallback_names = all_names[:]   # 出現順・重複OK
    fallback_idx = 0

    main = soup.find("main")
    if not main:
        return "<p>(本文が見つかりません)</p>", [f"[warn] <main> not found: {raw_index}"]

    parts: list[str] = []

    # Squarespaceの各ブロックを文書順で拾う
    blocks = main.find_all(class_=re.compile(r"\bsqs-block\b"))
    if not blocks:
        # 予備: main の中身をそのまま（最悪でも何か出す）
        return clean_fragment_html(main.decode_contents()), [f"[warn] sqs-block not found: {raw_index}"]

    for b in blocks:
        cls = " ".join(b.get("class") or [])

        # code-block（本文が入っていることが多い）
        if "sqs-block-code" in cls:
            c = b.find(class_="sqs-code-container")
            if c:
                parts.append(c.decode_contents())
            else:
                # fallback
                parts.append(b.decode_contents())
            continue

        # html-block（撮影機材などの自由HTML）
        if "sqs-block-html" in cls:
            c = b.find(class_="sqs-html-content")
            if c:
                parts.append(c.decode_contents())
            else:
                parts.append(b.decode_contents())
            continue

        # image-block
        if "sqs-block-image" in cls:
            fn = guess_image_filename(b)

            # ブロック内で取れなければ、ページ全体の候補から順番に割り当て
            if not fn and fallback_idx < len(fallback_names):
                fn = fallback_names[fallback_idx]
                fallback_idx += 1

            if fn:
                parts.append(f'<p><img src="{IMG_PUBLIC_PREFIX}{fn}" alt=""></p>')
            else:
                warnings.append(f"[warn] image filename not found: {raw_index}")
                parts.append("<!-- [warn] image block: filename not detected -->")
            continue

        # その他のブロックは基本スキップ（必要なら後で追加）
        # parts.append(f"<!-- skipped block: {cls} -->")

    body_html = clean_fragment_html("\n\n".join(parts))
    if not body_html:
        body_html = "<p>(本文が空でした)</p>"
        warnings.append(f"[warn] extracted body empty: {raw_index}")

    return body_html, warnings

def main():
    BODY_DIR.mkdir(parents=True, exist_ok=True)

    raw_slugs = sorted([p for p in RAW_DIR.iterdir() if p.is_dir()])
    if not raw_slugs:
        print("[gemdiary] no raw folders found.")
        return

    warn_lines: list[str] = []

    for d in raw_slugs:
        raw_index = d / "index.html"
        slug = d.name

        if not raw_index.exists():
            warn_lines.append(f"[warn] index.html missing: {raw_index}")
            continue

        out = BODY_DIR / f"{slug}.html"
        body_html, warns = extract_body_from_raw(raw_index)
        out.write_text(body_html + "\n", encoding="utf-8")
        warn_lines.extend(warns)

    # warnings をファイルに吐く
    if warn_lines:
        wpath = ROOT / "warn_gemdiary_extract.log"
        wpath.write_text("\n".join(warn_lines) + "\n", encoding="utf-8")
        print(f"[gemdiary] extracted with warnings: {wpath.name} ({len(warn_lines)} lines)")
    else:
        print("[gemdiary] extracted: OK (no warnings)")

    print(f"[gemdiary] body generated: {BODY_DIR.relative_to(ROOT)}")

if __name__ == "__main__":
    main()