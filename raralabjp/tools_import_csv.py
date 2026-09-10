#!/usr/bin/env python3
#!/usr/bin/env python3
import csv, json, pathlib, re, sys, argparse

from labels import COLOR_LABELS

parser = argparse.ArgumentParser()
parser.add_argument("--slug", default="", help="Update only this product, preserving other JSON records")
args = parser.parse_args()
matched = False

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
    s = re.sub(
        r"\bprocess_image_order\s*:\s*",
        "",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\bimage_order\s*:\s*",
        "",
        s,
        flags=re.IGNORECASE,
    )

    ids = [
        pathlib.Path(token.strip()).stem
        for token in re.split(r"[,\s]+", s)
        if token.strip()
    ]

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

        if args.slug and slug != args.slug:
            continue
        matched = True

        def S(k):
            v = row.get(k)
            return "" if v is None else str(v).strip()

        tags = [
            t.strip()
            for t in (S("tags").split("|") if S("tags") else [])
            if t.strip()
        ]
        colors = []
        for value in S("colors").split("|"):
            color = value.strip().lower()
            if not color:
                continue
            if color not in COLOR_LABELS:
                print(f"WARN: unknown color key kept for {slug}: {color}", file=sys.stderr)
            if color not in colors:
                colors.append(color)

        # 新規追加フィールド（空なら None で落とす）
        mod_note = S("modification_note") or None

        # design_is_named:
        # - CSV 側は "1"/"0" 想定
        # - 空欄なら None（= 未指定）
        # - "1"/"0" は文字列のまま保持（build.py 側 is_truthy() で判定）
        din = S("design_is_named")
        design_is_named = din if din else None

        # 既存データがあれば引き継ぎつつ上書き
        is_new = slug not in index
        it = index.get(slug, {})
        # Keep the source's decimal places; never reconstruct precision from float.
        carat_text = S("carat")
        if carat_text and not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", carat_text):
            parser.error(f"invalid carat for {slug}: {carat_text!r}")
        if is_new or S("image_selection_policy") or it.get("image_selection_policy"):
            if S("image_selection_policy") not in ("", "explicit"):
                parser.error(f"unsupported image selection policy for {slug}")
            it["image_selection_policy"] = "explicit"
            it["cover_image"] = S("cover_image") or it.get("cover_image", "")
        it.update({
            "slug": slug,
            "stone": S("stone"),
            "design_name": S("design_name"),
            "designer": S("designer"),
            "faceted_by": S("faceted_by") or "Rara Lab",
            "carat": carat_text,
            "size_mm": S("size_mm"),
            "origin_en": S("origin_en"),
            "treatment": S("treatment"),
            "clarity_note_en": S("clarity_note_en"),
            "title_jp": S("title_jp"),
            "date": S("date"),
            "tags": tags,
            "colors": colors,
            "image_order": S("image_order"),
            "process_image_order": S("process_image_order"),
            "video_url": S("video_url"),
            "shop_url": S("shop_url"),

            # ★追加（今回の目的）
            "modification_note": mod_note,
            "additional_note": S("additional_note") or None,
            "design_is_named": design_is_named,
        })
        index[slug] = it

if args.slug and not matched:
    parser.error(f"slug not found in CSV: {args.slug}")

# 日付で降順ソート
out = list(index.values())
out.sort(key=lambda x: x.get("date", ""), reverse=True)

jsonp.write_text(
    json.dumps(out, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print(f"✅ items.json 更新: {len(out)} 件")
