"""Throwaway: count what the heading rule keeps, rejects and cannot read.

Not production code and not imported by the package. Every number in the step
5a decisions of the V2 note comes out of here, so re-run it before believing
them — a third document in the corpus can invalidate any of them.

    uv run python scripts/probe_structure.py
    uv run python scripts/probe_structure.py --show-rejected --show-unreadable
"""

import argparse

from greek_law.ingestion import DEFAULT_MANIFEST_PATH, load_manifest
from greek_law.ingestion.extraction import extract_document
from greek_law.ingestion.normalization import normalize_document
from greek_law.ingestion.structure import (
    find_article_headings,
    rejected_heading_candidates,
    unreadable_heading_lines,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show-rejected", action="store_true")
    parser.add_argument("--show-unreadable", action="store_true")
    args = parser.parse_args()

    for entry in load_manifest(DEFAULT_MANIFEST_PATH).documents:
        document = normalize_document(extract_document(entry))
        kept = find_article_headings(document)
        rejected = rejected_heading_candidates(document)
        unreadable = unreadable_heading_lines(document)

        act = entry.act
        print(f"\n### {entry.id} — {act.act_type} {act.number}/{act.year}")
        if kept:
            print(
                f"  kept       {len(kept):>5}  άρθρα {kept[0].number}–"
                f"{kept[-1].number}, PDF pp. {kept[0].page}–{kept[-1].page}"
            )
            expected = [str(number) for number in range(1, len(kept) + 1)]
            print(f"  contiguous 1..N  {[h.number for h in kept] == expected}")
        else:
            print("  kept           0  — no article sequence found")
        print(f"  rejected   {len(rejected):>5}")
        print(
            f"  unreadable {sum(unreadable.values()):>5}  "
            f"in {len(unreadable)} distinct lines"
        )

        if args.show_rejected:
            for heading in rejected:
                print(f"    rejected   p{heading.page:<4} Άρθρο {heading.number}")
        if args.show_unreadable:
            for line, count in unreadable.most_common():
                print(f"    unreadable ×{count}  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
