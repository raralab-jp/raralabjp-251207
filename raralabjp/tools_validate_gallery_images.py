#!/usr/bin/env python3
"""Validate explicit image selections before the existing Gallery build writes files."""
import argparse
import json
import re
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def validate_image_selection(item, root):
    slug = item["slug"]
    errors = []
    cover = item.get("cover_image", "")
    if cover != f"{slug}-cover.jpg":
        errors.append(f"{slug}: cover_image must explicitly name {slug}-cover.jpg")

    def selection(field):
        tokens = re.split(r"[,\s]+", item.get(field, "").strip())
        tokens = [token for token in tokens if token]
        if len(tokens) != len(set(tokens)):
            errors.append(f"{slug}: duplicate entries in {field}")
        if any(not re.fullmatch(r"[A-Za-z0-9_-]+", token) for token in tokens):
            errors.append(f"{slug}: {field} must contain filename suffixes without extensions")
        return tokens

    photos = selection("image_order")
    making = selection("process_image_order")
    if not photos:
        errors.append(f"{slug}: image_order must explicitly list product photos")
    if set(photos) & set(making):
        errors.append(f"{slug}: product and Making selections overlap")
    if "cover" in making:
        errors.append(f"{slug}: cover cannot be a Making photo")
    expected = {f"{slug}-{token}" for token in photos + making} | {f"{slug}-cover"}
    # Match the legacy renderer's prefixes, including underscore variants.
    prefixes = (slug.lower(), slug.replace("-", "_").lower())
    for size in ("1200px", "2500px", "large"):
        folder = Path(root) / "assets/images" / size
        found = [p for p in folder.glob("*") if p.is_file()
                 and p.suffix.lower() in IMAGE_EXTENSIONS
                 and p.name.lower().startswith(prefixes)]
        actual = {p.stem for p in found}
        extras = sorted(p.name for p in found if p.stem not in expected)
        if extras:
            errors.append(f"{slug}: unselected images in {size}: " + ", ".join(extras))
        if size != "large":
            missing = sorted(expected - actual)
            if missing:
                errors.append(f"{slug}: missing images in {size}: " + ", ".join(missing))
            if cover and not (folder / cover).is_file():
                errors.append(f"{slug}: explicitly named cover file missing in {size}: {cover}")
    return errors


def validate_gallery_images(items, root):
    errors = []
    for item in items:
        policy = item.get("image_selection_policy", "")
        if policy == "explicit":
            errors.extend(validate_image_selection(item, root))
        elif policy:
            errors.append(f"{item['slug']}: unknown image_selection_policy: {policy}")
        # Existing records without a policy retain their established rendering.
        # tools_import_csv.py makes explicit selection mandatory for new records.
    if errors:
        raise ValueError("Gallery image selection needs confirmation:\n" + "\n".join(errors))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", default="")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    items = json.loads((root / "assets/data/items.json").read_text())
    if args.slug:
        items = [item for item in items if item["slug"] == args.slug]
        if not items:
            parser.error("slug not found")
        # A requested individual audit must never silently skip a legacy record.
        items = [dict(item, image_selection_policy="explicit") for item in items]
    try:
        validate_gallery_images(items, root)
    except ValueError as error:
        parser.exit(2, str(error) + "\n")
    print("Gallery image selection check passed")
