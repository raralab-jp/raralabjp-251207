#!/usr/bin/env python3
#!/usr/bin/env python3
import csv, json, pathlib, re

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

def _clean_order_field(v) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    # ラベル残留を除去
    s = re.sub(r"\bprocess_image_order\s*:\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\bimage_order\s*:\s*", "", s, flags=re.IGNORECASE)
    # IDっぽいものだけ残す（DSC_#### 等）
    ids = re.findall(r"(?:DSC_\d+|IMG_\d+|\d{4,})", s)
    return " ".join(ids)

def normalize_orders(row: dict) -> None:
    img = _clean_order_field(row.get("image_order"))
    proc = _clean_order_field(row.get("process_image_order"))

    # 典型事故：image_order に "process_image_order: ..." が入って proc が空
    raw_img = str(row.get("image_order") or "")
    if (not proc) and re.search(r"\bprocess_image_order\s*:", raw_img, flags=re.IGNORECASE):
        proc = img
        img = ""

    row["image_order"] = img
    row["process_image_order"] = proc

with csvp.open(newline="", encoding="utf-8") as f:
    r = csv.DictReader(f)

    for row in r:
        normalize_orders(row)  # ← ★ここ（最初）

        slug = (row.get("slug") or "").strip()
        if not slug:
            continue

        def S(k):
            v = row.get(k)
            return "" if v is None else str(v).strip()

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

        # 新規追加フィールド（空なら None で落とす）
        mod_note = S("modification_note") or None

        # design_is_named:
        # - CSV 側は "1"/"0" 想定
        # - 空欄なら None（= 未指定）
        # - "1"/"0" は文字列のまま保持（build.py 側 is_truthy() で判定）
        din = S("design_is_named")
        design_is_named = din if din else None

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
            "process_image_order": S("process_image_order"),
            "video_url": S("video_url"),
            "shop_url": S("shop_url"),

            # ★追加（今回の目的）
            "modification_note": mod_note,
            "design_is_named": design_is_named,
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