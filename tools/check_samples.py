"""Check that the sample keyword lists do not overlap a reference list (e.g. a book's table of contents).

Usage:
    python tools/check_samples.py REFERENCE.csv [SAMPLE.csv ...]

REFERENCE.csv is read with the same automatic preprocessing as the app (header, keyword column).
Samples default to samples/keywords_ko.csv. Compare samples with a reference in the same language.

Reported:
    exact        same keyword after normalization (case, spaces, full-width forms)   -> exit code 1
    containment  all words of one keyword appear in the other ("Plato" / "Plato's Cave") -> exit code 1
    partial      one is a substring of the other but not on word boundaries,
                 e.g. "천도교" contains "도교" (Cheondogyo vs Taoism)              -> for manual review
    similar      similarity score >= --threshold                                   -> for manual review
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import core  # noqa: E402


def read_keywords(path):
    rows, _ = core.read_csv_rows(core.read_file_text(path)[0])
    lay = core.detect_layout(rows)
    return core.extract_keywords(rows, lay.skip_top, lay.has_header, lay.selected)


def check(reference, sample, threshold):
    ref = [(k, core.features(k)) for k in reference]
    ref_keys = {core.key(k) for k in reference}
    exact, contained, partial, similar, seen, dups = [], [], [], [], set(), []
    for s in sample:
        if core.key(s) in seen:
            dups.append(s)
        seen.add(core.key(s))
        if core.key(s) in ref_keys:
            exact.append(s)
        fs = core.features(s)
        for r, fr in ref:
            a, b = fs.compact, fr.compact
            if a != b and len(a) >= 2 and len(b) >= 2 and (a in b or b in a):
                whole_words = fs.tokens and fr.tokens and (fs.tokens <= fr.tokens or fr.tokens <= fs.tokens)
                (contained if whole_words else partial).append((s, r))
            score = core.similarity_f(fs, fr)
            if threshold <= score < 1.0:
                similar.append((score, s, r))
    similar.sort(reverse=True)
    return exact, contained, partial, similar, dups


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("reference")
    ap.add_argument("samples", nargs="*", default=[os.path.join(ROOT, "samples", "keywords_ko.csv")])
    ap.add_argument("--threshold", type=float, default=0.45, help="similarity to report for review")
    args = ap.parse_args()

    reference = read_keywords(args.reference)
    failed = False
    for path in args.samples:
        sample = read_keywords(path)
        exact, contained, partial, similar, dups = check(reference, sample, args.threshold)
        print(f"== {os.path.basename(path)}: {len(sample)} keywords vs {len(reference)} reference keywords")
        print(f"   exact: {len(exact)}  containment: {len(contained)}  duplicates in sample: {len(dups)}"
              f"  | review: partial {len(partial)}, similar >= {args.threshold}: {len(similar)}")
        for s in exact:
            print(f"   EXACT        {s}")
        for s, r in contained:
            print(f"   CONTAINMENT  {s}  <->  {r}")
        for s in dups:
            print(f"   DUPLICATE    {s}")
        for s, r in partial:
            print(f"   partial      {s}  <->  {r}")
        for score, s, r in similar:
            print(f"   similar {score:.2f}  {s}  <->  {r}")
        failed |= bool(exact or contained or dups)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
