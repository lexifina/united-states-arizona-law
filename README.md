# Arizona law, as a git repository

Part of [lexifina/global-law](https://github.com/lexifina/global-law), one git history for every country's law: this is the law of Arizona, United States, which global-law reads at `united-states/arizona/acts/`.

The Constitution of the State of Arizona and titles of the Arizona Revised Statutes (A.R.S.), one file per section, as a git history. The source is the text the Arizona Legislature publishes at [azleg.gov](https://www.azleg.gov), maintained by the Arizona Legislative Council. It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law), which places it at `us/arizona/statutes`.

**What this repository is not, yet: a history.** The Legislature publishes only the current text of each section, with no earlier versions and no history notes. So each act here is one commit holding its whole current text, dated by the day the text was retrieved (in the table below), and credited to the publisher as the oldest version available.

| Folder | What | Sections | Retrieved |
| --- | --- | ---: | --- |
| `constitution-article-NN/`, `constitution-preamble/` | Constitution of the State of Arizona: preamble and 29 articles | 323 | 2026-10-30 |
| `title-13-chapter-NN/` | Arizona Revised Statutes, Title 13 (Criminal Code): 48 of 48 chapters | 985 | 2026-10-30 to 2026-10-31 |
| `title-33-chapter-NN/` | Arizona Revised Statutes, Title 33 (Property): 9 of 24 chapters | 280 | 2026-10-31 |

Title 33 is partial: chapters up to 8 (9 of the 24 chapters that print sections) are here; the rest are added, in order, as they are retrieved.

The Legislature's site says the compilation includes the sections revised by the 57th Legislature, 2nd Regular Session (2026), and "reflects the version of law that is effective on January 1st of the year following the most recent legislative session". A section here may therefore print wording that takes effect after the day it was retrieved.

## A lawyer's questions as git commands

| Question | Command |
| --- | --- |
| What does A.R.S. § 13-1105 say today? | `python tools/az.py 2026-10-31 13-1105` |
| A decimal section (13-3875.01) | `python tools/az.py 2026-10-31 13-3875.01` |
| Which sections of Title 13 cite § 13-105? | `git grep -n -E "13-105([^0-9.] | $)" -- "title-13-*"` |
| What does Ariz. Const. art. 2, § 4 say? | `python tools/az.py 2026-10-31 "art. 2, § 4"` |
| Every change to a section (after later builds) | `git log -p -- constitution-article-02/section-04.md` |
| Who is credited for each line | `git blame <file>` |

Files: each A.R.S. chapter is a folder, `title-13-chapter-11/13-1105.md` is A.R.S. § 13-1105 (Title 13, Chapter 11), and a decimal section such as § 13-3875.01 is `13-3875-01.md` (file names have no dots); `tools/az.py` finds the folder for you. `constitution-article-02/section-04.md` is Ariz. Const. art. 2, § 4; Article 6.1 is `constitution-article-06-1/`, a section such as art. 2, § 2.1 is `section-02-1.md`, and Article 4's two parts are `part-1-section-NN.md` and `part-2-section-NN.md`. Where two ballot measures amended a section differently, the Legislature prints both texts, and so does this record: art. 5, § 1 is `section-01.md` and its "Version 1" ("Version amended by 1992 Proposition 107") is `section-01-version-1.md`; which one governs is for the reader to judge from the measures themselves. The A.R.S. do the same where a session law leaves two texts of a section: § 13-1204's second text ("(L26, Ch. 177, sec. 2)", listed as "Version 2" in the Legislature's index) is `13-1204-version-2.md`. Each file starts with the section's heading line as printed (`# 13-101. Purposes`), then one paragraph per line, as the page prints them.

## Dates and authors

Every commit is dated at noon, America/Phoenix (UTC-7 all year: Arizona keeps no daylight saving time), and carries the day in its `In-force:` trailer, which the tools read. Each act's first commit is authored by `Arizona Legislature <publisher@azleg.gov.invalid>` (an address that cannot exist) as the oldest version available. No line is credited to a session law, because the source shows no earlier text: nobody can tell from it which words a session law wrote. When a later build finds a section changed, that change will be credited to a session law only where an official source names it unambiguously; otherwise it is labelled unexplained.

## What it does not show

- Any text before the day each part was retrieved. The Legislature keeps no past versions online.
- The session laws, the history notes and annotations of the official edition (published by Thomson Reuters), and the titles of the A.R.S. not listed above.
- Section headings above the section (title, chapter and article names) and repealed sections the Legislature no longer prints.

This is a research aid. The Legislature's site says its online A.R.S. is "primarily maintained for legislative drafting purposes"; for anything that matters, read the official edition.

## How it is checked and built

See [REPRODUCE.md](REPRODUCE.md): the sources and their sha256s (`tools/sources-sha256.json`), the build steps from the retrieved pages, and the checks. The letters and digits of every file were compared with those of its source page, read by a separate script that shares no code with the parser (`tools/check_words.py`). No AI model wrote, dated or credited any text.

## Reuse

The text of the law carries no copyright: under the government edicts doctrine (Georgia v. Public.Resource.Org, Inc., 590 U.S. 255 (2020)) nobody owns works made by legislators in their official capacity, which covers the statutes and the Constitution the Arizona Legislature publishes. The arrangement of the history, the commit messages, the tools and the documentation are © Lexifina, released under CC BY 4.0; see [LICENSE](LICENSE).

Built by [Lexifina](https://lexifina.com). For corrections, open an issue.
