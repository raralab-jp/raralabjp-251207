"""Idempotently include opt-in analytics in published HTML; leave content intact."""
from pathlib import Path
TAG = '<script defer src="/assets/js/analytics-consent.js?v=20261115"></script>'
def install(site_root):
    count = 0
    for path in Path(site_root).rglob('*.html'):
        if 'assets' in path.relative_to(site_root).parts:
            continue
        text = path.read_text(encoding='utf-8')
        if '/assets/js/analytics-consent.js' in text or '</body>' not in text:
            continue
        path.write_text(text.replace('</body>', TAG + '\n</body>', 1), encoding='utf-8')
        count += 1
    return count
if __name__ == '__main__':
    print(install(Path(__file__).parent / 'site'))
