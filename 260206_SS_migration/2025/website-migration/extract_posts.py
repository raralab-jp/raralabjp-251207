#!/usr/bin/env python3
import json, os, pathlib, datetime

IN_DIR = "json"
OUT_DIR = "site/gemdiary"  # 出力先（お好みで変更可）

def ms_to_date(ms):
    try:
        return datetime.datetime.utcfromtimestamp(ms/1000).strftime("%Y-%m-%d")
    except Exception:
        return ""

def render_html(title, body, pubdate, slug):
    # 最小の土台。CSSやナビは後で差し替え可
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="date" content="{pubdate}">
  <link rel="canonical" href="/gemdiary/{slug}/">
</head>
<body>
  <main>
  {body}
  </main>
</body>
</html>
"""

def load_item(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Squarespaceの構造に合わせて安全に拾う
    item = data.get("item") or data.get("record") or {}
    return {
        "title": item.get("title") or "",
        "body": item.get("body") or "",
        "publishOn": item.get("publishOn"),
        "urlId": item.get("urlId") or ""
    }

def main():
    pathlib.Path(OUT_DIR).mkdir(parents=True, exist_ok=True)
    count_ok = count_skip = 0
    for p in pathlib.Path(IN_DIR).glob("*.json"):
        item = load_item(p)
        slug = item["urlId"] or p.stem
        body = item["body"]
        if not body:
            print(f"SKIP(no body): {slug}")
            count_skip += 1
            continue
        title = item["title"] or slug
        pubdate = ms_to_date(item["publishOn"]) if item["publishOn"] else ""
        out_dir = pathlib.Path(OUT_DIR) / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "index.html"
        out_path.write_text(render_html(title, body, pubdate, slug), encoding="utf-8")
        print(f"WROTE: {out_path}")
        count_ok += 1
    print(f"done. wrote={count_ok}, skipped(no body)={count_skip}")

if __name__ == "__main__":
    main()