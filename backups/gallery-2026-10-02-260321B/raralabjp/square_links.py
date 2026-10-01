"""Square rich-text navigation. Preserve source URLs; never infer missing URLs."""
import html
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit

INTRO = '詳しい写真や動画、制作過程をご覧いただけます。'
LABELS = {'gallery': 'ギャラリーを見る →', 'note': 'noteを読む →'}
OLD_INTROS = {
    INTRO,
    '自然光で撮影した写真と動画は、公式サイトのギャラリーでご覧いただけます。',
    '写真と動画は、公式サイトのギャラリーでご覧いただけます。',
    '公式サイトのギャラリーページはこちらです。',
    'ギャラリーを見る', 'ギャラリーを見る →',
    'noteを読む', 'noteを読む →', 'この石の関連記事をnoteで読む →',
}


def validate_url(value):
    if not isinstance(value, str) or not value or any(c.isspace() for c in value):
        raise ValueError('Missing URL or whitespace in URL')
    p = urlsplit(value)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        raise ValueError('Expected an absolute HTTP(S) URL')
    return value


def link_html(url, label):
    """All newly maintained Square links use ordinary same-tab navigation."""
    validate_url(url)
    return '<a href="' + html.escape(url, quote=True) + '">' + html.escape(label, quote=False) + '</a>'


def navigation_html(gallery_url, note_url=''):
    validate_url(gallery_url)  # Required: do not silently omit the Gallery link.
    urls = [('gallery', gallery_url)]
    if note_url:
        urls.append(('note', validate_url(note_url)))
    return '<p>' + INTRO + '</p><p><br></p><p>' + '<br>'.join(
        link_html(url, LABELS[kind])
        for kind, url in urls) + '</p><p><br></p><p><br></p>'


def text_html(text):
    """Encode literal product copy without interpreting it as markup."""
    return '<p>' + html.escape(text, quote=False).replace('\n', '<br>') + '</p>'


class Fragment(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.links = []
        self.feed(source)

    def handle_data(self, value):
        self.text.append(value)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.append(dict(attrs).get('href', ''))


def kind_of_url(url):
    p = urlsplit(url)
    if p.hostname in ('awaifacets.com', 'www.awaifacets.com', 'raralab.com', 'www.raralab.com') and p.path.startswith('/gallery/'):
        return 'gallery'
    if p.hostname == 'note.com':
        return 'note'
    return None


URL_RE = re.compile(r'https?://[^\s<>"\u3000]+')


def normalize_description(source):
    """Return (description, audit). Unknown/ambiguous navigation fails closed.

    HTML is edited using original paragraph spans, not DOM serialization, so all
    unrelated characters remain exact. Plain text is handled by full-line spans.
    """
    is_html = bool(re.search(r'<(?:p|div|a|br)\b', source, re.I))
    pattern = r'<p\b[^>]*>.*?</p>' if is_html else r'[^\r\n]+(?:\r?\n|$)'
    units = list(re.finditer(pattern, source, re.S | re.I))
    candidates = []
    urls = {'gallery': set(), 'note': set()}
    styles = set()
    for unit in units:
        raw = unit.group()
        parsed = Fragment(raw)
        visible = ''.join(parsed.text).strip() if is_html else raw.strip()
        found = []
        for url in parsed.links + URL_RE.findall(html.unescape(visible)):
            # Markdown target ends with ')' and is parsed separately below.
            if not is_html and '](' in visible:
                url = url.rstrip(')')
            kind = kind_of_url(url)
            if kind:
                validate_url(url)
                urls[kind].add(url)
                found.append(url)
        if found:
            candidates.append(unit)
            styles.add('visible_url' if any(u in visible for u in found) else 'embedded')
        elif visible in OLD_INTROS:
            candidates.append(unit)
    full = Fragment(source)
    for url in full.links + URL_RE.findall('\n'.join(full.text)):
        if not is_html and '](' in source:
            url = url.rstrip(')')
        kind = kind_of_url(url)
        if kind and url not in urls[kind]:
            raise ValueError('Navigation outside supported paragraph/line boundaries')
    if not any(urls.values()):
        if candidates or re.search(r'gallery/|ギャラリー|note\.com|noteを読む', source, re.I):
            raise ValueError('Navigation text without a recoverable URL')
        return source, {'status': 'no_navigation', 'edits': []}
    if len(urls['gallery']) != 1 or len(urls['note']) > 1:
        raise ValueError('Missing or conflicting Gallery/note URLs')
    gallery = next(iter(urls['gallery']))
    note = next(iter(urls['note']), '')
    # A link paragraph may contain only recognized labels, URLs and the intro.
    # Never drop product copy that happens to share a paragraph with a link.
    for unit in candidates:
        raw = unit.group()
        visible = ''.join(Fragment(raw).text).strip() if is_html else raw.strip()
        residue = visible
        for value in sorted([*OLD_INTROS, gallery, note], key=len, reverse=True):
            if value:
                residue = residue.replace(value, '')
        if residue.strip(' \t\r\n[]()'):
            raise ValueError('Unrecognized text in navigation paragraph: ' + residue)
        if any(kind_of_url(u) is None for u in Fragment(raw).links):
            raise ValueError('Unrelated link shares navigation paragraph')
    # Only navigation and its adjoining blank paragraphs are layout-owned.
    # Body text between link paragraphs is ambiguous and must never be moved.
    start, end = candidates[0].start(), candidates[-1].end()
    blank_html = r'(?:\s|<p\b[^>]*>(?:\s|&nbsp;|&#160;|<br\s*/?>)*</p>)*'
    if is_html:
        for left, right in zip(candidates, candidates[1:]):
            if not re.fullmatch(blank_html, source[left.end():right.start()], re.I):
                raise ValueError('Body text between navigation paragraphs')
        end += re.match(blank_html, source[end:], re.I).end()
    else:
        for left, right in zip(candidates, candidates[1:]):
            if source[left.end():right.start()].strip():
                raise ValueError('Body text between navigation lines')
        end += len(source[end:]) - len(source[end:].lstrip('\r\n'))
    edits = [(start, end, navigation_html(gallery, note))]
    # All characters outside this bounded layout span remain exact.
    result = source
    for start, end, replacement in reversed(edits):
        result = result[:start] + replacement + result[end:]
    return result, {'status': 'normalized', 'gallery_url': gallery, 'note_url': note,
                    'styles': sorted(styles), 'edits': edits}


def finalize_description(source, sku=''):
    """Normalize navigation and apply only the two explicitly reviewed link repairs.

    SKU and exact source fragments bound the exception scope. Unknown content
    fails closed; unrelated anchors and body whitespace remain unchanged.
    """
    result, audit = normalize_description(source)
    repairs = []
    if sku == 'H319273':
        url = 'http://www.facetdiagrams.org/database/files/pc30117.html'
        old = 'ファセットデザインはこちら &gt; <a href="' + url + '" target="_blank" rel="noreferrer noopener nofollow">' + url + '</a>'
        new = link_html(url, 'ファセットデザインはこちら >')
        # Square may encode the literal greater-than sign either way.
        variants = (old, old.replace('&gt;', '>'))
        if sum(result.count(v) for v in variants) == 1:
            for v in variants:
                result = result.replace(v, new, 1)
            repairs.append('embed_design_reference_same_tab')
        elif result.count(new) != 1:
            raise ValueError('Unexpected design-reference fragment for ' + sku)
    elif sku == '241208G':
        url = 'https://customer-jnhhy169io6el95i.cloudflarestream.com/c8ddaebec9b87a0e7e98541a64852f39/watch'
        opening = '<a href="' + url + '" rel="noopener noreferrer nofollow" target="_blank">'
        old = opening + '動画はこちらからご覧いただけます</a>' + opening + '。</a>'
        new = link_html(url, '動画はこちらからご覧いただけます。')
        if result.count(old) == 1:
            result = result.replace(old, new, 1)
            repairs.append('merge_video_sentence_same_tab')
        elif result.count(new) != 1:
            raise ValueError('Unexpected split-video fragment for ' + sku)
    audit['review_repairs'] = repairs
    return result, audit
