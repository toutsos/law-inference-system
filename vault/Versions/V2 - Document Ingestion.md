Part of [[Home]]. See [[Agent Instructions]] for how decisions/tools/checklist should be maintained.

**Status:** Not Started

## Goal

Turn raw Greek legislation documents into clean, structured, chunked data with preserved provenance — without any database or embeddings yet. Ingestion quality silently caps everything downstream: no retrieval strategy or prompt engineering in later versions can recover information that was mangled here. This is also where the domain models from [[V0 - Project Foundation]] meet reality and get revised.

**You'll have learned:** text extraction from messy real-world documents, Unicode normalization (a genuinely sharp edge for Greek), structure-aware parsing, chunking strategy for legal text, and the golden-file testing pattern.


## Evidence from the corpus (2026-08-29, gathered in V0 step 12)

First text extraction from `data/raw/fek-a-121-2025.pdf` — π.δ. 62/2025, ΦΕΚ Α΄ 121/11.07.2025. Findings that constrain this version's design:

- **260 pages, and the PDF has a real text layer** (~2,000 characters on page 6). Ingestion is a *parsing* problem, not an OCR one. This was verified before committing to the corpus, not assumed.
- **The opening pages are a πίνακας περιεχομένων**, not body text. Page 6 lists `Άρθρο 156 Ποινική ευθύνη...`, `Άρθρο 157 ...` as a table of contents — article numbers and titles with no provisions under them. A parser that starts at page 1 and matches on `Άρθρο N` will emit a full set of **phantom articles with titles and empty text**, then emit the real ones later. Detecting and skipping the ToC is a first-class requirement, not an edge case.
- **Every page carries header/footer noise** — `ΕΦΗΜΕΡΙΔΑ TΗΣ ΚΥΒΕΡΝΗΣΕΩΣ`, the gazette page number (`2870`), and `Τεύχος A’ 121/11.07.2025`. These interleave with body text in extraction order and must be stripped per page.
- **`ΥΠΟΚΕΦΑΛΑΙΟ` is in active use**, alongside Βιβλίο / Μέρος / Τμήμα / Κεφάλαιο — five container levels in one document. Handled as data by `Article.path`; see [[Greek Legislation Structure]].
- **Mixed scripts and non-standard ordinal marks appear in the source itself.** NFC alone will not fix them — see the 2026-08-29 correction in [[Greek Legislation Structure]]. Normalization needs NFC *plus* an explicit confusable-folding map, shared with query normalization in [[V5 - Hybrid Retrieval]].

## Steps

- [ ] **1. Choose the acquisition source and verify terms of use** — _Why:_ provenance and legality first. Candidates: Εθνικό Τυπογραφείο (et.gr, official ΦΕΚ PDFs — authoritative but PDF-only), e-nomothesia.gr, ministry codifications. The choice shapes the whole pipeline (PDF vs. HTML parsing), so compare before committing and record the decision.
- [ ] **2. Download the sample corpus (3–5 laws from V0's selection) into `data/raw/` with a manifest** — _Why:_ a manifest file (source URL, retrieval date, official identifier — e.g. ΦΕΚ Α' issue) makes the corpus reproducible and is the root of the provenance chain that [[V6 - Legal Structure and Citations]] will surface to users. `data/` stays git-ignored; the manifest is committed.
- [ ] **3. Implement text extraction; compare at least two extraction libraries on one document** — _Why:_ PDF extraction is lossy in different ways per library (column order, headers/footers, hyphenation, dropped diacritics). Inspecting real output from e.g. `pypdf` vs. `pdfplumber` (or docling) against the original teaches you to never trust extraction blindly — and gives you grounds for the choice.
- [ ] **4. Normalize the text: Unicode NFC, whitespace, de-hyphenation, header/footer removal** — _Why:_ Greek text has two encodings for every accented vowel (precomposed vs. combining) and a final-sigma variant; if normalization is inconsistent, exact matching and lexical retrieval in [[V5 - Hybrid Retrieval]] silently fail. Normalizing once, at ingestion, in one place, is the fix.
- [ ] **5. Parse legal structure into the domain models: detect «Άρθρο N», numbered paragraphs, law title/number/year** — _Why:_ legal text has explicit machine-recognizable structure, and citations ([[V6 - Legal Structure and Citations]]) are only possible if it's captured now. Expect regex + heuristics; expect exceptions; log what fails to parse instead of dropping it silently. Revise the V0 domain models where reality disagrees with them.
- [ ] **6. Decide and implement the chunking strategy: structure-aware (article/paragraph boundaries), not fixed-size** — _Why:_ this is the first decision with major retrieval consequences. Fixed-size windows cut provisions mid-sentence and destroy citation precision; legal documents hand you natural semantic units (articles, paragraphs) for free. Decide the target unit, what to do with oversized articles, and record the reasoning — capture the general concept as a [[Chunking]] concept note.
- [ ] **7. Attach metadata to every chunk: law number/year, article, paragraph, source manifest reference** — _Why:_ metadata is what turns "similar text found" into "ν. 4808/2021, άρθρο 4, παρ. 2" — the product's entire value proposition per [[Home]].
- [ ] **8. Persist processed output as JSON files in `data/processed/`** — _Why:_ files are inspectable with any editor, diffable, and require zero infrastructure — see the Decision below. The database enters in [[V3 - First RAG System]] when something actually needs it.
- [ ] **9. Create a small fixture corpus and ingestion tests (golden files)** — _Why:_ a tiny law excerpt checked into `tests/fixtures/` with its expected parsed output pins the pipeline's behavior; any parsing change that alters output becomes a visible diff, not a silent corpus corruption.
- [ ] **10. Manual QA pass: read a sample of chunks side-by-side with the original document** — _Why:_ automated tests catch regressions, not wrongness you never noticed. Ten minutes of reading catches mangled diacritics, merged articles, and lost paragraphs before they get embedded in V3.

## Decisions

- **2026-08-22:** V2 persists processed output as **JSON files on disk, not a database**. Rationale: files are inspectable and diffable during exactly the phase where inspecting parser output constantly is the main activity; introducing Postgres here would add infrastructure a version early ([[V0 - Project Foundation]] deferred docker to [[V3 - First RAG System]]) and would hide parsing mistakes behind a query interface. Trade-off: V3 must re-load these files into the store — acceptable, since that loader is needed anyway.

## Tools & Alternatives Considered

_To fill during the version: extraction libraries compared (pypdf / pdfplumber / docling / …) with observed differences on the actual corpus; source options compared (et.gr vs. e-nomothesia vs. codified texts)._

## Definition of Done (version-specific)

- Running one command (`poe ingest` or similar) rebuilds `data/processed/` from `data/raw/` deterministically.
- Every chunk carries law/article/paragraph metadata and a resolvable source reference.
- Golden-file tests pass; parse failures are logged, counted, and understood.
- Manual QA notes recorded here (what the extractor gets wrong and why it's acceptable or fixed).

## Notes

_Freeform notes, gotchas, links, technical debt._
