"""Independent check: the letters and digits of every section file equal those of its source page.

    python -X utf8 check_words.py <repo> [--pages <folder of retrieved pages>]

Shares no code with parse.py. For each section page listed in the repository's tools/sources-sha256.json, it reads
the retrieved page (named by the sha256 of its URL), checks its sha256, strips the markup with a regular expression,
and compares the multiset of letters and digits with that of the file the page should have become (worked out from
the URL alone). Exit status 1 on any difference.
"""
from __future__ import annotations

import collections
import hashlib
import html
import json
import os
import re
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1])
pages = Path(sys.argv[sys.argv.index('--pages') + 1]) if '--pages' in sys.argv else Path(
    os.environ.get('AZ_PAGES', Path(__file__).resolve().parent / '.cache'))
ALNUM = re.compile(r'[A-Za-z0-9]')


def file_for(url: str) -> str | None:
    m = re.search(r'/ars/(\d+)/0*(\d+)((?:-\d+)*)([A-Za-z]?)(?:\.(\d+))?\.htm$', url)
    if m:
        ver = f'-version-{int(m.group(5)) + 1}' if m.group(5) else ''
        return f'title-{m.group(1)}/{m.group(1)}-{m.group(2)}{m.group(3)}{m.group(4).lower()}{ver}.md'
    m = re.search(r'/ars/(\d+)/(\d+[A-Za-z]\d+)\.htm$', url)          # U.C.C. 47-2A101 -> 47-2a101.md
    if m:
        return f'title-{m.group(1)}/{m.group(1)}-{m.group(2).lower()}.md'
    if url.endswith('/const/preamble.htm'):
        return 'constitution-preamble/preamble.md'
    m = re.search(r'/const/(\d+)((?:\.\d+)?)/(\d+)((?:_\d+)*)([A-Za-z]?)(?:\.p(\d+)|\.(\d+))?\.htm$', url)
    if m:
        art = f'constitution-article-{int(m.group(1)):02d}' + m.group(2).replace('.', '-')
        sec = (f'part-{m.group(6)}-' if m.group(6) else '') + f'section-{int(m.group(3)):02d}' + m.group(4).replace('_', '-') + (f'-{m.group(5).lower()}' if m.group(5) else '') + (f'-version-{m.group(7)}' if m.group(7) else '')
        return f'{art}/{sec}.md'
    return None


def page_chars(raw: bytes) -> collections.Counter:
    t = raw.decode('utf-8', errors='replace')
    t = re.sub(r'<head.*?</head>', ' ', t, flags=re.S | re.I)
    t = re.sub(r'<!--.*?-->|<![^>]*>', ' ', t, flags=re.S)
    t = re.sub(r'<[^>]+>', ' ', t)
    return collections.Counter(ALNUM.findall(html.unescape(t)))


def main() -> None:
    listed = json.loads(subprocess.run(['git', 'show', 'HEAD:tools/sources-sha256.json'], cwd=repo,
                                       capture_output=True, check=True).stdout)
    total = missing = extra = files = unpublished = 0
    bad = []
    seen = set()
    for r in listed:
        f = file_for(r['url'])
        if f is None:
            continue           # index pages
        raw = (pages / hashlib.sha256(r['url'].encode()).hexdigest()).read_bytes()
        if hashlib.sha256(raw).hexdigest() != r['sha256']:
            bad.append(f'{r["url"]}: sha256 differs from the record')
            continue
        want = page_chars(raw)
        p = repo / f
        if f.startswith('title-'):      # sections sit in chapter folders: title-13-chapter-NN/13-101.md
            t, name = f.split('/')
            hits = sorted(repo.glob(f'{t}-chapter-*/{name}'))
            p = hits[0] if len(hits) == 1 else repo / f
        if not p.exists():
            unpublished += 1     # a page read for a part not (yet) in this record
            continue
        seen.add(p.relative_to(repo).as_posix())
        have = collections.Counter(ALNUM.findall(p.read_text(encoding='utf-8')))
        files += 1
        total += sum(want.values())
        lost, added = want - have, have - want
        missing += sum(lost.values())
        extra += sum(added.values())
        if lost or added:
            bad.append(f'{f}: missing {dict(lost)} extra {dict(added)}')
    # every law file of the record must have been checked against its page
    law = [f for f in subprocess.run(['git', 'ls-files'], cwd=repo, capture_output=True, text=True).stdout.split()
           if f.startswith(('title-', 'constitution-')) and f.endswith('.md') and not f.endswith('/README.md')]
    unchecked = sorted(set(law) - seen)
    bad += [f'{f}: in the record but no source page checked' for f in unchecked]
    print(f'{files} files, {total} letters and digits; missing {missing}, extra {extra}; '
          f'{len(unchecked)} law files unchecked; {unpublished} listed pages are for parts not in this record')
    for b in bad[:30]:
        print('  ' + b)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
