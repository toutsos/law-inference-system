# Greek Legislation Structure

Part of [[Home]]. The domain model this project is built on. Established in [[V0 - Project Foundation]] (step 11), extended in [[V6 - Legal Structure and Citations]].

Domain knowledge below is the learner's (2026-08-25); the engineering framing is the tutor's.

## The hierarchy

```
Νόμος
 └── Μέρος            (large thematic division, when used)
      └── Τμήμα        (sometimes used)
           └── Κεφάλαιο       (thematic subdivision)
                └── Υποκεφάλαιο   (sometimes used)
                     └── Άρθρο           (the primary numbered provision)
                          └── Παράγραφος     (1., 2., 3.)
                               ├── Εδάφιο         (a sentence / syntactic unit)
                               └── Περίπτωση      ((α), (β), (γ) — or α), β) …)
                                    └── Υποπερίπτωση  ((αα), (αβ) …)
```

**Depth is not uniform.** A law may use some or all of these, and some laws add further organizational units. One article may contain only παράγραφοι; another may go παράγραφοι → περιπτώσεις → υποπεριπτώσεις. Any model that assumes a fixed number of levels will be wrong on the second law it meets.

## The key distinction: addressable units vs organizational containers

The insight that makes variable depth tractable. Look at a real citation:

> Ν. 4808/2021, άρθρο 4 παρ. 2 περ. α΄

**Κεφάλαιο does not appear.** Nobody cites "Κεφάλαιο Β΄" as the source of a rule.

| | Levels | Properties |
| --- | --- | --- |
| **Addressable units** | Άρθρο, Παράγραφος, Περίπτωση, Υποπερίπτωση | Appear in citations, carry normative text, must be individually retrievable. **This set is stable across laws.** |
| **Organizational containers** | Μέρος, Τμήμα, Κεφάλαιο, Υποκεφάλαιο | Vary between laws, nest inconsistently, carry titles rather than rules, **never appear in a citation**. |

The variable-depth part of Greek legislation is exactly the part that is not addressable. So: model the addressable spine with real types, and carry the containers as a **path** — an ordered list of `(kind, number, title)` attached to the Άρθρο.

That retains the breadcrumb (useful as prompt context: *"this article sits in Κεφάλαιο Β΄, Employment Protection"*) without needing a class for every organizational unit a drafter might invent.

## Identifying a provision: identity + path

> **[identity of the νομοθέτημα] + [path inside the νομοθέτημα]**

`άρθρο 4` alone is meaningless — every law has one.

**Identity of the act:**

- Τύπος νομοθετικού κειμένου (Νόμος, Π.Δ., ΚΥΑ, …)
- Αριθμός — e.g. 4808
- Έτος — e.g. 2021
- ΦΕΚ — the authoritative publication reference, e.g. `ΦΕΚ Α΄ 101/19.06.2021`

**Path within the act:** Άρθρο → Παράγραφος → Περίπτωση → Υποπερίπτωση, each optional below the article.

Rendered for a human:

> Ν. 4808/2021, άρθρο 4 παρ. 2 περ. α΄, ΦΕΚ Α΄ 101/19.06.2021

**Store the reference structurally, not as a string**, and generate the human-readable citation from the structure. A string citation cannot be filtered, compared, or validated.

## Representation: nested canonical, flat index

- **Canonical representation: nested** — because the legal structure genuinely is hierarchical, and the nesting carries meaning.
- **Retrieval representation: flat** — a stable identifier such as `Ν.4808/2021/άρθρο-3Α/παρ-2/περ-α` makes indexing, deduplication, and foreign keys from the vector store straightforward.
  _Corrected 2026-08-29: this example originally read `N4808-2021/ART10/P2/CASE-a`, which contradicts the identifier-alphabet decision below. A Latin key alongside Greek source text is exactly the second representation that decision exists to avoid, so `SourceReference.key` is Greek throughout._

**Derive the flat identifier; do not store it.** It should be a computed property of the structure, not a settable field. A stored id can drift out of agreement with the tree it claims to describe; a derived one cannot. It is persisted only in the vector database, as a key back into the canonical structure.

## Modelling decision (2026-08-25): hybrid

Three options were weighed. The question that separates them: **is the containment genuinely self-similar?** (A folder contains folders — recursion is honest. A book contains chapters contains pages — a page cannot contain a chapter, so recursion would be a lie.)

- **Recursive node** — one `Provision(kind, number, text, children)` type for everything. Handles any structure, uniform ingestion; but nothing prevents a παράγραφος containing a νόμος, `kind` is a stringly-typed field open to typos, every consumer branches on it, and no type checker or editor can help.
- **Fixed types** — one class per level. Self-documenting, containment enforced, invalid trees unrepresentable; but no home for Κεφάλαιο without a class per container, and depth is capped — each new lettered level needs a new class.
- **Hybrid — chosen.** Learner's reasoning: *"there are many optional parts in the flow."*

Applying the self-similarity test to this hierarchy gives different answers in different places, which is exactly why the hybrid wins:

| Containment | Self-similar? | Modelled as |
| --- | --- | --- |
| Άρθρο → Παράγραφος | No — a παράγραφος never contains an άρθρο | Fixed types |
| Περίπτωση → Υποπερίπτωση | **Yes** — both are lettered items carrying text, the same shape one level down | Recursion (`Case.subcases: list[Case]`) |
| Μέρος / Κεφάλαιο → Άρθρο | Non-addressable, varies per law | Data, not classes — a `path: list[StructuralUnit]` on `Article` |

### Where the text lives (2026-08-25)

Articles occur as: τίτλος + παρ. 1,2,3 (common); τίτλος + unnumbered text and no paragraphs; τίτλος + introductory text *then* παρ. 1.

Options: (a) `Article.text` for loose text alongside `Article.paragraphs`; (b) all normative text lives in a `Paragraph`, with unnumbered text carried by a `Paragraph` whose `number is None`.

**Chosen: (b).** Under (a), normative text lives in two places, so V2's chunker, V3's retriever and V6's citation builder each need to handle both. The citation settles it: a paragraph with `number=None` renders as *"Ν. 4808/2021, άρθρο 4"* — no παρ. component, which is the correct citation for unnumbered article text. Uniformity without inventing a "παρ. 0" that does not exist in the law.

`Article.title` stays separate: a τίτλος is a heading, not a provision, and is never cited.

### Identifier alphabet (2026-08-25)

**Keep Greek characters. NFC-normalize at ingestion. Do not transliterate.**

Transliteration (`3Α` → `3A`, `περ. α΄` → `case-a`) buys tidier keys at the price of a second representation to keep in sync forever, plus a mapping table that will eventually be wrong. Keeping source characters means one representation.

Accepted cost: [[V2 - Document Ingestion]] must normalize everything on the way in, and [[V5 - Hybrid Retrieval]] must normalize queries **with the same function**, or a user typing Latin `A` will not match Greek `Α`.

#### Correction (2026-08-29): NFC is not sufficient

Measured against the real corpus — first text extraction from ΦΕΚ Α΄ 121/11.07.2025, page 6:

| Where | What it actually contains | Codepoints |
| --- | --- | --- |
| Masthead `ΕΦΗΜΕΡΙΔΑ TΗΣ ΚΥΒΕΡΝΗΣΕΩΣ` | `T` is **Latin** | U+0054 + U+0397 U+03A3 |
| `Τεύχος A’ 121` | `A` is **Latin**, where τεύχος Α΄ is meant | U+0041 |
| `ΥΠΟΚΕΦΑΛΑΙΟ Α’` | Greek Α, but the mark is a **right single quote** | U+0391 + U+2019 |
| What `SourceReference.citation` renders | Greek Α + **Greek tonos** | U+0391 + U+0384 |

So the official gazette mixes scripts *inside a single word* in its own masthead, and marks ordinals with U+2019 rather than the U+0384 our renderer emits.

**NFC does not fix any of this.** NFC composes/decomposes accents — `ά` as one codepoint versus alpha + combining acute. It will never map Latin `A` to Greek `Α`, nor `’` to `΄`; they are semantically distinct characters, not alternate encodings of one character.

Normalization therefore needs **two** stages, and the second is a project decision, not a Unicode standard:

1. **NFC** — accent composition. Standard, safe, non-negotiable.
2. **Confusable folding** — an explicit map (Latin `A`→Greek `Α`, `B`→`Β`, `E`→`Ε`, `H`→`Η`, `I`→`Ι`, `K`→`Κ`, `M`→`Μ`, `N`→`Ν`, `O`→`Ο`, `P`→`Ρ`, `T`→`Τ`, `X`→`Χ`, `Y`→`Υ`, `Z`→`Ζ`, plus `’`/`'`/`΄`→ one chosen mark). Applied to *identifiers* — article numbers, ordinals — and to queries with the same function. Applying it to body text is a separate call, since Latin characters legitimately appear there (EU directive references, trade names).

Owned by [[V2 - Document Ingestion]]; the fix is one shared function, and the risk is having two.

## Traps

### 1. Article numbers are strings, and homoglyphs will bite

Amendments insert articles *between* existing ones: `Άρθρο 3Α`, `Άρθρο 3Β`. So `number: int` is wrong before a single document has been read.

Worse: **Greek `Α` (U+0391) and Latin `A` (U+0041) are visually identical.** A Latin-alphabet identifier scheme (`.../ART10/...`) alongside source text containing Greek `3Α` means `"3Α" == "3A"` is `False` while looking `True` on screen. Decide which alphabet identifiers use **before** ingestion, and have [[V2 - Document Ingestion]] enforce it during normalization. The same class of problem governs lexical matching in [[V5 - Hybrid Retrieval]].

### 2. Where does the text live? — resolved 2026-08-25

**Answered:** all normative text lives in a `Paragraph`; unnumbered article text is a `Paragraph` with `number=None`. See "Where the text lives" above. Retained here because the reasoning matters.

Original framing: Greek articles typically carry a τίτλος plus numbered paragraphs — but some have unnumbered introductory text before παρ. 1. If only `Παράγραφος` holds text, that introductory text has no home. This decides the chunking strategy in [[V2 - Document Ingestion]], so it must be answered before ingestion is designed.

### 3. Temporal validity

Raised by the learner unprompted: a citation should identify the **version** of the provision supporting the answer. Provisions get τροποποιηθεί, καταργηθεί, αντικατασταθεί, so `Ν. X/XXXX, άρθρο Y` may not establish what the law said at a given time.

Correct, and **deliberately out of scope for V0–V3** — [[Home]] lists amendment-awareness as a long-term extension and [[V6 - Legal Structure and Citations]] handles provenance. Building it now would repeat the empty-package mistake from V0 step 5.

**Cheap accommodation that preserves the option:** record which *snapshot* is held — the ΦΕΚ reference plus the retrieval date. The model then does not implicitly claim to be timeless, and later work can tell whether a provision has since moved. Record what is held; do not model amendment chains.


## Implemented model (2026-08-29)

Step 11 of [[V0 - Project Foundation]]. One module per model in `src/greek_law/domain/`, all re-exported from the package.

| Model | Role |
| --- | --- |
| `ActIdentity` | τύπος + αριθμός + έτος + ΦΕΚ — what makes "άρθρο 4" mean something |
| `Act` | identity + title + `retrieved_on` snapshot + articles |
| `Article` | `number: str`, `title`, `path: list[StructuralUnit]`, `paragraphs` |
| `Paragraph` | `number: str \| None`, `text`, `cases` |
| `Case` | `number`, `text`, `subcases: list[Case]` — the one recursive type |
| `StructuralUnit` | `kind`, `number`, `title` — containers as data |
| `SourceReference` | `act` + `article` + `paragraph` + `cases: list[str]`; `.citation` and `.key` derived |

Named `Act`, not `Law`: the corpus will include Π.Δ. and ΚΥΑ, which are not νόμοι.

All six are frozen and forbid unknown fields — see [[Immutable Domain Models]]. `Article.path` is a *materialized path*: the ordered list encodes containment, and the container tree is reconstructable by grouping on path prefixes. This matters because chapter numbering restarts inside each Μέρος, so `Κεφάλαιο Α΄` alone is ambiguous while `Μέρος Β΄ › Κεφάλαιο Α΄` is not.

**Still owned by [[V2 - Document Ingestion]]:** NFC normalization. The models keep source characters verbatim and do not normalize, so until ingestion exists, two visually identical strings can both enter a model and compare unequal.

## Used in

- [[V0 - Project Foundation]] — step 11, the initial models.
- [[V2 - Document Ingestion]] — parsing this structure out of raw documents; normalization must resolve the homoglyph decision.
- [[V3 - First RAG System]] — chunk boundaries follow addressable units.
- [[V6 - Legal Structure and Citations]] — full hierarchy and canonical citations as structured data.
