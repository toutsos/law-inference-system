# Corpus Sourcing and Licensing

Part of [[Home]]. Established in [[V0 - Project Foundation]] (step 12), 2026-08-29. Acted on in [[V2 - Document Ingestion]].

## What it is / problem it solves

Step 12 requires verifying that the sample corpus can legally be downloaded, stored, processed and quoted. Two separate questions, often conflated:

1. Is the **legal text itself** protected? — No.
2. Is the **database or compilation** you took it from protected? — Often yes.

## 1. The legal text is not copyrighted

**ν. 2121/1993, άρθρο 2 παρ. 5** excludes from copyright protection *"τα επίσημα κείμενα με τα οποία εκφράζεται η άσκηση πολιτειακής εξουσίας και ιδίως τα νομοθετικά, διοικητικά ή δικαστικά κείμενα"* — legislative, administrative and judicial texts.

So statutes, π.δ., and ΚΥΑ carry no copyright. There is no licence to accept and no attribution legally required (attribution is still required *for the system to be useful* — an unsourced legal answer is worthless, per the scope boundary in [[Home]]).

**ν. 3861/2010, άρθρο 7** (Διαύγεια) additionally makes all ΦΕΚ freely available electronically from the Εθνικό Τυπογραφείο, for reading, saving and printing, without charge.

## 2. The aggregator's database may be protected

Sites like kodiko.gr, e-nomothesia.gr, lawspot.gr and taxheaven.gr are far easier to scrape than ΦΕΚ PDFs — clean HTML, already split by article, often consolidated. **Do not ingest from them.**

The underlying text is free, but their *codification, structuring, cross-linking and annotation* is their own work, and a substantial database can attract the **sui generis database right** (ν. 2121/1993, άρθρο 45Α) independently of copyright in the contents. Their terms of use typically forbid systematic extraction as well.

**Rule for this project: ingest only from the official source (`et.gr` / `search.et.gr`).** Aggregators may be used to *find* which ΦΕΚ to fetch, and to eyeball a parse for correctness — never as the ingested text.

## 3. The primary source

**Εθνικό Τυπογραφείο** — `search.et.gr` (simple, advanced and semantic search over ΦΕΚ). Free PDF download of any issue.

Accepted cost, carried into [[V2 - Document Ingestion]]: ΦΕΚ are **PDFs, not structured text**. Layout is two-column with headers, footers, page numbers and digital signature blocks that must be stripped. Whether a given issue has a usable text layer or needs OCR must be checked per document before committing to it — an unverified assumption here would be discovered halfway through building the parser.

## Used in

- [[V0 - Project Foundation]] — step 12, choosing the corpus.
- [[V2 - Document Ingestion]] — fetching and parsing; the "official source only" rule binds here.

## Notes

Attribution and version-awareness are *engineering* requirements here, not legal ones — see temporal validity in [[Greek Legislation Structure]] and the scope boundary in [[Home]].
