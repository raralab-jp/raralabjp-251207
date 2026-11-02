"""Bounded note RSS snapshots. No browser-time requests or third-party scripts."""
import contextlib
import hashlib
import html
import io
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime
from PIL import Image

FEED = 'https://note.com/awaifacets/rss'
MAX_RSS = 512 * 1024
MAX_IMAGE = 5 * 1024 * 1024
MAX_PIXELS = 16_000_000
DEADLINE = 15
MEDIA = '{http://search.yahoo.com/mrss/}thumbnail'

class Invalid(ValueError):
    pass


def url_ok(url, image=False):
    if not isinstance(url, str) or len(url) > 2048 or any(ord(c) < 33 for c in url):
        raise Invalid('Invalid URL')
    p = urllib.parse.urlsplit(url)
    host = 'assets.st-note.com' if image else 'note.com'
    if p.scheme != 'https' or p.hostname != host or p.username or p.password or p.port not in (None, 443) or p.fragment:
        raise Invalid('URL is outside allowed origin')
    if image:
        if not p.path.startswith('/production/uploads/images/'):
            raise Invalid('Invalid thumbnail path')
    elif not re.fullmatch(r'/awaifacets/n/n[a-zA-Z0-9]+', p.path) or p.query:
        raise Invalid('Invalid article path')
    return url


class Redirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, validator):
        self.validator = validator
        self.count = 0
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.count += 1
        if self.count > 2:
            raise Invalid('Too many redirects')
        self.validator(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, limit, deadline, image=False):
    if image:
        validator = lambda u: url_ok(u, True)
    else:
        def validator(u):
            if u not in (FEED, FEED + '/'):
                raise Invalid('RSS redirect outside fixed endpoint')
    validator(url)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('note update deadline')
    opener = urllib.request.build_opener(Redirects(validator))
    req = urllib.request.Request(url, headers={'User-Agent':'awai-facets-static-feed/1.0', 'Accept-Encoding':'identity'})
    with opener.open(req, timeout=min(3, remaining)) as response:
        if response.status != 200:
            raise Invalid('HTTP failure')
        content_type = response.headers.get_content_type()
        if image and content_type not in ('image/jpeg', 'image/png', 'image/webp'):
            raise Invalid('Invalid image content type')
        if not image and content_type not in ('application/rss+xml','application/xml','text/xml'):
            raise Invalid('Invalid RSS content type')
        length = response.headers.get('Content-Length')
        if length and int(length) > limit:
            raise Invalid('Response too large')
        result = bytearray()
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError('note update deadline')
            chunk = response.read(min(32768, limit + 1 - len(result)))
            if not chunk:
                break
            result.extend(chunk)
            if len(result) > limit:
                raise Invalid('Response too large')
        if time.monotonic() > deadline:
            raise TimeoutError('note update deadline')
        return bytes(result)


def parse_rss(raw):
    if len(raw) > MAX_RSS:
        raise Invalid('RSS too large')
    # Strict UTF-8 prevents UTF-16 hiding a DTD from the declaration check.
    text = raw.decode('utf-8-sig')
    if re.search(r'<!\s*(DOCTYPE|ENTITY)', text, re.I):
        raise Invalid('DTD/entities are forbidden')
    root = ET.fromstring(text)
    if root.tag != 'rss' or root.get('version') != '2.0':
        raise Invalid('Expected RSS 2.0')
    channel = root.find('channel')
    if channel is None or channel.findtext('link') != 'https://note.com/awaifacets':
        raise Invalid('Unexpected feed owner')
    nodes = channel.findall('item')
    if not nodes or len(nodes) > 100:
        raise Invalid('Empty or oversized feed')
    records = {}
    for node in nodes:
        title = (node.findtext('title') or '').strip()
        if not title or len(title) > 300 or any(ord(c) < 32 for c in title):
            raise Invalid('Missing or invalid title')
        url = url_ok((node.findtext('link') or '').strip())
        dt = parsedate_to_datetime(node.findtext('pubDate') or '')
        if dt.tzinfo is None:
            raise Invalid('Missing timezone')
        thumb = (node.findtext(MEDIA) or '').strip()
        if thumb:
            url_ok(thumb, True)
        rec = {'id': url.rsplit('/',1)[1], 'title': title, 'url':url,
               'published':dt.isoformat(), 'thumbnail':thumb}
        if url in records and records[url] != rec:
            raise Invalid('Conflicting duplicate')
        records[url] = rec
    return sorted(records.values(), key=lambda r:(datetime.fromisoformat(r['published']).timestamp(),r['url']), reverse=True)[:3]


def reencode(raw):
    if not raw or len(raw) > MAX_IMAGE:
        raise Invalid('Image byte limit')
    with Image.open(io.BytesIO(raw)) as im:
        if im.format not in ('JPEG','PNG','WEBP') or im.width * im.height > MAX_PIXELS:
            raise Invalid('Image format/pixel limit')
        if getattr(im, 'n_frames', 1) != 1:
            raise Invalid('Animated image not supported')
        im.load()
        im = im.convert('RGB')
        im.thumbnail((960,640))
        output = io.BytesIO()
        im.save(output, 'WEBP', quality=82, method=4)
        return output.getvalue()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode()


def atomic(path, data):
    tmp = path.with_name(path.name + '.tmp')
    with open(tmp, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def validate_snapshot(base, data):
    if data.get('schema') != 1 or not 1 <= len(data.get('articles',[])) <= 3:
        raise Invalid('Invalid snapshot')
    urls = set()
    for r in data['articles']:
        url_ok(r['url'])
        if r['url'] in urls or not isinstance(r['title'],str) or not 1 <= len(r['title']) <= 300:
            raise Invalid('Duplicate or invalid title')
        urls.add(r['url'])
        __import__('datetime').datetime.fromisoformat(r['published'])
        image = r.get('image')
        if image is not None:
            if not re.fullmatch(r'images/[0-9a-f]{64}\.webp', image):
                raise Invalid('Invalid local image path')
            p = base/image
            if p.is_symlink() or not p.is_file() or digest(p.read_bytes()) != r['image_sha256'] or p.stem != r['image_sha256']:
                raise Invalid('Missing or changed snapshot image')
    body = {'schema':1,'articles':data['articles']}
    if digest(encode(body)) != data.get('generation'):
        raise Invalid('Generation mismatch')
    return data


def load(root):
    base = Path(root)/'assets/note'
    paths = [base/'current.json']
    backups = Path(root)/'_work/note/backups'
    if backups.exists():
        paths += sorted(backups.glob('*.json'), key=lambda p:p.stat().st_mtime_ns, reverse=True)
    for p in paths:
        if not p.exists():
            continue
        try:
            if p.is_symlink() or p.stat().st_size > MAX_RSS:
                raise Invalid('Invalid snapshot file')
            return validate_snapshot(base,json.loads(p.read_bytes()))
        except (OSError,ValueError,KeyError,TypeError):
            continue
    return None


def refresh(root, offline=False, fetcher=fetch, before_promote=None):
    root = Path(root)
    if offline:
        return load(root), 'offline: retained snapshot'
    work = root/'_work/note'
    lock = work/'update.lock'
    try:
        work.mkdir(parents=True,exist_ok=True)
        lock.mkdir()
    except FileExistsError:
        return load(root), 'warning: note update lock exists (_work/note/update.lock); retained snapshot; see README lock recovery'
    except OSError:
        return load(root), 'warning: note staging unavailable; retained snapshot'
    candidate = None
    try:
        atomic(lock/'owner.json',encode({'pid':os.getpid(),'started_at':time.time()}))
        atomic(work/'status.json',encode({'state':'updating'}))
        deadline = time.monotonic()+DEADLINE
        records = parse_rss(fetcher(FEED,MAX_RSS,deadline,False))
        import tempfile
        candidate = Path(tempfile.mkdtemp(prefix='candidate-',dir=work))
        articles = []
        for r in records:
            article = {k:v for k,v in r.items() if k!='thumbnail'}
            article.update(image=None,image_sha256=None)
            if r['thumbnail']:
                image = reencode(fetcher(r['thumbnail'],MAX_IMAGE,deadline,True))
                sha = digest(image)
                rel = 'images/'+sha+'.webp'
                (candidate/'images').mkdir(exist_ok=True)
                (candidate/rel).write_bytes(image)
                article.update(image=rel,image_sha256=sha)
            articles.append(article)
        data = {'schema':1,'articles':articles}
        data['generation'] = digest(encode(data))
        validate_snapshot(candidate,data)
        base = root/'assets/note'
        (base/'images').mkdir(parents=True,exist_ok=True)
        for r in articles:
            if r['image']:
                target = base/r['image']
                if target.exists() and digest(target.read_bytes()) != r['image_sha256']:
                    raise Invalid('Existing immutable image mismatch')
                if not target.exists():
                    atomic(target,(candidate/r['image']).read_bytes())
        validate_snapshot(base,data)
        current = base/'current.json'
        if current.exists():
            old = load(root)
            if old:
                backups = work/'backups'
                backups.mkdir(exist_ok=True)
                atomic(backups/(old['generation']+'.json'),encode(old))
        if before_promote:
            before_promote()
        atomic(current,encode(data))
        atomic(work/'status.json',encode({'state':'success','generation':data['generation'],'completed_at':time.time()}))
        return data, 'updated: '+data['generation'][:12]
    except (OSError,ValueError,KeyError,TypeError,ET.ParseError,Image.DecompressionBombError) as error:
        with contextlib.suppress(OSError):
            atomic(work/'status.json',encode({'state':'failed'}))
        # Do not print remote content, redirect URLs, or arbitrary exception bodies.
        return load(root), 'warning: note refresh failed ('+type(error).__name__+'); retained snapshot'
    finally:
        if candidate:
            import shutil
            shutil.rmtree(candidate)
        with contextlib.suppress(OSError):
            (lock/'owner.json').unlink()
        with contextlib.suppress(OSError):
            lock.rmdir()


def render(data):
    link = '<a href="https://note.com/awaifacets">noteの記事一覧を見る</a>'
    if not data:
        return '<section class="top-section top-note"><h2 class="section-doubleline">Journal</h2><p class="note-more">'+link+'</p></section>'
    cards = []
    for r in data['articles']:
        image = ('<img src="/assets/note/'+html.escape(r['image'],quote=True)+'" alt="" width="960" height="640" loading="lazy" decoding="async">') if r['image'] else '<span class="note-placeholder" aria-hidden="true">awai facets</span>'
        cards.append('<article class="note-card"><a href="'+html.escape(url_ok(r['url']),quote=True)+'"><div class="note-thumb">'+image+'</div><h3>'+html.escape(r['title'])+'</h3><time datetime="'+html.escape(r['published'],quote=True)+'">'+html.escape(r['published'][:10])+'</time></a></article>')
    return '<section class="top-section top-note"><h2 class="section-doubleline">Journal</h2><div class="note-cards">'+''.join(cards)+'</div><p class="note-more">'+link+'</p></section>'


def transfer(source_root, target_root, expected_generation, use_candidate=False, candidate_generation=None):
    """Explicit note-only transfer. Existing published snapshot wins on refresh failure.

    Caller must set use_candidate only for an explicitly selected successful snapshot against the
    recorded published generation. Never infer freshness from article dates.
    No deletes, Git operations or whole-site copies.
    """
    import shutil
    source_root, target_root = Path(source_root), Path(target_root)
    target = load(target_root)
    if (target_root/'assets/note/current.json').exists() and target is None:
        raise Invalid('Published snapshot is corrupt; manual reconciliation required')
    actual = target['generation'] if target else None
    if actual != expected_generation:
        raise Invalid('Published baseline changed; rebase note-only transfer')
    if use_candidate:
        try:
            receipt = json.loads((source_root/'_work/note/status.json').read_bytes())
            candidate = load(source_root)
            if candidate_generation is not None and (not candidate or candidate['generation'] != candidate_generation):
                raise Invalid('Reviewed candidate generation changed')
            if receipt.get('state') != 'success' or not candidate or receipt.get('generation') != candidate['generation']:
                raise Invalid('No matching successful refresh; retain published snapshot')
        except (OSError,KeyError,TypeError,ValueError) as error:
            raise Invalid('No matching successful refresh; retain published snapshot') from error
    data = load(source_root) if use_candidate else (target or load(source_root))
    if not data:
        return None, []
    origin = source_root if use_candidate or not target else target_root
    if target and data['generation'] != target['generation']:
        backups = target_root/'_work/note/backups'
        backups.mkdir(parents=True, exist_ok=True)
        atomic(backups/(target['generation']+'.json'),encode(target))
    # Validate before preparing any target changes; allowlist is derived locally.
    validate_snapshot(origin/'assets/note',data)
    writes = []
    for prefix in ('assets/note','site/assets/note'):
        base = target_root/prefix
        (base/'images').mkdir(parents=True,exist_ok=True)
        for r in data['articles']:
            if r['image']:
                dest = base/r['image']
                payload = (origin/'assets/note'/r['image']).read_bytes()
                if dest.exists() and digest(dest.read_bytes()) != r['image_sha256']:
                    raise Invalid('Target immutable image conflict')
                if not dest.exists():
                    atomic(dest,payload); writes.append(str(dest.relative_to(target_root)))
        validate_snapshot(base,data)
        if not (base/'current.json').exists() or (base/'current.json').read_bytes()!=encode(data):
            atomic(base/'current.json',encode(data)); writes.append(str((base/'current.json').relative_to(target_root)))
    return data,writes


def insert_section(page, data):
    start, end = '<!-- note-feed:start -->','<!-- note-feed:end -->'
    if start in page or end in page:
        if page.count(start)!=1 or page.count(end)!=1:
            raise Invalid('Ambiguous note section')
        a,b=page.index(start),page.index(end)+len(end)
    else:
        legacy = '<section class="top-more">'
        if page.count(legacy)!=1:
            raise Invalid('Expected one original note section')
        a=page.index(legacy)
        b=page.index('</section>',a)+len('</section>')
        if page[a:b].count('<section')!=1 or 'https://note.com/awaifacets' not in page[a:b]:
            raise Invalid('Unexpected original note section')
    return page[:a]+start+'\n'+render(data)+'\n'+end+page[b:]
