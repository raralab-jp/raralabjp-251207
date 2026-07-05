#!/usr/bin/env python3
import csv
import sys
from pathlib import Path

NORMALIZE = {
    "stone_ja": {
        "モンタナサファイア": "モンタナ・サファイア",
    },
    "origin_en": {
        "Montana (US)": "Montana, USA",
        "Montana, US": "Montana, USA",
        "Rock Creek, Montana (US)": "Rock Creek, Montana, USA",
        "Rock Creek, Montana, US": "Rock Creek, Montana, USA",
        "Oregon (USA)": "Oregon, USA",
        "Sun Summit Mine, Oregon (US)": "Sun Summit Mine, Oregon, USA",
        "Umba (Tanzania)": "Umba, Tanzania",
        "Lindi (Tanzania)": "Lindi, Tanzania",
    },
    "origin_ja": {
        "Montana, USA": "モンタナ（アメリカ）",
        "Rock Creek, Montana, USA": "ロッククリーク、モンタナ（アメリカ）",
    },
    "treatment": {
        "No treatment": "None",
        "Unkown": "Unknown",
    },
    "treatment_ja": {
        "Unheated": "なし（非加熱）",
        "Heated": "加熱",
    },
    "clarity_note_en": {
        "Eye Clean": "Eye clean",
        "Loupe Clean": "Loupe clean",
    },
    "clarity_note_ja": {
        "Eye clean": "肉眼で目立つインクルージョンなし",
    },
    "faceted_by_ja": {
        "Rara Lab": "Rara Lab",
    },
    "stone_ja": {
    "モンタナサファイア": "モンタナ・サファイア",
    "ピンクトルマリン": "ピンク・トルマリン",
    "モスアクアマリン": "モス・アクアマリン",
},
}

def normalize_value(column: str, value: str) -> str:
    value = "" if value is None else str(value).strip()

    # 完全一致の正規化
    value = NORMALIZE.get(column, {}).get(value, value)

    # title_jp 内の部分置換
    if column == "title_jp":
        value = value.replace("モンタナサファイア", "モンタナ・サファイア")
        value = value.replace("ブルーモンタナ・サファイア", "ブルー・モンタナ・サファイア")
        value = value.replace("ピンクトルマリン", "ピンク・トルマリン")
        value = value.replace("モスアクアマリン", "モス・アクアマリン")

    if column in ("image_order", "process_image_order"):
        value = value.replace("process_image_order:", "")
        value = value.replace("process_image_order：", "")
        value = value.replace("image_order:", "")
        value = value.replace("image_order：", "")
        value = " ".join(value.split())
    return value

def main() -> None:
    if len(sys.argv) != 3:
        print("usage: tools_normalize_items_csv.py <input_csv> <output_csv>", file=sys.stderr)
        raise SystemExit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    with input_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if not fieldnames:
            print("ERROR: CSV header not found", file=sys.stderr)
            raise SystemExit(1)

        rows = []
        changes = []

        for i, row in enumerate(reader, start=2):
            new_row = dict(row)
            slug = (row.get("slug") or "").strip()

            for col in fieldnames:
                old = row.get(col, "")
                new = normalize_value(col, old)
                new_row[col] = new

                if (old or "").strip() != new:
                    changes.append((i, slug, col, old, new))

            rows.append(new_row)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(f"normalized: {input_path} -> {output_path}")
    print(f"changes: {len(changes)}")

    for line_no, slug, col, old, new in changes:
        print(f"{line_no}: {slug}: {col}: {old!r} -> {new!r}")

if __name__ == "__main__":
    main()
