#!/usr/bin/env python3
import re, sys, csv, io, unicodedata, argparse

raw = sys.stdin.read()
text = unicodedata.normalize("NFKC", raw)

def pick(labels, default=""):
    for label in labels:
        m = re.search(rf"^{label}\s*:?\s*(.+)$", text, flags=re.M|re.I)
        if m: return m.group(1).strip()
    return default

first = text.strip().splitlines()[0].strip() if text.strip() else ""
m1 = re.match(r"^(.+?)\s+([0-9.]+)\s*ct$", first, flags=re.I)
stone = m1.group(1).strip() if m1 else ""
carat = m1.group(2).strip() if m1 else ""

design_name_raw = pick([r"Facet\s*Design", r"Design"])
design_name = design_name_raw.strip("“”\"' ")
designer = pick([r"Designed\s*by", r"Designer"])
faceted_by = pick([r"Faceted\s*by"], "Rara Lab")
size_mm = pick([r"Size"])
origin_en = pick([r"Origin"])
treatment = pick([r"Treatment"])
clarity = pick([r"Clarity"])

def slugify(s):
    s = s.lower()
    s = re.sub(r"[’'“”\"]","",s)
    s = re.sub(r"[^a-z0-9]+","-",s)
    s = re.sub(r"-+","-",s).strip("-")
    return s

def carat4_from_str(c):
    digits = re.sub(r"\D","", c)
    digits = (digits + "0000")[:4]
    return digits.zfill(4)

carat4 = carat4_from_str(carat) if carat else ""
slug_default = f"{slugify(stone)}-{carat4}ct-{slugify(design_name)}" if (stone and carat4 and design_name) else ""
title_default = f"{stone} {carat}ct “{design_name}”" if stone and carat and design_name else ""

ap = argparse.ArgumentParser(add_help=False)
ap.add_argument("--slug", dest="slug", default=slug_default)
ap.add_argument("--title_jp", dest="title_jp", default=title_default)
ap.add_argument("--date", dest="date", default="")
args, _ = ap.parse_known_args()

header = [
  "slug","stone","design_name","designer","faceted_by","carat",
  "size_mm","origin_en","treatment","clarity_note_en",
  "title_jp","date","tags","image_order"   # ★ image_order を追加
]

row = {
  "slug": args.slug,
  "stone": stone,
  "design_name": design_name,
  "designer": designer,
  "faceted_by": faceted_by or "Rara Lab",
  "carat": carat,
  "size_mm": size_mm,
  "origin_en": origin_en,
  "treatment": treatment,
  "clarity_note_en": clarity,
  "title_jp": args.title_jp,
  "date": args.date,
  "tags": "",
  "image_order": ""   # ここは手動で後から埋める前提なら空でOK
}

buf = io.StringIO()
w = csv.DictWriter(buf, fieldnames=header)
w.writeheader(); w.writerow(row)
print(buf.getvalue().strip())
