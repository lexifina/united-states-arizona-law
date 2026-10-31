"""Prints Arizona law as it stood on a given day, read from this repository's history.

    python tools/az.py 2026-10-30 13-1105                 # A.R.S. § 13-1105
    python tools/az.py 2026-10-30 13-3875.01              # a decimal section (file title-13/13-3875-01.md)
    python tools/az.py 2026-10-30 "art. 2, § 4"           # Ariz. Const. art. 2, § 4
    python tools/az.py 2026-10-30 "art. 6.1, § 3"         # Article 6.1
    python tools/az.py 2026-10-30 "art. 4, pt. 2, § 1"    # Article 4 has two parts
    python tools/az.py 2026-10-30 title-13-chapter-11     # a whole chapter
    python tools/az.py --law 2026-10-30 33-1301           # also name who is credited for the version shown

A thin wrapper around tools/on.py: the version is chosen by each commit's `In-force:` trailer, never by its commit
date. Standard library only.
"""
import re
import runpy
import subprocess
import sys
from pathlib import Path


def target(ref: str) -> list[str]:
    ref = ref.strip()
    m = re.fullmatch(r'(?:A\.R\.S\.\s*)?(?:§\s*)?(\d+)-(\d+(?:\.\d+)*[A-Za-z]?)', ref)
    if m:
        name = f'{m.group(1)}-{m.group(2)}'.replace('.', '-').lower()
        # sections sit in chapter folders (title-13-chapter-11/13-1105.md): find the folder in the history
        files = subprocess.run(['git', 'log', '--all', '--format=', '--name-only', '--', f'title-{m.group(1)}-chapter-*/{name}.md'],
                               capture_output=True, text=True, encoding='utf-8').stdout.split()
        if files:
            return [files[0].split('/')[0], name]
        return [f'title-{m.group(1)}', name]
    m = re.fullmatch(r'title-?\s*(\d+)', ref, re.I)
    if m:
        return [f'title-{m.group(1)}']
    m = re.fullmatch(r'(?:Ariz\.\s*Const\.\s*)?art(?:icle|\.)?\s*([0-9.]+),?\s*(?:p(?:ar)?t\.?\s*(\d+),?\s*)?'
                     r'(?:§|sec(?:tion|\.)?)\s*([0-9.]+[A-Za-z]?)', ref, re.I)
    if m:
        a = m.group(1).split('.')
        s = re.fullmatch(r'(\d+)((?:\.\d+)*)([A-Za-z]?)', m.group(3))
        act = f'constitution-article-{int(a[0]):02d}' + ''.join(f'-{x}' for x in a[1:])
        unit = (f'part-{m.group(2)}-' if m.group(2) else '') + (f'section-{int(s.group(1)):02d}' + ''.join(f'-{x}' for x in s.group(2).split('.') if x)
                + (f'-{s.group(3).lower()}' if s.group(3) else ''))
        return [act, unit]
    if ref.lower() == 'preamble':
        return ['constitution-preamble', 'preamble']
    return ref.split()


if __name__ == '__main__':
    args = sys.argv[1:]
    flags = [a for a in args if a.startswith('--')]
    rest = [a for a in args if not a.startswith('--')]
    if not rest:
        sys.exit(__doc__)
    day, refs = rest[0], rest[1:]
    sys.argv = [str(Path(__file__).with_name('on.py')), *flags, day] + (target(' '.join(refs)) if refs else [])
    runpy.run_path(sys.argv[0], run_name='__main__')
