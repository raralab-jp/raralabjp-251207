#!/usr/bin/env python3
import csv
import sys
from pathlib import Path
import io

def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(1)

def is_blank_row(row: dict) -> bool:
    if not row:
        return True
    for v in row.values():
        if (v or "").strip():
            return False
    return True

def clean_row(row: dict) -> dict:
    # 余剰列があると DictReader は None キーにリストを入れる
    if row is None:
        return {}
    if None in row:
        row.pop(None, None)
    return row

def clean_fieldnames(fns):
    if not fns:
        return None
    return [fn for fn in fns if fn is not None]

def read_csv_rows(path: Path):
    if not path.exists():
        return [], None

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        fieldnames = clean_fieldnames(r.fieldnames)
        rows = []
        for row in r:
            row = clean_row(row)
            if is_blank_row(row):
                continue
            rows.append(row)
        return rows, fieldnames

def read_single_row_from_stdin():
    text = sys.stdin.read()
    if not text.strip():
        die("stdin is empty")

    f = io.StringIO(text)
    r = csv.DictReader(f)
    fieldnames = clean_fieldnames(r.fieldnames)

    rows = []
    for row in r:
        row = clean_row(row)
        if is_blank_row(row):
            continue
        rows.append(row)

    if len(rows) != 1:
        die(f"stdin must contain exactly 1 data row, got {len(rows)}")

    return rows[0], fieldnames

def main():
    if len(sys.argv) != 2:
        die("usage: tools_upsert_csv.py <target_csv_path>")

    target = Path(sys.argv[1])

    new_row, new_fields = read_single_row_from_stdin()
    slug = (new_row.get("slug") or "").strip()
    if not slug:
        die("new row has empty slug")

    existing_rows, existing_fields = read_csv_rows(target)

    fieldnames = existing_fields or new_fields
    if not fieldnames:
        die("cannot determine fieldnames")

    out_rows = []
    replaced = False

    for row in existing_rows:
        rslug = (row.get("slug") or "").strip()
        if not rslug:
            continue
        if rslug == slug:
            out_rows.append(new_row)
            replaced = True
        else:
            out_rows.append(row)

    if not replaced:
        out_rows.append(new_row)

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(out_rows)

if __name__ == "__main__":
    main()