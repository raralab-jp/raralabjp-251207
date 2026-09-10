import csv
import importlib.util
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tools_validate_gallery_images import validate_gallery_images


class GalleryValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.item = dict(slug="sample", image_selection_policy="explicit",
                         cover_image="sample-cover.jpg", image_order="one two",
                         process_image_order="making")
        for size in ("1200px", "2500px"):
            folder = self.root / "assets/images" / size
            folder.mkdir(parents=True)
            for stem in ("cover", "one", "two", "making"):
                (folder / f"sample-{stem}.jpg").touch()

    def test_explicit_selection_accepts_jpg_webp_pair(self):
        (self.root / "assets/images/1200px/sample-one.webp").touch()
        validate_gallery_images([self.item], self.root)

    def test_unselected_image_fails_in_either_size_or_generated_large(self):
        for size in ("1200px", "2500px", "large"):
            with self.subTest(size=size):
                folder = self.root / "assets/images" / size
                folder.mkdir(exist_ok=True)
                extra = folder / "sample-unselected.jpg"
                extra.touch()
                with self.assertRaisesRegex(ValueError, "sample-unselected.jpg"):
                    validate_gallery_images([self.item], self.root)
                extra.unlink()

    def test_missing_explicit_cover_never_falls_back(self):
        for change in ({"cover_image": ""}, {"cover_image": "sample-one.jpg"}):
            with self.assertRaisesRegex(ValueError, "cover_image"):
                validate_gallery_images([dict(self.item, **change)], self.root)
        (self.root / "assets/images/2500px/sample-cover.jpg").unlink()
        with self.assertRaisesRegex(ValueError, "cover file missing"):
            validate_gallery_images([self.item], self.root)

    def test_missing_duplicate_and_overlapping_selections_fail(self):
        for change in ({"image_order": "one two absent"},
                       {"image_order": "one one two"},
                       {"process_image_order": "one making"}):
            with self.assertRaises(ValueError):
                validate_gallery_images([dict(self.item, **change)], self.root)

    def test_build_stops_before_any_generation(self):
        # Loading the module does not run its __main__ entry point.
        module = runpy.run_path(str(ROOT / "build.py"))
        build = module["build"]
        (self.root / "assets/images/1200px/sample-extra.jpg").touch()
        with patch.dict(build.__globals__, ROOT=self.root,
                        read_items=lambda: [self.item],
                        build_site_css=lambda: self.fail("CSS generation ran")):
            with self.assertRaisesRegex(ValueError, "sample-extra.jpg"):
                build()

    def test_import_preserves_decimal_text_and_unrelated_records(self):
        data = self.root / "assets/data"
        data.mkdir()
        original = {"slug": "existing", "carat": 1.2, "date": "2020-01-01", "custom": "keep"}
        (data / "items.json").write_text(json.dumps([original]))
        for carat in ("0.370", "0.280", "1.200", "1.2", "0.2800"):
            with self.subTest(carat=carat):
                with (data / "items.csv").open("w") as f:
                    writer = csv.DictWriter(f, fieldnames=["slug", "carat", "date"])
                    writer.writeheader()
                    writer.writerow(dict(slug="existing", carat="999", date="2020-01-01"))
                    writer.writerow(dict(slug="sample", carat=carat, date="2026-09-10"))
                subprocess.run([sys.executable, "-B", str(ROOT / "tools_import_csv.py"),
                                "--slug", "sample"], cwd=self.root, check=True, capture_output=True)
                result = {r["slug"]: r for r in json.loads((data / "items.json").read_text())}
                self.assertEqual(result["existing"], original)
                self.assertEqual(result["sample"]["carat"], carat)
                self.assertEqual(result["sample"]["image_selection_policy"], "explicit")
                # No named cover in the CSV means no automatic cover choice.
                self.assertEqual(result["sample"]["cover_image"], "")
                with self.assertRaisesRegex(ValueError, "cover_image"):
                    validate_gallery_images([result["sample"]], self.root)


if __name__ == "__main__":
    unittest.main()
