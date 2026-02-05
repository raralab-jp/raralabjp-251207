#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse, unquote

from bs4 import BeautifulSoup


# ========= 設定 =========

ROOT = Path(__file__).resolve().parent

JSON_DIR = ROOT / "assets" / "gemdiary" / "json"
OUT_DIR  = ROOT / "assets" / "gemdiary" / "body"

IMG_PUBLIC_PREFIX = "/assets/gemdiary/"

IMG_EXT_RE = re.compile(r"\.(jpe?g|png|gif|webp|avif)$", re.I)


# ========= ユーティリティ =========

def extract_filename_from_url(url: str) -> str:
    if not url:
        return ""
    try:
        u = urlparse(url)
        if u.path:
            name = unquote(u.path.rsplit("/", 1)[-1])
            if IMG_EXT_RE.search(name):
                return name
    except Exception:
        pass
    return ""


# ========= 本体 =========

def build_html_from_json(json_path: Path) -> tuple[str, list[str]]:
    """
    JSON 1件 → 本文HTML（画像パス置換済み）
    """
    warnings: list[str] = []

    data = json.loads(json_path.read_text(encoding="utf-8"))
    item = data.get("item")
    if not item:
        return "<p>(item が見つかりません)</p>", ["item missing"]

    body_html = item.get("body", "")
    if not body_html:
        return "<p>(本文が空でした)</p>", ["body empty"]

    soup = BeautifulSoup(body_html, "html.parser")

    for img in soup.find_all("img"):
        src = img.get("src", "")
        fn = extract_filename_from_url(src)
        if fn:
            img["src"] = IMG_PUBLIC_PREFIX + fn
        else:
            warnings.append(f"image filename not detected: {src}")

    return soup.decode_contents(), warnings


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    all_warnings: list[str] = []

    for json_path in sorted(JSON_DIR.glob("*.json")):
        slug = json_path.stem  # 例: 250705-untreated-vs-normal-heated
        out_dir = OUT_DIR / slug
        out_dir.mkdir(parents=True, exist_ok=True)

        body_html, warnings = build_html_from_json(json_path)

        out_html = out_dir / "index.html"
        out_html.write_text(body_html, encoding="utf-8")

        for w in warnings:
            all_warnings.append(f"[{slug}] {w}")

        print(f"OK: {slug}")

    if all_warnings:
        warn_file = ROOT / "warn_gemdiary_from_json.log"
        warn_file.write_text("\n".join(all_warnings), encoding="utf-8")
        print(f"\nWARNINGS written to: {warn_file}")
    else:
        print("\nNo warnings 🎉")


if __name__ == "__main__":
    main()