"""Writes the static docs in repo/ (README.md, LICENSE, corpus.json) from corpus.json, before the shared build runs.

    python -X utf8 docs.py --today YYYY-MM-DD

Every file goes through the publish gate first.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.append(str(HERE.parent / 'gitlaw_common'))
try:
    from publish_gate import publish_gate
except ImportError:          # an outside reader rebuilding from the published tools: no private rule to apply
    if os.environ.get('GITLAW_PUBLIC_REBUILD') != '1':
        raise SystemExit('publish gate missing: run from lexifina/scripts, or set GITLAW_PUBLIC_REBUILD=1')

    def publish_gate(files): return files

REUSE = ('The text of the law carries no copyright: under the government edicts doctrine (Georgia v. '
         'Public.Resource.Org, Inc., 590 U.S. 255 (2020)) nobody owns works made by legislators in their official '
         'capacity, which covers the statutes and the Constitution the Arizona Legislature publishes.')


def chapters_in_title(t: str) -> int:
    """How many chapters of the title print at least one section, from the title's index page as retrieved."""
    import re
    import parse
    idx = parse.page(f'{parse.BASE}/arsDetail/?title={t}')
    blocks = re.split(rb'<div id="chapter[^"]*" class="accordion">', idx)[1:]
    return sum(1 for b in blocks if re.search(rf'https://www\.azleg\.gov/ars/{t}/'.encode(), b))


def readme(c: dict, today: str) -> str:
    acts = c['acts']
    const = [a for a in acts if a['slug'].startswith('constitution')]
    titles = [a for a in acts if a['slug'].startswith('title-')]
    n = lambda xs: sum(len(a['versions'][-1]['units']) for a in xs)  # noqa: E731
    rows = []
    if const:
        rows.append(f'| `constitution-article-NN/`, `constitution-preamble/` | Constitution of the State of Arizona: '
                    f'preamble and {len(const) - 1} articles | {n(const)} | {const[0]["versions"][0]["from"]} |')
    partial = []
    for t in sorted({a['slug'].split('-')[1] for a in titles}, key=int):
        mine = [a for a in titles if a['slug'].startswith(f'title-{t}-chapter-')]
        total = chapters_in_title(t)
        days = sorted({a['versions'][0]['from'] for a in mine})
        name = mine[0]['title'].split(', Chapter')[0]
        rows.append(f'| `title-{t}-chapter-NN/` | {name}: {len(mine)} of {total} chapters | {n(mine)} | '
                    f'{days[0]}{" to " + days[-1] if len(days) > 1 else ""} |')
        if len(mine) < total:
            last = mine[-1]['short'].rsplit('ch. ', 1)[1]
            partial.append(f'Title {t} is partial: chapters up to {last} ({len(mine)} of the {total} chapters that '
                           f'print sections) are here; the rest are added, in order, as they are retrieved.')
    ex_sec = '13-1105' if any(a['slug'].startswith('title-13-') and '13-1105' in a['versions'][0]['units']
                              for a in titles) else None
    q = ['| Question | Command |', '| --- | --- |']
    if ex_sec:
        q += [f'| What does A.R.S. § 13-1105 say today? | `python tools/az.py {today} 13-1105` |',
              '| A decimal section (13-3875.01) | `python tools/az.py ' + today + ' 13-3875.01` |',
              '| Which sections of Title 13 cite § 13-105? | `git grep -n -E "13-105([^0-9.]|$)" -- "title-13-*"` |']
    if const:
        q += [f'| What does Ariz. Const. art. 2, § 4 say? | `python tools/az.py {today} "art. 2, § 4"` |',
              '| Every change to a section (after later builds) | `git log -p -- constitution-article-02/section-04.md` |']
    q += ['| Who is credited for each line | `git blame <file>` |']
    return f'''# Arizona law, as a git repository

The Constitution of the State of Arizona and titles of the Arizona Revised Statutes (A.R.S.), one file per section,
as a git history. The source is the text the Arizona Legislature publishes at [azleg.gov](https://www.azleg.gov),
maintained by the Arizona Legislative Council. It follows the shared design of
[lexifina/global-law](https://github.com/lexifina/global-law), which places it at `us/arizona/statutes`.

**What this repository is not, yet: a history.** The Legislature publishes only the current text of each section,
with no earlier versions and no history notes. So each act here is one commit holding its whole current text,
dated by the day the text was retrieved (in the table below), and credited to the publisher as the oldest version available. Later
builds will add the text as it changes, so the history grows forward from here.

| Folder | What | Sections | Retrieved |
| --- | --- | ---: | --- |
{chr(10).join(rows)}
{(chr(10) + chr(10).join(partial) + chr(10)) if partial else ''}
The Legislature's site says the compilation includes the sections revised by the 57th Legislature, 2nd Regular
Session (2026), and "reflects the version of law that is effective on January 1st of the year following the most
recent legislative session". A section here may therefore print wording that takes effect after the day it was
retrieved.

## A lawyer's questions as git commands

{chr(10).join(q)}

Files: each A.R.S. chapter is a folder, `title-13-chapter-11/13-1105.md` is A.R.S. § 13-1105 (Title 13, Chapter 11),
and a decimal section such as § 13-3875.01 is `13-3875-01.md` (file names have no dots); `tools/az.py` finds the
folder for you. `constitution-article-02/section-04.md` is Ariz. Const. art. 2, § 4; Article 6.1 is
`constitution-article-06-1/`, a section such as art. 2, § 2.1 is `section-02-1.md`, and Article 4's two parts are
`part-1-section-NN.md` and `part-2-section-NN.md`. Where two ballot measures amended a section differently, the
Legislature prints both texts, and so does this record: art. 5, § 1 is `section-01.md` and its "Version 1"
("Version amended by 1992 Proposition 107") is `section-01-version-1.md`; which one governs is for the reader to
judge from the measures themselves. The A.R.S. do the same where a session law leaves two texts of a section:
§ 13-1204's second text ("(L26, Ch. 177, sec. 2)", listed as "Version 2" in the Legislature's index) is
`13-1204-version-2.md`. Each file starts with the
section's heading line as printed (`# 13-101. Purposes`), then one paragraph per line, as the page prints them.

## Dates and authors

Every commit is dated at noon, America/Phoenix (UTC-7 all year: Arizona keeps no daylight saving time), and carries
the day in its `In-force:` trailer, which the tools read. Each act's first commit is authored by
`Arizona Legislature <publisher@azleg.gov.invalid>` (an address that cannot exist) as the oldest version available.
No line is credited to a session law, because the source shows no earlier text: nobody can tell from it which
words a session law wrote. When a later build finds a section changed, that change will be credited to a session
law only where an official source names it unambiguously; otherwise it is labelled unexplained.

## What it does not show

- Any text before the day each part was retrieved. The Legislature keeps no past versions online.
- The session laws, the history notes and annotations of the official edition (published by Thomson Reuters), and
  the titles of the A.R.S. not listed above.
- Section headings above the section (title, chapter and article names) and repealed sections the Legislature no
  longer prints.

This is a research aid. The Legislature's site says its online A.R.S. is "primarily maintained for legislative
drafting purposes"; for anything that matters, read the official edition.

## How it is checked and built

See [REPRODUCE.md](REPRODUCE.md): the sources and their sha256s (`tools/sources-sha256.json`), the build steps from
the retrieved pages, and the checks. The letters and digits of every file were compared with those of its source
page, read by a separate script that shares no code with the parser (`tools/check_words.py`). No AI model wrote,
dated or credited any text.

## Reuse

{REUSE} The arrangement of the history, the commit messages, the tools and the documentation are © Lexifina,
released under CC BY 4.0; see [LICENSE](LICENSE).

Built by [Lexifina](https://lexifina.com). For corrections, open an issue.
'''


def licence() -> str:
    return f'''# License

The text of the Arizona Constitution and the Arizona Revised Statutes in this repository comes from the Arizona
Legislature (https://www.azleg.gov). {REUSE} The Legislature's site prints "All Rights Reserved" for the site; that
notice cannot reach the text of the law. Neither the Arizona Legislature nor the Arizona Legislative Council
endorses this repository.

Changes made by Lexifina: each section was converted to one Markdown file, one paragraph per line; curly quotes were
made straight and spacing was normalised; the words of the law were not changed.

The arrangement of the history (which commits exist, their dates and authors), the commit messages, the tools and the
documentation are © Lexifina, released under the Creative Commons Attribution 4.0 International License (CC BY 4.0):
https://creativecommons.org/licenses/by/4.0/
'''


def corpus_json(c: dict, today: str) -> str:
    d = {
        'corpus': 'us/arizona/statutes',
        'parent': 'us/federal/usc',
        'name': 'Constitution of the State of Arizona and the Arizona Revised Statutes',
        'label': 'Arizona statutes',
        'language': 'en',
        'history': 'current-only',
        'history_from': min(a['versions'][0]['from'] for a in c['acts']),
        'record_to': today,
        'record_note': ('The Arizona Legislature publishes only the current text of each section, with no earlier '
                        'versions or history notes, so each act has one version here: the text as retrieved on '
                        'the day given in the table of README.md. The online compilation includes the 2026 session and reflects the law effective on '
                        'January 1 following the most recent session.'),
        'built': today,
        'in_force_trailer': 'In-force',
        'has_future_branch': False,
        'author': {'consolidated': 'Arizona Legislature', 'amendment': 'none yet', 'unexplained': 'Arizona Legislature'},
        'dates': {'commit': 'the day the text was retrieved', 'time': '12:00 America/Phoenix (UTC-7, no daylight saving time)'},
        'scope': {
            'when_absent': 'not extracted; effective-date provisions are in the session laws',
            'default_reach': {
                'rule': 'presumption against retroactivity',
                'meaning': 'no statute is retroactive unless expressly declared therein',
                'authority': 'A.R.S. § 1-244 ("No statute is retroactive unless expressly declared therein.")',
                'decided_here': False}},
        'reuse': REUSE,
        'citation': {
            'file': '(title-[0-9]+-chapter-[0-9a-z-]+)/([0-9]+-[0-9]+)\\.md',
            'cites': '(§§ ?|§ ?|[Ss]ections? |A[.]R[.]S[.] ){n}([^0-9.]|[.]([^0-9]|$)|$)',
            'note': ('files are title-<n>-chapter-<NN>/<section>.md, the section number as cited (A.R.S. § 13-1105 is '
                     'title-13-chapter-11/13-1105.md); decimal sections (13-3875.01 -> 13-3875-01.md) and the Constitution '
                     '(constitution-article-NN/section-NN.md) are not matched by this rule.')},
        'tool': 'tools/az.py',
    }
    return json.dumps(d, ensure_ascii=False, indent=2) + '\n'


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--today', required=True)
    a = ap.parse_args()
    # The docs describe what main holds: corpus.json plus each corpus.d part verified against the source (PUBLISH).
    # AZ_DOCS_PARTS=all: describe every part, for the check build run before a part's PUBLISH is written.
    os.environ['GITLAW_VERIFIED_PARTS_ONLY'] = '0' if os.environ.get('AZ_DOCS_PARTS') == 'all' else '1'
    from build import load
    c, _ = load(HERE)
    files = {'README.md': readme(c, a.today).encode(), 'LICENSE': licence().encode(),
             'corpus.json': corpus_json(c, a.today).encode()}
    for k, v in publish_gate(files).items():
        (HERE / 'repo' / k).write_bytes(v)
    print('docs written:', ', '.join(files))


if __name__ == '__main__':
    main()
