"""Regression checks for the page number expression shipped to browsers.

Runs the actual JavaScript expression with Node.js or macOS JavaScriptCore.
No site build, dependencies, or source writes are needed.
"""
import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'assets/js/gallery-filter.js'
JSC = Path('/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc')


class GalleryFilterTests(unittest.TestCase):
    def page_numbers(self, paths):
        expression = re.search(r'^  const page = (.+);$', SOURCE.read_text(), re.M).group(1)
        runtime = shutil.which('node') or (str(JSC) if JSC.is_file() else None)
        if runtime is None:
            self.skipTest('Node.js or macOS JavaScriptCore required')
        script = ('const paths = ' + json.dumps(paths) + ';'
                  'const result = paths.map(pathname => {'
                  'const location = {pathname}; return ' + expression + ';});'
                  '(typeof print === "function" ? print : console.log)(JSON.stringify(result));')
        return json.loads(subprocess.check_output([runtime, '-e', script], text=True))

    def test_generated_and_extensionless_gallery_routes(self):
        paths = ['/gallery/', '/gallery/index.html', '/gallery']
        expected = [1, 1, 1]
        for page in (2, 3, 10):
            for suffix in ('', '.html', '/', '.html/'):
                paths.append(f'/gallery/page-{page}{suffix}')
                expected.append(page)
        self.assertEqual(self.page_numbers(paths), expected)

    def test_unrelated_or_malformed_paths_do_not_match(self):
        paths = ['/gallery/not-page-2.html', '/gallery/product-page-2.html',
                 '/other/page-2.html', '/prefix/gallery/page-2',
                 '/gallery/page-2.html/extra', '/gallery/page-2extra',
                 '/gallery/page-2.htm', '/gallery/page-02', '/gallery/page-0',
                 '/gallery/page--2', '/gallery/page-2//', '/gallery/page-2%2F',
                 '/gallery/<page-2.html>', '/gallery/PAGE-2.html']
        self.assertEqual(self.page_numbers(paths), [1] * len(paths))

    def test_published_script_matches_source(self):
        self.assertEqual(SOURCE.read_bytes(),
                         (ROOT / 'site/assets/js/gallery-filter.js').read_bytes())


if __name__ == '__main__':
    unittest.main()
