#!/usr/bin/env python3
import re, io, csv, sys, argparse

# -----------------------------
# Read input text (from stdin)
# -----------------------------
text = sys.stdin.read().strip()

# -----------------------------
# Helpers
# -----------------------------
def pick(labels, text, default=""):
    """
    Pick the LAST occurrence of any labeled line.
    Labels are treated as plain strings (not regex).
    Accepts both ':' and '：'.
    Allows leading whitespace before labels.

    Important:
    Do not let \s* consume the newline after an empty label.
    Use [ \t]* instead of \s* around the colon.
    """
    for label in labels:
        pat = rf"^[ \t]*{re.escape(label)}[ \t]*(?:[:：][ \t]*(.*))?[ \t]*$"
        ms = re.findall(pat, text, flags=re.M | re.I)
        if ms:
            return ms[-1].strip()
    return default

def warn(msg):
    print(f"WARN: {msg}", file=sys.stderr)

def to_bool01(s: str) -> str:
    """
    Convert user input to "1" / "0" / "" (unspecified).
    Accepts: 1/0, true/false, yes/no, on/off, named.
    """
    s = (s or "").strip().lower()
    if s in ("1", "true", "yes", "y", "on", "named"):
        return "1"
    if s in ("0", "false", "no", "n", "off"):
        return "0"
    return ""

def slugify(s):
    s = (s or "").lower()
    s = re.sub(r"[’'“”\"]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s

def parse_carat_value(s: str) -> str:
    """
    Extract numeric carat value WITHOUT normalizing decimals.
    Returns e.g. "1.019" or "1.2" exactly as in the source (trimmed).
    Accepts '1.019ct' or '1.019 ct'.
    """
    s = (s or "").strip()
    if not s:
        return ""
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*ct\b", s, flags=re.I)
    return m.group(1).strip() if m else ""

def warn_if_carat_weird(carat_str: str):
    """
    Policy:
      - Sorted: decimals must be 3 digits (e.g., 1.019)
      - Unsorted: decimals must be 1 digit (e.g., 1.2)
    Do NOT normalize; only warn.
    """
    if not carat_str:
        return
    if not re.fullmatch(r"\d+(?:\.\d+)?", carat_str):
        warn(f"carat format looks invalid: {carat_str!r}")
        return
    if "." in carat_str:
        dec = carat_str.split(".", 1)[1]
        if len(dec) not in (1, 3):
            warn(f"carat decimals should be 1 or 3 digits by policy: {carat_str!r}")

def carat_token_no_dot(c: str) -> str:
    """
    For filenames/slug compatibility with legacy assets (your existing rule):
      - "1.2"     -> "12"
      - "1.019"   -> "1019"
      - "0.493"   -> "0493"   (keeps leading zero)
      - "12.345"  -> "12345"  (10ct+ supported)
    IMPORTANT: This does NOT change the 'carat' output field.
    """
    c = (c or "").strip()
    if not c:
        return ""
    if not re.fullmatch(r"\d+(?:\.\d+)?", c):
        return ""
    return c.replace(".", "")

# -----------------------------
# Parse: first non-empty line (fallback only)
# -----------------------------
def first_content_line(text: str) -> str:
    # fixed labels; skip if line starts with these labels (colon optional, whitespace allowed)
    skip_labels = (
        "URLs", "image_order", "process_image_order",
        "Title JP", "Japanese Title", "Product ID", "ProductID", "ID",
        "Stone", "Stone JP", "stone_ja", "Facet Design", "Design", "Designed by", "Designer", "Faceted by",
        "Carat", "Size", "Origin", "Treatment", "Clarity",
        "Design Is Named", "design_is_named", "modification_note", "Modification Note",
        "商品番号", "石種", "石種JP", "石種日本語", "ファセットデザイン", "デザイナー", "研磨", "重さ", "サイズ",
        "産地", "処理", "透明度", "鑑別", "デザイン改変",
    )
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            continue
        low = s.lower()
        if any(low.startswith(lbl.lower()) for lbl in skip_labels):
            continue
        return s
    return ""

first = first_content_line(text)

# -----------------------------
# Prefer fixed labels (your policy)
# -----------------------------
title_jp_input = pick(["Title JP", "Japanese Title"], text, default="")
product_id = pick(["Product ID", "ProductID", "ID", "商品番号"], text, default="").strip()

# English fields are kept for existing gallery/slug behavior.
# Japanese labels are added as optional master/listing fields.
#
# Policy:
#   Stone / 石種       = English stone name for slug and legacy gallery field
#   Stone JP / 石種JP = Japanese stone name for title_jp and listing/master fields
#
# Backward compatibility:
#   Older test data may use "石種: Montana Sapphire". If that value is ASCII/slugifiable,
#   it is treated as the English stone name below, not as the Japanese display name.
stone_ja = pick(["Stone JP", "stone_ja", "石種JP", "石種日本語"], text, default="").strip()
stone_jp_legacy = pick(["石種"], text, default="").strip()
if not stone_ja and stone_jp_legacy and not slugify(stone_jp_legacy):
    # If someone writes "石種: モンタナサファイア", keep it as Japanese display name.
    stone_ja = stone_jp_legacy

design_name_raw = pick(["Facet Design", "ファセットデザイン"], text, default="")
if not design_name_raw:
    design_name_raw = pick(["Design"], text, default="")

designer = pick(["Designed by", "Designer", "デザイナー"], text, default="")
faceted_by = pick(["Faceted by"], text, default="Rara Lab")
faceted_by_ja = pick(["研磨"], text, default="").strip()

size_mm = pick(["Size", "サイズ"], text, default="")
origin_en = pick(["Origin"], text, default="")
origin_ja = pick(["産地"], text, default="")
if not origin_en and origin_ja and re.search(r"[A-Za-z]", origin_ja):
    origin_en = origin_ja

treatment = pick(["Treatment"], text, default="")
treatment_ja = pick(["処理"], text, default="")
if not treatment and treatment_ja and re.search(r"[A-Za-z]", treatment_ja):
    treatment = treatment_ja

clarity = pick(["Clarity", "クラリティ"], text, default="")
clarity_note_ja = pick(["透明度", "クラリティ"], text, default="")
if not clarity and clarity_note_ja and re.search(r"[A-Za-z]", clarity_note_ja):
    clarity = clarity_note_ja

cut_note = pick(["カット備考", "Cut Note", "cut_note"], text, default="").strip()

cert_lab_ja = pick(["鑑別"], text, default="").strip()
cert_lab_en = pick(["cert_lab_en", "Cert Lab EN"], text, default="").strip()

# -----------------------------
# Image order (optional)
# -----------------------------
image_order = pick(["image_order"], text, default="").strip()
process_image_order = pick(["process_image_order"], text, default="").strip()

# -----------------------------
# Optional: modification note + design quote flag
# -----------------------------
modification_note = pick(["modification_note", "Modification Note", "デザイン改変"], text, default="").strip()

# Safety guard:
# If the modification field accidentally captured the next labeled field
# (for example "デザイナー: TJ Jackson"), treat it as empty.
# Modification should be shown only when the user writes an actual note in
# modification_note / Modification Note / デザイン改変.
_modification_bad_prefixes = (
    "デザイナー:", "デザイナー：",
    "Designer:", "Designer：",
    "Designed by:", "Designed by：",
    "研磨:", "研磨：",
    "Faceted by:", "Faceted by：",
    "石種:", "石種：",
    "Stone:", "Stone：",
    "産地:", "産地：",
    "Origin:", "Origin：",
)
if modification_note.startswith(_modification_bad_prefixes):
    warn(f"modification_note looks like another field and was ignored: {modification_note!r}")
    modification_note = ""

design_is_named = to_bool01(pick(["Design Is Named", "design_is_named"], text, default=""))

# -----------------------------
# URLs (new unified format)
# -----------------------------
urls_line = pick(["URLs"], text, default="").strip()

shop_url = ""
video_url = ""
gallery_url = ""
note_url = ""

if urls_line:
    for part in urls_line.split(";"):
        p = part.strip()
        if p.startswith("shop="):
            shop_url = p[len("shop="):].strip()
        elif p.startswith("video="):
            video_url = p[len("video="):].strip()
        elif p.startswith("gallery="):
            gallery_url = p[len("gallery="):].strip()
        elif p.startswith("note="):
            note_url = p[len("note="):].strip()

# sanity check (detect mix-up, do not auto-fix)
if "raralab.shop" in video_url:
    warn("Video iframe contains a shop URL. Check input.")
    video_url = ""

if shop_url and "cloudflarestream.com" in shop_url:
    warn("Shop URL contains a video URL. Check input.")
    shop_url = ""

# -----------------------------
# Stone / Carat (minimize guessing)
# -----------------------------
stone = ""
carat = ""

# Prefer explicit Stone label (English, for slug stability).
# If only the Japanese label is supplied but the value is ASCII/slugifiable
# (e.g. "石種: Montana Sapphire"), safely use it for the legacy stone field too.
stone_labeled = pick(["Stone"], text, default="").strip()
stone_legacy_labeled = pick(["石種"], text, default="").strip()
has_stone_label = bool(stone_labeled or stone_legacy_labeled)
if stone_labeled:
    stone = stone_labeled
    if not slugify(stone):
        warn("Stone label exists but cannot be slugified. Use English in 'Stone:'.")
elif stone_legacy_labeled and slugify(stone_legacy_labeled):
    # Japanese label with English value, e.g. "石種: Montana Sapphire"
    stone = stone_legacy_labeled
elif stone_legacy_labeled:
    # Japanese-only value is useful for title_jp, but not for slug stability.
    stone = ""
    warn("石種 is Japanese/non-ascii. Add 'Stone:' in English or use '石種: English' + '石種JP: 日本語'.")

# Carat: prefer label (fixed)
carat_labeled = parse_carat_value(pick(["Carat", "重さ"], text, default=""))
has_carat_label = bool(carat_labeled)
if has_carat_label:
    carat = carat_labeled

# -----------------------------
# Fallbacks (ONLY when labels are missing)
# -----------------------------

# Fallback: parse from first line "Zircon 1.019ct"
# Only run when Stone label is missing OR Carat label is missing
if (not has_stone_label) or (not has_carat_label):
    m1 = re.match(r"^(.+?)\s+([0-9]+(?:\.[0-9]+)?)\s*ct$", first, flags=re.I)
    if m1:
        if not has_stone_label:
            stone = m1.group(1).strip()
        if not has_carat_label and not carat:
            carat = m1.group(2).strip()

# If still no stone, try Title JP pattern: "ジルコン 1.019ct “Tessellation 20”"
# Only for missing Stone label (this may be Japanese, so warn later)
if not has_stone_label and not stone and title_jp_input:
    m_jp = re.match(r"^(.+?)\s+([0-9]+(?:\.[0-9]+)?)\s*ct\b", title_jp_input)
    if m_jp:
        stone = m_jp.group(1).strip()
        if not has_carat_label and not carat:
            carat = m_jp.group(2).strip()

# If still no stone but we have quoted first line: 'Zircon “Design”'
# Only for missing Stone label
if not has_stone_label and not stone:
    m_title = re.match(r'^(.+?)\s*[“"](.*?)[”"]\s*$', first)
    if m_title:
        stone = m_title.group(1).strip()

# Final sanity warnings (do not change values)
if not stone:
    warn("stone is empty")
elif not slugify(stone):
    # stone might be JP if coming from Title JP fallback etc.
    warn("stone cannot be slugified (non-ascii likely). Consider adding 'Stone:' in English for slug stability.")

if not carat:
    warn("carat is empty")

# -----------------------------
# Clean Design Name
# -----------------------------
# fallback: quoted design name in first line
if not design_name_raw:
    m_title = re.match(r'^(.+?)\s*[“"](.*?)[”"]\s*$', first)
    if m_title:
        design_name_raw = m_title.group(2).strip()

design_name = design_name_raw.strip("“”\"' ").strip()

# -----------------------------
# Clarity fallback (optional)
# -----------------------------
if not clarity:
    m_eye = re.search(r"^Eye\s*Clean\b.*$", text, flags=re.M | re.I)
    if m_eye:
        clarity = m_eye.group(0).strip()
clarity = clarity.strip()

# -----------------------------
# Normalize treatment (light)
# -----------------------------
treatment_map = {
    "heated": "Heated",
    "heat": "Heated",
    "none": "None",
    "untreated": "None",
}
treatment_norm = treatment_map.get(treatment.lower(), treatment) if treatment else ""

# -----------------------------
# Carat validation (WARN only; do not normalize)
# -----------------------------
warn_if_carat_weird(carat)

# Carat token for filenames/slug (legacy-compatible)
carat_token = carat_token_no_dot(carat) if carat else ""
if carat_token and len(carat_token) > 5:
    # You said 100ct+ is not expected; this catches 100.000 -> "100000" etc.
    warn(f"carat_token is {len(carat_token)} digits (100ct+?). unexpected: {carat!r} -> {carat_token!r}")

# -----------------------------
# Slug default (use carat_token, not padded 4-digit)
# -----------------------------
slug_default = (
    f"{slugify(stone)}-{carat_token}ct-{slugify(design_name)}"
    if (stone and carat_token and design_name)
    else ""
)

# wrap_design: if design is explicit or first line is quoted
wrap_design = bool(design_name_raw) or bool(re.match(r'^(.+?)\s*[“"](.*?)[”"]\s*$', first))

# If user didn't specify, infer from wrap_design (named design => quoted)
if design_is_named == "":
    design_is_named = "1" if wrap_design else "0"

# title default: prefer explicit input; else generate from Japanese stone name when available.
if title_jp_input:
    title_default = title_jp_input
else:
    title_stone = stone_ja or stone
    if title_stone and carat and design_name:
        if wrap_design:
            title_default = f"{title_stone} {carat}ct “{design_name}”"
        else:
            title_default = f"{title_stone} {carat}ct {design_name}"
    else:
        title_default = ""
    if title_default and not stone_ja:
        warn("title_jp was auto-generated with English stone name. Add 'Stone JP:' or '石種JP:' for Japanese title.")

# -----------------------------
# Args
# -----------------------------
ap = argparse.ArgumentParser(add_help=False)
ap.add_argument("--slug", dest="slug", default=slug_default)
ap.add_argument("--title_jp", dest="title_jp", default=title_default)
ap.add_argument("--date", dest="date", default="")
ap.add_argument("--debug", action="store_true")
args, _ = ap.parse_known_args()

if args.debug:
    print("DBG first =", repr(first), file=sys.stderr)
    print("DBG stone =", repr(stone), file=sys.stderr)
    print("DBG stone_ja =", repr(stone_ja), file=sys.stderr)
    print("DBG carat =", repr(carat), file=sys.stderr)
    print("DBG carat_token =", repr(carat_token), file=sys.stderr)
    print("DBG design_name =", repr(design_name), file=sys.stderr)
    print("DBG slug_default =", repr(slug_default), file=sys.stderr)
    print("DBG video_url =", repr(video_url), file=sys.stderr)
    print("DBG shop_url  =", repr(shop_url), file=sys.stderr)
    print("DBG modification_note =", repr(modification_note), file=sys.stderr)
    print("DBG design_is_named =", repr(design_is_named), file=sys.stderr)

# -----------------------------
# WARN checks (do not stop CSV output)
# -----------------------------
if not stone:
    warn("stone is empty")
if not design_name:
    warn("design_name is empty")
if not carat:
    warn("carat is empty")
if not size_mm:
    warn("size_mm is empty")
if not treatment_norm and not treatment_ja:
    warn("treatment is empty")
if not origin_en and not origin_ja:
    warn("origin is empty (fill later)")
if not args.slug:
    warn("slug is empty")
if not args.title_jp:
    warn("title_jp is empty")

# -----------------------------
# Output CSV
# -----------------------------
header = [
    "slug","stone","design_name","designer","faceted_by","carat",
    "size_mm","origin_en","treatment","clarity_note_en",
    "title_jp","date","tags","image_order","process_image_order","video_url","shop_url",
    "modification_note","design_is_named",
    "product_id","stone_ja","faceted_by_ja","origin_ja","treatment_ja","clarity_note_ja",
    "cert_lab_ja","cert_lab_en","title_jp_override","clarity_note_ja_override","clarity_note_en_override","gallery_url","note_url","cut_note",
]

row = {
    "slug": args.slug,
    "stone": stone,
    "design_name": design_name,
    "designer": designer,
    "faceted_by": faceted_by or "Rara Lab",
    "carat": carat,                     # ← 入力の小数桁を保持（正規化しない）
    "size_mm": size_mm,
    "origin_en": origin_en,
    "treatment": treatment_norm,
    "clarity_note_en": clarity,
    "title_jp": args.title_jp,
    "date": args.date,
    "tags": "",
    "image_order": image_order,
    "process_image_order": process_image_order,
    "video_url": video_url,
    "shop_url": shop_url,
    "modification_note": modification_note,
    "design_is_named": design_is_named,
    "product_id": product_id,
    "stone_ja": stone_ja,
    "faceted_by_ja": faceted_by_ja,
    "origin_ja": origin_ja,
    "treatment_ja": treatment_ja,
    "clarity_note_ja": clarity_note_ja,
    "cert_lab_ja": cert_lab_ja,
    "cert_lab_en": cert_lab_en,
    "title_jp_override": "",
    "clarity_note_ja_override": "",
    "clarity_note_en_override": "",
    "gallery_url": gallery_url,
    "note_url": note_url,
    "cut_note": cut_note,
}

buf = io.StringIO()
w = csv.DictWriter(buf, fieldnames=header)
w.writeheader()
w.writerow(row)

out = buf.getvalue()
if not out.endswith("\n"):
    out += "\n"
sys.stdout.write(out)