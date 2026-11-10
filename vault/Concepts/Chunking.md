# Chunking

Part of [[Home]]. First applied in [[V2 - Document Ingestion]] (step 6); consumed by [[V3 - First RAG System]], measured in [[V4 - Question to Relevant Law]] and [[V5 - Hybrid Retrieval]].

## What it is / problem it solves

Cutting a document into the pieces a retrieval system stores, scores and returns. One embedding vector stands for a whole chunk, so the chunk is the unit of everything downstream:

- **What can be found.** A chunk about ten things has a vector that sits near none of them. A chunk too small to say what it is about has a vector that sits near nothing useful.
- **What can be cited.** An answer can only point as precisely as the chunk boundary. A chunk that is a whole article can be cited as «άρθρο 84», never as «άρθρο 84 παρ. 3».
- **What fits.** Embedding models read a bounded input — around 512 tokens for many multilingual models, 8 000 for others — and most **silently truncate** the rest rather than failing.

Three families of strategy, in increasing awareness of the text:

1. **Fixed-size windows** (N characters/tokens, often with overlap). No knowledge of the document; cuts mid-sentence and mid-provision. The default in most RAG tutorials.
2. **Recursive / separator-based** (split on blank lines, then sentences, then words, until under N). Respects prose, knows nothing about legal structure.
3. **Structure-aware** — cut on the document's own units. Legislation hands these over for free: article, paragraph, case.

## Why we're using it here

_2026-11-10, V2 step 6._ **Structure-aware, one chunk per paragraph (παράγραφος).** The paragraph is the only unit where one chunk is exactly one citable provision, which is the product's whole promise per [[Home]]. Measured on the corpus: 2 136 paragraphs, median 369 characters, against 701 articles with median 1 172 and 74 over 4 000.

Two techniques make paragraph-sized chunks work:

- **A contextual header on the embedded text only.** 56 paragraphs are under 80 characters («2. Η παρ. 1 ισχύει από 1.1.2025.») and say nothing about their subject. The text that gets embedded is `citation + article title + blank line + paragraph`; the text that gets *shown* is the paragraph as printed. Two representations of one chunk, derived from the same fields so they cannot disagree. This is a simple form of what the literature calls *contextual retrieval* / *contextual chunk headers*.
- **Oversize is reported, not fixed blind.** 25 paragraphs exceed 4 000 characters of embedding text. They are kept whole and listed by `oversized_chunks` until the embedding model — and so the real limit — is chosen in V3. Splitting before knowing the limit means guessing a number.

The chunk also carries **metadata that is not embedded**: the manifest `document_id` (the link back to the exact PDF) and the container path (ΜΕΡΟΣ/ΚΕΦΑΛΑΙΟ…) for filtering. Document-level facts stay in the manifest, joined by id — the same reasoning as a foreign key over denormalised columns.

## Alternatives considered

- **One chunk per article** — fewer, more complete chunks; citation stops at article level, and the 74 large articles blur or truncate.
- **Merge small paragraphs within an article up to a size budget** — even sizes and no fragments; a chunk becomes «παρ. 2–4» and stops being one citation.
- **Fixed-size windows** — rejected before measuring: they cut provisions mid-sentence and break citation precision, and legal text already provides better boundaries.
- **For oversized paragraphs:** split by size at sentence boundaries (the planned fix once V3 knows the limit), or by legal structure at case markers α), β) and quoted articles (best boundaries, most work, reopens step 5d decisions).

## Used in

- [[V2 - Document Ingestion]] — step 6 (unit, header, oversize report), step 7 (metadata).
- [[V3 - First RAG System]] — step 3 chooses the embedding model and therefore the limit `oversized_chunks` should be checked against; step 4 upserts on `Chunk.key`.
- [[V4 - Question to Relevant Law]] — error analysis is where a header or chunk-size change has to earn its place.

## Notes

- **Python for a Java developer:** `Chunk.header` and `Chunk.embedding_text` are `@property` — a getter computed from final fields, with no backing field. See [[Python for Java Developers]].
- **Open ideas, not decisions:** adding the act title or the container path to the header; unwrapping the gazette's line breaks inside a paragraph (tables depend on them, so not blindly).
