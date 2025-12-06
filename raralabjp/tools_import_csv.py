#!/usr/bin/env python3
import csv, json, pathlib

root = pathlib.Path(".")
csvp = root / "assets/data/items.csv"
jsonp = root / "assets/data/items.json"

# 既存 items.json を読み込み（壊れていたら空から）
if jsonp.exists():
    try:
        items = json.loads(jsonp.read_text(encoding="utf-8"))
        if not isinstance(items, list):
            print("⚠ items.json の形式が想定外なので、空の状態から再生成します。")
            items = []
    except json.JSONDecodeError:
        print("⚠ items.json のJSONが壊れているので、空の状態から再生成します。")
        items = []
else:
    items = []

# slug をキーにしたインデックス
index = {it.get("slug"): it for it in items if it.get("slug")}

with csvp.open(newline="", encoding="utf-8") as f:
    r = csv.DictReader(f)

    for row in r:
        slug = (row.get("slug") or "").strip()
        if not slug:
            continue

        def S(k):
            return (row.get(k) or "").strip()

        def F(k):
            v = (row.get(k) or "").strip()
            if not v:
                return None
            try:
                return float(v)
            except ValueError:
                return None

        tags = [
            t.strip()
            for t in (S("tags").split("|") if S("tags") else [])
            if t.strip()
        ]

        # 既存データがあれば引き継ぎつつ上書き
        it = index.get(slug, {})
        it.update({
            "slug": slug,
            "stone": S("stone"),
            "design_name": S("design_name"),
            "designer": S("designer"),
            "faceted_by": S("faceted_by") or "Rara Lab",
            "carat": F("carat"),
            "size_mm": S("size_mm"),
            "origin_en": S("origin_en"),
            "treatment": S("treatment"),
            "clarity_note_en": S("clarity_note_en"),
            "title_jp": S("title_jp"),
            "date": S("date"),
            "tags": tags,
            "image_order": S("image_order"),
            "video_url": S("video_url"),
        })
        index[slug] = it

# 日付で降順ソート
out = list(index.values())
out.sort(key=lambda x: x.get("date", ""), reverse=True)

jsonp.write_text(
    json.dumps(out, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print(f"✅ items.json 更新: {len(out)} 件")