"""Arizona: the retrieved pages of the Arizona Legislature -> corpus.json for scripts/gitlaw_common/build.py.

    python -X utf8 parse.py --today YYYY-MM-DD [--acts constitution,title-13,...]

Reads only the retrieved pages (the folder named by AZ_PAGES, by default the folder of retrieved pages next to this file), each named by the
sha256 of its URL. Deterministic: the same pages give the same bytes. The Legislature publishes the current text
only, with no history notes, so each act has one version, dated by the day its pages were retrieved and
credited to the publisher as the oldest version available.

Writes corpus.json (country, sources, the acts) and sources-sha256.json (every page read, with its sha256).
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAGES = Path(os.environ.get('AZ_PAGES', HERE / '.cache'))
PENDING = HERE / '.pending'       # working copies of the lists, for parts not yet published
BASE = 'https://www.azleg.gov'
ORDER = ['constitution', 'title-13', 'title-33', 'title-10']
TITLES = {'13': 'Criminal Code', '33': 'Property', '10': 'Corporations and Associations'}


def page(url: str) -> bytes | None:
    p = PAGES / hashlib.sha256(url.encode()).hexdigest()
    if p.exists():
        return p.read_bytes()
    r = p.with_suffix('.redirect')
    return page(r.read_text()) if r.exists() else None


# ---------------------------------------------------------------- HTML -> lines

class Lines(HTMLParser):
    """One line per <p>, <br>, table row or heading; table cells joined by ' | '."""
    BLOCK = {'p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'tr', 'blockquote', 'center'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self.cur: list[str] = []
        self.cells: list[str] | None = None
        self.skip = 0
        self.body = False

    def flush(self):
        t = ''.join(self.cur)
        self.cur = []
        if self.cells is not None:
            if t.strip():
                self.cells.append(t)
            return
        self.lines.append(t)

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'title', 'head'):
            self.skip += 1
        elif tag == 'body':
            self.body = True
        elif tag == 'br':
            self.flush()
        elif tag == 'tr':
            self.flush()
            self.cells = []
        elif tag in ('td', 'th'):
            if self.cells is not None:
                self.flush()
        elif tag in self.BLOCK:
            self.flush()

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'title', 'head'):
            self.skip = max(0, self.skip - 1)
        elif tag == 'tr':
            self.flush()
            row = self.cells or []
            self.cells = None
            self.lines.append(' | '.join(norm(c) for c in row))
        elif tag in ('td', 'th'):
            if self.cells is not None:
                self.flush()
        elif tag in self.BLOCK:
            self.flush()

    def handle_data(self, data):
        if not self.skip:
            self.cur.append(data)


QUOTES = str.maketrans({'“': '"', '”': '"', '‘': "'", '’': "'", ' ': ' ', '‑': '-',
                        '­': '', '​': '', '\t': ' '})


def norm(s: str) -> str:
    return re.sub(r' {2,}', ' ', s.translate(QUOTES).replace('\r', ' ').replace('\n', ' ')).strip()


def lines_of(raw: bytes) -> list[str]:
    text = raw.decode('utf-8', errors='replace')
    text = re.sub(r'<!(?!--)[^>]*>', '', text)          # the <!Creation Date: ...> pseudo-comments
    p = Lines()
    p.feed(text)
    p.flush()
    return [l for l in (norm(x) for x in p.lines) if l]


# ---------------------------------------------------------------- the acts

def section_key(num: str) -> str:
    """The file name of a section, as cited: 13-101 -> 13-101; 13-3875.01 -> 13-3875-01 (no dots in file names)."""
    if not re.fullmatch(r'\d+-\d+(?:\.\d+)*[A-Z]?', num):
        raise SystemExit(f'unexpected section number {num}')
    return num.replace('.', '-').lower()


def unit_text(lines: list[str]) -> str:
    return ''.join(('# ' + l if i == 0 else l) + '\n' for i, l in enumerate(lines))


def chapter_slug(t: str, ch: str) -> str:
    """Title 13, chapter 7.1 -> title-13-chapter-07-1 (zero-padded, so folders sort in chapter order)."""
    a = ch.split('.')
    return f'title-{t}-chapter-{int(a[0]):02d}' + ''.join(f'-{x}' for x in a[1:])


def title_acts(t: str, read: list[dict], only_complete_prefix: bool) -> list[dict]:
    """One act per chapter of the title (folder title-<t>-chapter-NN), in the index's order. With
    only_complete_prefix, the chapters up to (not including) the first one whose pages are not all retrieved yet:
    a published record then only grows at its end."""
    idx_url = f'{BASE}/arsDetail/?title={t}'
    idx = page(idx_url)
    if idx is None:
        raise SystemExit(f'title {t}: index page not retrieved')
    read.append({'url': idx_url, 'sha256': hashlib.sha256(idx).hexdigest()})
    blocks = re.split(rb'<div id="chapter[^"]*" class="accordion">', idx)[1:]
    acts = []
    for b in blocks:
        m = re.search(rb'>Chapter ([0-9.]+)</a><div class="two-thirds">([^<]*)</div>', b)
        if not m:
            raise SystemExit(f'title {t}: a chapter block without a heading')
        ch, name = m.group(1).decode(), norm(html.unescape(m.group(2).decode()))
        urls = list(dict.fromkeys(re.findall(rf'https://www\.azleg\.gov/ars/{t}/[0-9A-Za-z_.\-]+\.htm'.encode(), b)))
        if not urls:
            continue                     # a chapter the index lists with no section of its own (repealed)
        if any(page(u.decode()) is None for u in urls):
            if only_complete_prefix:
                break
            if os.environ.get('AZ_ALLOW_PARTIAL') != '1':
                raise SystemExit(f'title {t} chapter {ch}: section pages not retrieved yet')
        units, pages = {}, [hashlib.sha256(idx).hexdigest()]
        start = len(read)
        for u in (x.decode() for x in urls):
            raw = page(u)
            if raw is None:
                continue
            read.append({'url': u, 'sha256': hashlib.sha256(raw).hexdigest()})
            pages.append(read[-1]['sha256'])
            ls = lines_of(raw)
            mm = re.match(r'(\d+-\d+(?:\.\d+)*[A-Z]?)\.\s*(.*)', ls[0]) if ls else None
            if not mm:
                raise SystemExit(f'{u}: no section heading: {ls[:1]}')
            num = mm.group(1)
            key = section_key(num)
            label = f'A.R.S. § {num}'
            v = re.search(r'/\d+(?:-\d+)*\.(\d+)\.htm$', u)
            if v:
                # A second text of the section (the index lists it as "13-1204; Version 2", the page itself says
                # "Version 1"); kept as printed, beside the first.
                key += f'-version-{int(v.group(1)) + 1}'
                label += f' (version {int(v.group(1)) + 1})'
            if key in units:
                raise SystemExit(f'{u}: section {num} twice')
            units[key] = {'label': label, 'kind': 'section', 'text': unit_text(ls)}
        acts.append({'slug': chapter_slug(t, ch), 'short': f'A.R.S. Title {t}, ch. {ch}',
                     'title': f'Arizona Revised Statutes, Title {t} ({TITLES[t]}), Chapter {ch} ({name.capitalize()})',
                     'url': idx_url, 'first_law': None, 'earlier_laws': [], 'units': units, '_pages': pages,
                     '_read': [{'url': idx_url, 'sha256': pages[0]}] + read[start:],
                     '_part': f'title-{t}-chapter-{ch}', '_of': len(blocks)})
    return acts


def const_sec_key(sec: str) -> str:
    """The file name of a section page -> unit key: 1 -> section-01, 2_1 -> section-02-1, 14A -> section-14-a,
    1.p2 -> part-2-section-01, 1.1 -> section-01-version-1 (the site prints a second version of a section that two
    measures amended differently, e.g. art. 5, § 1 "Version 1", "Version amended by 1992 Proposition 107")."""
    m = re.fullmatch(r'(\d+)((?:_\d+)*)([A-Za-z]*)(?:\.p(\d+)|\.(\d+))?', sec)
    if not m:
        raise SystemExit(f'unexpected constitution section file {sec}')
    return ((f'part-{m.group(4)}-' if m.group(4) else '') + f'section-{int(m.group(1)):02d}'
            + ''.join(f'-{x}' for x in m.group(2).split('_') if x) + (f'-{m.group(3).lower()}' if m.group(3) else '')
            + (f'-version-{m.group(5)}' if m.group(5) else ''))


def const_sec_label(sec: str) -> str:
    """1 -> § 1; 2_1 -> § 2.1; 1.p2 -> pt. 2, § 1; 1.1 -> § 1 (version 1)."""
    m = re.fullmatch(r'([0-9_A-Za-z]+)(?:\.p(\d+)|\.(\d+))?', sec)
    return ((f'pt. {m.group(2)}, ' if m.group(2) else '') + '§ ' + m.group(1).replace('_', '.')
            + (f' (version {m.group(3)})' if m.group(3) else ''))


def art_slug(art: str) -> str:
    a = art.split('.')
    return f'constitution-article-{int(a[0]):02d}' + ''.join(f'-{x}' for x in a[1:])


def constitution_acts(read: list[dict]) -> list[dict]:
    """The Constitution as one act per article (folder constitution-article-NN), plus the preamble."""
    idx_url = f'{BASE}/constitution/'
    idx = page(idx_url)
    read.append({'url': idx_url, 'sha256': hashlib.sha256(idx).hexdigest()})
    rows = re.findall(rb'href="constitution\?article=([0-9.]+)">[^<]*</a></td><td>([^<]*)</td>', idx)
    names = {a.decode(): norm(html.unescape(n.decode())) for a, n in rows}
    arts = sorted(names, key=lambda a: [int(x) for x in a.split('.')])
    acts, missing = [], []
    pre = f'{BASE}/const/preamble.htm'
    raw = page(pre)
    if raw is None:
        missing.append(pre)
    else:
        read.append({'url': pre, 'sha256': hashlib.sha256(raw).hexdigest()})
        acts.append({'slug': 'constitution-preamble', 'short': 'Ariz. Const. preamble',
                     'title': 'Constitution of the State of Arizona, Preamble', 'url': pre, 'first_law': None,
                     'earlier_laws': [], 'units': {'preamble': {'label': 'Ariz. Const. preamble', 'kind': 'preamble',
                                                                'text': unit_text(lines_of(raw))}},
                     '_pages': [read[-1]['sha256']], '_read': [read[0], read[-1]]})
    for a in arts:
        au = f'{BASE}/constitution/?article={a}'
        ap = page(au)
        if ap is None:
            missing.append(au)
            continue
        start = len(read)
        read.append({'url': au, 'sha256': hashlib.sha256(ap).hexdigest()})
        pages = [read[-1]['sha256']]
        # the article's own table of sections follows its <h2>Article N</h2>
        own = ap.split(f'<h2>Article {a}</h2>'.encode(), 1)[-1]
        urls = [u.decode() for u in dict.fromkeys(re.findall(
            rb'https://www\.azleg\.gov/const/' + re.escape(a.encode()) + rb'/[0-9A-Za-z_.]+\.htm', own))]
        units = {}
        for u in urls:
            raw = page(u)
            if raw is None:
                missing.append(u)
                continue
            read.append({'url': u, 'sha256': hashlib.sha256(raw).hexdigest()})
            pages.append(read[-1]['sha256'])
            sec = u.rsplit('/', 1)[1][:-4]
            key = const_sec_key(sec)
            if key in units:
                raise SystemExit(f'{u}: {key} twice')
            units[key] = {'label': f'Ariz. Const. art. {a}, {const_sec_label(sec)}', 'kind': 'section',
                          'text': unit_text(lines_of(raw))}
        acts.append({'slug': art_slug(a), 'short': f'Ariz. Const. art. {a}',
                     'title': f'Constitution of the State of Arizona, Article {a} ({names[a].capitalize()})',
                     'url': au, 'first_law': None, 'earlier_laws': [], 'units': units, '_pages': pages,
                     '_read': [read[0]] + read[start:]})
    if missing and os.environ.get('AZ_ALLOW_PARTIAL') != '1':
        raise SystemExit(f'constitution: {len(missing)} pages not retrieved yet')
    return acts


def add(acts: list[dict], act: dict, today: str, read: list[dict]) -> None:
    units = act.pop('units')
    read.extend(act.pop('_read', []))
    # one digest per act: the sha256 of the sha256s of the pages it was read from (each is in sources-sha256.json)
    own = act.pop('_pages')
    act['versions'] = [{'from': today, 'source_url': act['url'], 'sha256': hashlib.sha256(''.join(own).encode()).hexdigest(),
                        'units': dict(sorted(units.items())), 'credits': {},
                        'note': 'The current text as the Arizona Legislature publishes it; the source gives no dated past versions.'}]
    acts.append(act)
    print(f'{act["slug"]}: {len(units)} sections')


def write(path: Path, data) -> str:
    """Atomic write (another process may read the folder at any moment); returns the sha256."""
    b = (json.dumps(data, ensure_ascii=False, indent=1) + '\n').encode('utf-8')
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_bytes(b)
    os.replace(tmp, path)
    return hashlib.sha256(b).hexdigest()


def write_corpus_json(dated: dict) -> None:
    """corpus.json: the country, the source (retrieved: the latest day of a published part) and the decisions."""
    corpus = {
        'country': {
            'code': 'US-AZ', 'name': 'United States (Arizona)', 'slug': 'united-states-arizona', 'lang': 'en',
            'tz': 'America/Phoenix', 'future_branch': 'future',
            'publisher': {'name': 'Arizona Legislature', 'email': 'publisher@azleg.gov.invalid'},
            'default_in_force_rule': {
                'text': 'Ariz. Const. art. 4, pt. 1, § 1(3): an act takes effect ninety days after the close of the '
                        'session that passed it, unless it is an emergency measure or the act sets another date',
                'source': f'{BASE}/const/4/1.p1.htm'},
            'licence_note': 'Text from the Arizona Legislature (azleg.gov). Statutes carry no copyright: '
                            'Georgia v. Public.Resource.Org, Inc., 590 U.S. 255 (2020).',
        },
        'sources': [{'name': 'Arizona Legislature: Arizona Revised Statutes and Arizona Constitution', 'url': BASE,
                     'retrieved': max(dated.values()) if dated else '2026-10-30',
                     'licence': 'No copyright in the text of the law (Georgia v. Public.Resource.Org, Inc., 590 U.S. 255 (2020)).',
                     'notes': 'The online compilation is maintained by the Arizona Legislative Council for legislative '
                              'drafting; the official edition of the Arizona Revised Statutes is published by Thomson Reuters.'}],
        'laws': {},
        'acts': [],
        'applies': [],
        'decisions': [
            'The Legislature publishes the current text only, with no history notes, so each act has one version, '
            'dated by the day the pages were retrieved and credited to the publisher as the oldest version available.',
            'One file per section; one paragraph (each <p> or line break of the page) per line; table rows as cells '
            'joined by " | "; curly quotes made straight; no other change to the words.',
        ],
        'ai_use': ['none: the text, dates and credits come from the source pages by rule.'],
    }
    print('corpus.json sha256', write(HERE / 'corpus.json', corpus))


def publish_lists(everything: bool) -> None:
    """sources-sha256.json and acts-retrieved.json for the parts that are published (corpus.d/<part>.PUBLISH), or
    for every part with --all (a check build of parts not yet published)."""
    parts = sorted((HERE / 'corpus.d').glob('*.json'))
    if not everything:
        parts = [p for p in parts if p.with_suffix('.PUBLISH').exists()]
    pages, slugs = {}, set()
    for p in parts:
        d = json.loads(p.read_text(encoding='utf-8'))
        if 'pages' not in d:
            raise SystemExit(f'{p.name} has no page list')
        pages.update({r['url']: r for r in d['pages']})
        slugs |= {a['slug'] for a in d['acts']}
    src = PENDING / 'acts-retrieved.json'
    dated = json.loads(src.read_text(encoding='utf-8')) if src.exists() else {}

    def published(key: str) -> bool:
        if key == 'constitution':
            return any(s.startswith('constitution') for s in slugs)
        m = re.fullmatch(r'title-(\d+)-chapter-([0-9.]+)', key)
        return bool(m) and chapter_slug(m.group(1), m.group(2)) in slugs
    write(HERE / 'sources-sha256.json', [pages[u] for u in sorted(pages)])
    shown = {k: v for k, v in sorted(dated.items()) if published(k)}
    write(HERE / 'acts-retrieved.json', shown)
    write_corpus_json(shown)
    print(f'lists: {len(pages)} pages, {len(slugs)} acts from {len(parts)} parts')


def main() -> None:
    if '--publish-lists' in sys.argv:
        return publish_lists('--all' in sys.argv)
    ap = argparse.ArgumentParser()
    ap.add_argument('--today', required=True, help='the day the pages of any part not yet dated were retrieved')
    ap.add_argument('--part', required=True, help='constitution, or title-13 / title-33 / title-10')
    ap.add_argument('--prefix', action='store_true',
                    help='for titles: a new batch of the chapters after the last batch, up to the first chapter not '
                         'fully retrieved (so the published record only grows at its end)')
    a = ap.parse_args()
    parts = HERE / 'corpus.d'
    parts.mkdir(exist_ok=True)
    # Each part is dated by the day its pages were retrieved, kept in acts-retrieved.json so a later build that adds
    # a part leaves the earlier parts' commits as they were.
    # The working copy of the dates lives in .pending/ (not published); acts-retrieved.json and sources-sha256.json
    # beside this file are the published lists, written by --publish-lists for the parts marked PUBLISH only.
    dated_path = PENDING / 'acts-retrieved.json'
    dated = json.loads(dated_path.read_text(encoding='utf-8')) if dated_path.exists() else (
        json.loads((HERE / 'acts-retrieved.json').read_text(encoding='utf-8')) if (HERE / 'acts-retrieved.json').exists() else {})
    mine: list[dict] = []
    name = a.part
    if name == 'constitution':
        got, out = constitution_acts(mine), parts / '10-constitution.json'
    else:
        t = name.split('-', 1)[1]
        rank = {'13': 20, '33': 30, '10': 40}[t]
        done = set()
        earlier = sorted(parts.glob(f'{rank}-title-{t}-batch-*.json'))
        for p in earlier:
            done |= {x['slug'] for x in json.loads(p.read_text(encoding='utf-8'))['acts']}
        allc = title_acts(t, mine, only_complete_prefix=a.prefix)
        got = [x for x in allc if x['slug'] not in done]
        if a.prefix and not got:
            print(f'{name}: no new complete chapter after the {len(done)} already in batches')
            return
        out = parts / f'{rank}-title-{t}-batch-{len(earlier) + 1:02d}.json'
        print(f'{name}: batch {out.name}: {len(got)} chapters ({got[0]["short"] if got else "-"} to '
              f'{got[-1]["short"] if got else "-"}), {len(done)} in earlier batches')
    acts, used = [], []
    for act in got:
        part = act.pop('_part', name)
        act.pop('_of', None)
        day = dated.setdefault(part, a.today)
        if day > a.today:
            raise SystemExit(f'{part} is dated {day}, after --today {a.today}')
        add(acts, act, day, used)
    pages = {r['url']: r for r in used}
    print(out.name, 'sha256', write(out, {'acts': acts, 'pages': [pages[u] for u in sorted(pages)]}))
    write(dated_path, dict(sorted(dated.items())))



if __name__ == '__main__':
    main()
