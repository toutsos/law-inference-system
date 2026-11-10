# Golden-file fixtures

Used by `tests/test_golden.py`. See the step 9 decision in `vault/Versions/V2 - Document Ingestion.md`.

## `fek_a_75_2024_excerpt.pages.txt`: the input

270 lines of pypdf's **raw, un-normalized** output for ν. 5110/2024 (ΦΕΚ Α' 75/24.05.2024), cut from eight real PDF pages (10, 16, 17, 20, 57, 58, 59, 60). Each page opens with a `=== page N ===` line naming the real PDF page.

- **Quoted, never written.** Every line is verbatim pypdf output, including the trailing spaces it leaves on many lines. Don't edit by hand, and don't let an editor strip trailing whitespace. A slow test (`test_every_excerpt_line_is_real_text_from_the_page_it_names`) checks every line against the real PDF.
- **Quoting scale, by design.** A downloaded ΦΕΚ never enters git: search.et.gr's terms of use (§2.4) forbid redistributing what was downloaded, even though the legal text itself carries no copyright (ν. 2121/1993 άρθρο 2 §5). Quoting provisions is fine. This excerpt is 270 of the extraction's 6 743 lines, about 4% of the document. See `vault/Concepts/Corpus Sourcing and Licensing.md`.

## `fek_a_75_2024_excerpt.jsonl` / `.report.json`: the expected output

What `ingest_extracted` produces from the excerpt, reviewed and accepted. All 16 chunks match the full-PDF run's chunks for the same articles in text and title. The only difference is that άρθρο 13 has an empty path, because the excerpt cuts the ΜΕΡΟΣ Β΄ heading above it.

To accept an intended change: `uv run pytest --update-golden`, then **read the diff** before committing.
