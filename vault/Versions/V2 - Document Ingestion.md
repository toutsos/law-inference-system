Part of [[Home]]. See [[Agent Instructions]] for how decisions/tools/checklist should be maintained.

**Status:** In Progress — started 2026-09-14. Steps 1–3 done (2026-09-14). Extraction is `greek_law.ingestion.extraction` on **pypdf**, chosen by measurement — see the Decisions and the Notes. Next: step 4, normalization, which now has a measured target list rather than a predicted one. **One document is already in `data/raw/` and is not optional**: ν. 5110/2024 (ΦΕΚ Α' 75/24.05.2024) is the law [[V1 - Minimal LLM Application]]'s baseline questions were written against, so [[V3 - First RAG System]]'s comparison depends on this version ingesting it. See the note on step 5 — it breaks an assumption the domain model currently makes.

## Goal

Turn raw Greek legislation documents into clean, structured, chunked data with preserved provenance — without any database or embeddings yet. Ingestion quality silently caps everything downstream: no retrieval strategy or prompt engineering in later versions can recover information that was mangled here. This is also where the domain models from [[V0 - Project Foundation]] meet reality and get revised.

**You'll have learned:** text extraction from messy real-world documents, Unicode normalization (a genuinely sharp edge for Greek), structure-aware parsing, chunking strategy for legal text, and the golden-file testing pattern.


## Evidence from the corpus (2026-08-29, gathered in V0 step 12)

First text extraction from `data/raw/20250100121.pdf` (named `fek-a-121-2025.pdf` at the time; renamed to the publisher's own filename in step 2) — π.δ. 62/2025, ΦΕΚ Α΄ 121/11.07.2025. Findings that constrain this version's design:

- **260 pages, and the PDF has a real text layer** (~2,000 characters on page 6). Ingestion is a *parsing* problem, not an OCR one. This was verified before committing to the corpus, not assumed.
- **The opening pages are a πίνακας περιεχομένων**, not body text. Page 6 lists `Άρθρο 156 Ποινική ευθύνη...`, `Άρθρο 157 ...` as a table of contents — article numbers and titles with no provisions under them. A parser that starts at page 1 and matches on `Άρθρο N` will emit a full set of **phantom articles with titles and empty text**, then emit the real ones later. Detecting and skipping the ToC is a first-class requirement, not an edge case.
- **Every page carries header/footer noise** — `ΕΦΗΜΕΡΙΔΑ TΗΣ ΚΥΒΕΡΝΗΣΕΩΣ`, the gazette page number (`2870`), and `Τεύχος A’ 121/11.07.2025`. These interleave with body text in extraction order and must be stripped per page.
- **`ΥΠΟΚΕΦΑΛΑΙΟ` is in active use**, alongside Βιβλίο / Μέρος / Τμήμα / Κεφάλαιο — five container levels in one document. Handled as data by `Article.path`; see [[Greek Legislation Structure]].
- **Mixed scripts and non-standard ordinal marks appear in the source itself.** NFC alone will not fix them — see the 2026-08-29 correction in [[Greek Legislation Structure]]. Normalization needs NFC *plus* an explicit confusable-folding map, shared with query normalization in [[V5 - Hybrid Retrieval]].

## Steps

- [x] **1. Choose the acquisition source and verify terms of use** — _Why:_ provenance and legality first. Candidates: Εθνικό Τυπογραφείο (et.gr, official ΦΕΚ PDFs — authoritative but PDF-only), e-nomothesia.gr, ministry codifications. The choice shapes the whole pipeline (PDF vs. HTML parsing), so compare before committing and record the decision. — _Done 2026-09-14: Εθνικό Τυπογραφείο (`search.et.gr`), official ΦΕΚ PDFs, confirming the rule already set in [[Corpus Sourcing and Licensing]]. Terms of use read and quoted; the operational finding — no reachable machine download route — is in the Notes._
- [x] **2. Download the sample corpus (3–5 laws from V0's selection) into `data/raw/` with a manifest** — _Already held:_ `fek_a_75_2024.pdf` — ν. 5110/2024, ΦΕΚ Α' 75/24.05.2024, *Ίδρυση Ελληνικού Κέντρου Αμυντικής Καινοτομίας…*. Its manifest entry matters more than the others': `experiments/baseline_no_rag/questions.json` transcribes ten provisions from it as ground truth, and `data/` is gitignored, so the manifest is the only committed thing that says which document those transcriptions came from. Record the source URL and retrieval date, and re-download from et.gr to verify the file matches before trusting the transcriptions. — _Why:_ a manifest file (source URL, retrieval date, official identifier — e.g. ΦΕΚ Α' issue) makes the corpus reproducible and is the root of the provenance chain that [[V6 - Legal Structure and Citations]] will surface to users. `data/` stays git-ignored; the manifest is committed. — _Done 2026-09-14: **two** documents, not 3–5 (see the Decision below). `corpus/manifest.json` + `greek_law.ingestion` + `poe corpus`. Both files re-downloaded from source and hash-matched, so V1's ground truth is anchored to bytes that are provably the published ones._
- [x] **3. Implement text extraction; compare at least two extraction libraries on one document** — _Why:_ PDF extraction is lossy in different ways per library (column order, headers/footers, hyphenation, dropped diacritics). Inspecting real output from e.g. `pypdf` vs. `pdfplumber` (or docling) against the original teaches you to never trust extraction blindly — and gives you grounds for the choice. — _Done 2026-09-14: pypdf, after pdfplumber was measured spliceing the two ΦΕΚ columns into one line on body pages of **both** corpus documents. `ingestion/extraction.py` + `scripts/probe_extraction.py`; 8 new tests, 106 total._
- [ ] **4. Normalize the text: Unicode NFC, whitespace, de-hyphenation, header/footer removal** — _Why:_ Greek text has two encodings for every accented vowel (precomposed vs. combining) and a final-sigma variant; if normalization is inconsistent, exact matching and lexical retrieval in [[V5 - Hybrid Retrieval]] silently fail. Normalizing once, at ingestion, in one place, is the fix.
- [ ] **5. Parse legal structure into the domain models: detect «Άρθρο N», numbered paragraphs, law title/number/year** — ⚠️ _Known counterexample, found 2026-09-07 by reading ν. 5110/2024:_ **one ΦΕΚ can carry two parallel article numberings.** Άρθρα 1–82 are the law; άρθρο 13 ratifies a ΚΑΤΑΣΤΑΤΙΚΟ whose own articles are spelled out — *Άρθρο πρώτο* … *Άρθρο τριακοστό*. So «άρθρο 15» (Κέντρα Αριστείας) and «άρθρο δέκατο πέμπτο» (σύνθεση του Διοικητικού Συμβουλίου) are **different provisions of the same document**. A regex for `Άρθρο\s+\d+` silently drops the whole καταστατικό; one that also matches spelled-out ordinals merges two namespaces into one. `SourceReference` cannot express the difference today — see the [[V1 - Minimal LLM Application]] architecture review, finding 4 — and this step is where the second real example arrives that makes the fix designable rather than guessable — _Why:_ legal text has explicit machine-recognizable structure, and citations ([[V6 - Legal Structure and Citations]]) are only possible if it's captured now. Expect regex + heuristics; expect exceptions; log what fails to parse instead of dropping it silently. Revise the V0 domain models where reality disagrees with them.
- [ ] **6. Decide and implement the chunking strategy: structure-aware (article/paragraph boundaries), not fixed-size** — _Why:_ this is the first decision with major retrieval consequences. Fixed-size windows cut provisions mid-sentence and destroy citation precision; legal documents hand you natural semantic units (articles, paragraphs) for free. Decide the target unit, what to do with oversized articles, and record the reasoning — capture the general concept as a [[Chunking]] concept note.
- [ ] **7. Attach metadata to every chunk: law number/year, article, paragraph, source manifest reference** — _Why:_ metadata is what turns "similar text found" into "ν. 4808/2021, άρθρο 4, παρ. 2" — the product's entire value proposition per [[Home]].
- [ ] **8. Persist processed output as JSON files in `data/processed/`** — _Why:_ files are inspectable with any editor, diffable, and require zero infrastructure — see the Decision below. The database enters in [[V3 - First RAG System]] when something actually needs it.
- [ ] **9. Create a small fixture corpus and ingestion tests (golden files)** — _Why:_ a tiny law excerpt checked into `tests/fixtures/` with its expected parsed output pins the pipeline's behavior; any parsing change that alters output becomes a visible diff, not a silent corpus corruption.
- [ ] **10. Manual QA pass: read a sample of chunks side-by-side with the original document** — _Why:_ automated tests catch regressions, not wrongness you never noticed. Ten minutes of reading catches mangled diacritics, merged articles, and lost paragraphs before they get embedded in V3.

## Decisions

- **2026-09-14 (step 3): pypdf, not pdfplumber.** Measured, not assumed — the probe ran both over body pages of both corpus documents. **pdfplumber's `extract_text()` splices the two ΦΕΚ columns**: it sorts words by (top, left) across the whole page, so line 1 of the left column and line 1 of the right column come back as one line. `layout=True` does not fix it — it renders the page onto a fixed-width character canvas, preserving the look and therefore the splice. pypdf preserved reading order on both documents, which matters because the two were produced by different toolchains (Distiller/PDFsharp vs. InDesign/Adobe PDF Library), so a single success would have proved nothing. **The failure mode is why this decision is worth the time it took**: spliced text is fluent, correctly accented Greek that nothing flags and that says something nobody wrote — the ingestion-layer twin of V1's finding that fabricated citations resolve.
- **2026-09-14 (step 3): the correctness pypdf gives is not controllable, and that is accepted with a named trigger.** pypdf emits text in PDF *content-stream* order; it performs no layout analysis, so there is no setting to verify and no way to check its answer. pdfplumber's offer is the inverse — wrong by default, but word coordinates make cropping into columns *checkable*. Declined because paying for controllability means writing and maintaining column detection to fix a problem pypdf does not currently have. **Revisit the day a ΦΕΚ extracts out of order**; `pages_with_suspicious_line_width` exists to make that day visible rather than silent.
- **2026-09-14 (step 3): the test suite stays fast, and the one test that opens a real PDF is marked `slow` and excluded by default.** Reading the 260-page π.δ. takes 4.77 s against a whole-suite time of 0.18 s. That speed is load-bearing, not vanity: V1's architecture review was done by *reading* the code, which is only affordable when running the tests is free. `poe test` excludes the marker, `poe test-all` includes it — surefire vs. failsafe, or JUnit's `@Tag` excluded from the default profile.
- **2026-09-14 (step 2): files on disk keep the publisher's filename (`20240100075.pdf`), not a readable one of ours (`fek_a_75_2024.pdf`).** The learner's call, overruling the tutor's naming, and it is the better one. The stated reason was convenience — no rename step after downloading. The stronger reason is that it removes an error class: `20240100075` is the Εθνικό Τυπογραφείο's own identifier, so it is **transcribed by nobody**, whereas `fek_a_75_2024` is a human re-encoding of ΦΕΚ Α' 75/2024 and can therefore be re-encoded wrongly — silently, since no check compares a filename to the act identity beside it. It also makes `file` and `source_url` mutually derivable rather than two independent facts that can drift. Accepted cost: `ls data/raw/` is unreadable, and `id` no longer matches the file stem. That cost is paid by the manifest, which is where the human-readable handle now lives and the only place it needs to.
- **2026-09-14 (step 2): two documents, not the "3–5" the step title asks for.** ν. 5110/2024 (V1's baseline law) and π.δ. 62/2025 (V0's corpus choice). Each is in the corpus because a specific earlier decision put it there; a third would be in it to satisfy a number. Breadth is cheap to add later — one manifest entry and a download — and [[V4 - Question to Relevant Law]] is the version with an actual reason to want it.
- **2026-09-14 (step 2): the manifest lives at `corpus/manifest.json`, outside `data/`, and is verified by hash rather than trusted.** Two sub-decisions. **(a) Location.** The obvious home is `data/manifest.json`, next to what it describes — rejected because `.gitignore` contains `data/`, and git *cannot re-include a file whose parent directory is excluded*; it never descends into an ignored directory to find the negation. Committing it there means rewriting the ignore rule as `data/*` + `!data/raw/` + `data/raw/*` + `!data/raw/manifest.json`, four coupled lines that the next person to add a `data/processed/` breaks without noticing. The deeper reason is lifecycle, not mechanics: `data/` holds what can be re-downloaded, and the manifest is *the instructions for re-downloading it* — different lifecycle, different home. Diagnose with `git check-ignore -v <path>`, which names the rule and line number that excluded a file. **(b) A SHA-256 per document, not just a URL.** A URL is a claim that cannot fail; a hash is a claim that can. It is the only thing that can confirm the `fek_a_75_2024.pdf` on a given machine is the document `experiments/baseline_no_rag/questions.json` transcribed its ground truth from — and it is what will detect et.gr silently re-issuing a corrected ΦΕΚ under the same URL, which would otherwise re-attribute the whole V1 baseline to a text the model never saw. `size_bytes` is recorded but deliberately **not** checked: the hash subsumes it, and it is there so a human reading the manifest can tell a 500 KB PDF from a 12-byte error page saved under a `.pdf` name.
- **2026-09-14 (step 1): the acquisition source is the Εθνικό Τυπογραφείο (`search.et.gr`), and downloads are manual, not crawled.** The source question was already settled in principle by [[Corpus Sourcing and Licensing]] (V0 step 12): official source only, aggregators may be used to *find* a ΦΕΚ but never as the ingested text. What step 1 added is the part that note did not cover — **the site's terms are a second, independent layer on top of the copyright answer.** ν. 2121/1993 άρθρο 2 §5 says the legislative text carries no copyright; the search.et.gr *Όροι Χρήσης* still bind the use of the *service*: §1.2 grants access "αποκλειστικά για προσωπικούς, πληροφοριακούς, μη εμπορικούς σκοπούς", and §2.4 forbids "αναπαραγωγή του περιεχομένου του διαδικτυακού τόπου για εμπορικούς σκοπούς ή/και για μη προσωπική χρήση". Free-of-copyright content obtained through a service whose terms restrict reproduction is not free to redistribute. Three consequences, all binding on this version: **(a)** `data/` stays gitignored — that was a size and reproducibility decision, and is now also the decision that keeps the repo inside the terms; **(b)** the corpus is a handful of documents fetched by hand, not a crawl — no scripted enumeration of ΦΕΚ, which §1.2's "personal, informational" grant would not cover; **(c)** the project's non-commercial, educational framing in [[Home]] is what makes the download lawful, so it is a constraint to keep, not just a disclaimer.
- **2026-08-22:** V2 persists processed output as **JSON files on disk, not a database**. Rationale: files are inspectable and diffable during exactly the phase where inspecting parser output constantly is the main activity; introducing Postgres here would add infrastructure a version early ([[V0 - Project Foundation]] deferred docker to [[V3 - First RAG System]]) and would hide parsing mistakes behind a query interface. Trade-off: V3 must re-load these files into the store — acceptable, since that loader is needed anyway.

## Tools & Alternatives Considered

**Source options, compared 2026-09-14 (step 1).** Each was checked by fetching `robots.txt` and the terms page, not by reputation.

| Source | What it is | Verdict |
| --- | --- | --- |
| **`search.et.gr` (Εθνικό Τυπογραφείο)** | The publisher of record. ΦΕΚ as they were published, as PDF. `robots.txt` is `User-agent: * / Disallow:` — nothing disallowed. | **Chosen.** The only source whose text *is* the law rather than a rendering of it. Cost accepted: PDF parsing, two columns, headers/footers, signature blocks. |
| `e-nomothesia.gr` | Clean HTML, split by article, **codified** (amendments already folded in). | Rejected. Three reasons, in increasing order of weight: its `robots.txt` sets `Crawl-delay: 30` and disallows `Python-urllib` outright; the codification is its own editorial work and attracts the sui generis database right ([[Corpus Sourcing and Licensing]] §2); and — the one that would still rule it out if the other two vanished — a codified text has **no ΦΕΚ page numbers and no publication date of its own**, so it cannot anchor the provenance chain [[V6 - Legal Structure and Citations]] has to surface. |
| `kodiko.gr`, `lawspot.gr`, `taxheaven.gr` | Commercial legal publishers. | Rejected on the same database-right grounds; partly paywalled. Fine for *finding* a ΦΕΚ number and for eyeballing a parse. |
| Ministry codifications (PDF/DOC on ministry sites) | Consolidated texts published by the competent ministry. | Rejected as a *source*. No stable identifier, no guaranteed URL lifetime, no consistent format between ministries — three different reasons the manifest in step 2 could not be made reproducible. |

**Extraction libraries, compared 2026-09-14 (step 3)** on body pages of both corpus documents, via `scripts/probe_extraction.py`.

| Library | Column handling | Speed (260 pp.) | Verdict |
| --- | --- | --- | --- |
| **pypdf 6.18** | **Correct on both documents.** Follows content-stream order; no layout analysis, nothing to configure, nothing to verify. | 4.8 s | **Chosen.** Ships `py.typed`, pure Python, no system libraries. |
| pdfplumber 0.11 | **Splices the columns.** Median line width 97 against pypdf's 51 on body pages — two provisions welded into one line. `layout=True` reproduces the splice with padding. | ~14 s | Rejected as a default. Its word coordinates remain the fallback if pypdf ever mis-orders a document, since cropping columns explicitly is checkable. |
| PyMuPDF | Not measured. | — | Not tried, on licensing: **AGPL-3.0 or a commercial licence.** Worth knowing it is the usual "best quality" recommendation, and worth knowing why it was skipped without a benchmark. |
| docling | Not measured. | — | Deferred. An ML layout model is a heavyweight answer to a problem a 51-character median already solved, and [[Home]]'s guiding principle says add complexity when something justifies it. Reconsider only if a ΦΕΚ with tables or scanned pages enters the corpus. |

**Sampling lesson, worth more than the table:** the π.δ.'s first ~45 pages are a single-column πίνακας περιεχομένων, where pdfplumber's splice cannot occur (ratio 1.05×). Sampling only the front of the document would have cleared it. The failure appears from page ~60 (ratio 1.90×). *Where you sample decides what you find.*

## Definition of Done (version-specific)

- Running one command (`poe ingest` or similar) rebuilds `data/processed/` from `data/raw/` deterministically.
- Every chunk carries law/article/paragraph metadata and a resolvable source reference.
- Golden-file tests pass; parse failures are logged, counted, and understood.
- Manual QA notes recorded here (what the extractor gets wrong and why it's acceptable or fixed).

## Notes

### The official search backend does not resolve — 2026-09-14 (step 1)

Every search form on `search.et.gr` (`/el/search-legislation/`, `/el/simple-search/`, `/el/advanced-search/`) submits a plain `GET` to **`https://nationalprintinghousefek.azurewebsites.net/`**, carrying `field_year[]`, `legislation_catalogues` (1 = Νόμος, 2 = Προεδρικό Διάταγμα, 3 = ΠΝΠ, 101 = Αναγκαστικός Νόμος, 102 = Βασιλικό Διάταγμα, 301 = Νομοθετικό Διάταγμα, 501 = Νομοθετικό Προεδρικό Διάταγμα) and `field_number_legislation`. **That host is NXDOMAIN from the tutor's network**, so the search returns nothing and no PDF URL can be derived. `https://et.gr/api/DownloadFek/?fek_pdf=...` — the download endpoint the older site used — answers `404` on all three hosts.

Reproduce in ten seconds, and re-run it before believing this note is still true:

```
dig +short nationalprintinghousefek.azurewebsites.net          # empty output = NXDOMAIN
curl -sSIL -o /dev/null -w '%{http_code}\n' 'https://et.gr/api/DownloadFek/?fek_pdf=20240100075'
curl -sSL 'https://search.et.gr/el/simple-search/' | grep -oE '<form[^>]*action="[^"]+"'
```

The third command is the durable one: it reads the *current* form action out of the page, so it answers "where does the search actually post today" without trusting anything written here.

**Why this matters for step 2 rather than being a curiosity.** The manifest exists to make the corpus reproducible — "run this and you get the same bytes". A dated NXDOMAIN means the manifest's `source_url` may be a URL that only a browser session can resolve, or only from certain networks. So step 2 records **what was actually done** (the URL the browser downloaded from, the date, and a SHA-256 of the file) rather than a URL asserted to work. The hash is what makes the claim checkable when the URL eventually rots — and it is the only thing that can confirm `fek_a_75_2024.pdf`, already sitting in `data/raw/`, is the document `experiments/baseline_no_rag/questions.json` transcribed its ground truth from.

**Answered the same day, and it corrects the framing above.** The search works in the learner's browser, so the NXDOMAIN is network-scoped, not a dead service. More importantly, "no machine download route" was **wrong** — see the next note. What is unreachable from the tutor's network is the *search*; the *documents* are a plain GET.

### The ΦΕΚ URL is a pure function of the ΦΕΚ identity — 2026-09-14 (step 2)

The URLs the browser produced are not session-scoped and not behind the broken search host:

```
https://ia37rg02wpsa01.blob.core.windows.net/fek/01/2024/20240100075.pdf
https://ia37rg02wpsa01.blob.core.windows.net/fek/01/2025/20250100121.pdf
```

Plain Azure blob storage, `HTTP 200` to an unauthenticated `curl` from the tutor's network, and the shape decodes completely:

```
https://ia37rg02wpsa01.blob.core.windows.net/fek/{τεύχος:02d}/{year}/{year}{τεύχος:02d}{number:05d}.pdf
```

`τεύχος` is `01` for Α΄ and `02` for Β΄. Checked against four documents across two years and both τεύχη — ΦΕΚ Α΄ 75/2024, Α΄ 121/2025, Α΄ 1/2025 and Β΄ 121/2025 all returned 200.

**This corrects the step 1 note above.** Acquisition splits into two problems with different answers, and conflating them produced the wrong conclusion:

| Problem | Reachable by machine? |
| --- | --- |
| *Which* ΦΕΚ contains the law I want (number/year → τεύχος + ΦΕΚ number) | **No.** That is the search, and its backend does not resolve here. |
| Fetch a ΦΕΚ whose τεύχος/year/number I already know | **Yes.** One `curl`, no auth, no session. |

So the manual step is *identification*, not *download* — which is a much smaller manual step, and one that happens once per document rather than once per rebuild. The practical consequence for later versions: a `poe corpus --fetch` that downloads every missing manifest entry from its recorded `source_url` is now a ten-line addition rather than a browser-automation project. **Deliberately not built in V2**: two documents do not justify it, and a fetcher that nobody needs is a fetcher nobody notices has rotted.

**The verification step 2 asked for, done 2026-09-14:** both PDFs were downloaded again from the URLs above, into a different directory, and hashed. `bc8d145d…` and `c1468c50…` — identical to the files in `data/raw/` and to the manifest. ΦΕΚ PDFs are therefore byte-stable across downloads (the blob's `Last-Modified` for the 2024 issue is 14 Sep 2024, i.e. static since publication), so the hash is a usable identity and V1's transcribed ground truth is anchored to bytes that are provably the published ones.

### First extraction measurements — 2026-09-14 (step 3)

`scripts/probe_extraction.py` on **ν. 5110/2024 pages 6–8** (body text, two columns), pypdf 6.x vs pdfplumber 0.11.x, run with `uv run --with` so that neither library is a project dependency yet.

| | chars | lines | lines ending in `-` | seconds |
| --- | ---: | ---: | ---: | ---: |
| pypdf | 16 581 | 350 | 97 | 0.10 |
| pdfplumber (default) | 16 385 | 193 | 58 | 0.28 |
| pdfplumber (`layout=True`) | 21 161 | 211 | 58 | 0.26 |

**1. pdfplumber interleaves the two columns, and `layout=True` does not fix it.** Its `extract_text()` sorts words by (top, left) across the *whole page*, so line 1 of the left column and line 1 of the right column come back as one line — two unrelated provisions spliced together. `layout=True` renders the page onto a fixed-width character canvas, which preserves the *look* and therefore reproduces exactly the same splice with padding between the halves. The 193 lines against pypdf's 350 is the symptom: roughly half as many lines, each roughly twice as wide. **This is the single most dangerous failure mode available to this project** — the text is fluent, the Greek is perfect, nothing raises, and every sentence is wrong.

**2. pypdf got the column order right, by luck rather than by analysis.** It emits text in PDF *content-stream* order, which for a document laid out in InDesign or Distiller usually follows the text frames — left column, then right. It performs no layout analysis, so there is nothing to configure and nothing to verify: when a producer writes the stream in a different order, pypdf will be wrong in exactly the same silent way and there is no switch to turn. pdfplumber's advantage is the inverse: its default is wrong, but it exposes word coordinates, so cropping the page into two column boxes makes correctness *checkable* instead of lucky.

**3. The two documents in the corpus were produced by different toolchains, so neither result generalises from one to the other.** From the PDF metadata: ν. 5110/2024 is `PScript5.dll` → `Acrobat Distiller 11.0` → `PDFsharp`, re-signed with `OpenPDF/jsign`; π.δ. 62/2025 is `Adobe InDesign 18.5` → `Adobe PDF Library 17.0`, modified with `iTextSharp`. The probe must be run on both before anything is chosen.

**4. The confusable warning is now measured, not predicted.** In ν. 5110/2024's page header, `ΕΦΗΜΕΡΙ∆Α` contains **U+2206 INCREMENT** — a mathematical operator — where Greek Δ (U+0394) belongs, and `TΗΣ` begins with **U+0054 LATIN CAPITAL LETTER T**. π.δ. 62/2025 has the Latin `T` but a real Greek `Δ`. Both survive NFC untouched, because NFC unifies *equivalent encodings of the same character* and these are simply different characters. Step 4's normalization therefore needs an explicit confusable-folding map, exactly as [[Greek Legislation Structure]] predicted — and the fold must be applied to queries too ([[V5 - Hybrid Retrieval]]), or a user typing a real Greek Δ will fail to match the corpus.

**5. Hyphenation has two shapes, in the same paragraph.** `ερ-\nγοδότη` (no space) and `δι -\nμήνου` (space before the hyphen) both occur on π.δ. 62/2025 page 40. A de-hyphenation rule matching `-\n` alone silently leaves the second one broken.

**Blind spot in the probe's own census, worth knowing before trusting its numbers:** it only inspects whitespace-delimited tokens that contain at least one Greek character. pypdf renders the ν. 5110 header as `T ΗΣ` with a space, so the Latin `T` becomes a token of its own and is *not* counted — which is why pypdf's census shows 3 foreign characters and pdfplumber's shows 6 for the same page. The census undercounts; it never overcounts.

### Step 3 closed — 2026-09-14

`greek_law.ingestion.extraction` turns a manifest entry into `ExtractedDocument(document_id, pages)`, one `ExtractedPage` per PDF page, **uncleaned**. Extraction and normalization are deliberately separate: a normalization change should never require re-reading 260 pages of PDF.

**`ExtractedPage.number` is the PDF index, not the printed gazette page.** PDF page 6 of ν. 5110/2024 carries «3188» in its header. Citations ([[V6 - Legal Structure and Citations]]) need the printed number, and recovering it means parsing the header — step 4's job. Conflating the two would produce well-formed, confident, wrong citations: V1's failure mode relocated one layer down.

**The guard, and what it cannot do.** `pages_with_suspicious_line_width` reports pages whose median line width exceeds 1.5× the *document's own* median. Self-calibrating, so a single-column act does not report every page. The cost of self-calibration is a blind spot that is real and is not worked around: **a document spliced on every page moves its own baseline and reports nothing.** `test_a_document_spliced_on_every_page_is_not_flagged` pins that as a decision rather than a surprise, so anyone who later reads the function and assumes it guarantees correct columns is contradicted by the suite. The defences for that case are the golden files in step 9 and reading the output in step 10.

**It already earned its keep.** Over both documents: median width 51.0 each, no flags on the 260-page π.δ., and **one flag — page 60 of ν. 5110/2024**, the Εθνικό Τυπογραφείο colophon (Καποδιστρίου 34, phone numbers, `www.et.gr`), full-width boilerplate rather than law. A true positive for unusual layout and a requirement for step 4: **every ΦΕΚ ends with that page and it must be dropped.**

**Step 4's target list is now measured rather than predicted:** confusable folding (U+2206 INCREMENT for Δ, U+0054 LATIN T for Τ), de-hyphenation in its two observed shapes (`ερ-\nγοδότη` and `δι -\nμήνου`), per-page header removal whose *shape differs per document* (the ν. 5110 header arrives as one line with the page number glued on, the π.δ.'s as three separate lines), and the trailing colophon page.

_Freeform notes, gotchas, links, technical debt._
