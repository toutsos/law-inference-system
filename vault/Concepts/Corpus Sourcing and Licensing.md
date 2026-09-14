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

## 2b. The site's terms are a third layer — added 2026-09-14

Sections 1 and 2 answer "who owns the words". They do not answer "what did you agree to by downloading them". The **Όροι Χρήσης of `search.et.gr`** (`https://search.et.gr/el/oroi-xrisis/`) are a contract with the service, and they bind even though the text they deliver is public domain:

- **§1.2** — «Οι χρήστες έχουν πρόσβαση και χρησιμοποιούν τον Ιστότοπο **αποκλειστικά για προσωπικούς, πληροφοριακούς, μη εμπορικούς σκοπούς**.»
- **§2.4** — «Απαγορεύεται η **αναπαραγωγή του περιεχομένου του διαδικτυακού τόπου για εμπορικούς σκοπούς ή/και για μη προσωπική χρήση**… Υλικό από τον διαδικτυακό τόπο δεν επιτρέπεται να πωληθεί ή να διανεμηθεί με οποιονδήποτε άλλο τρόπο για κερδοσκοπικούς λόγους.»

The three layers resolve independently, and the strictest one wins in practice:

| Layer | Source | Says |
| --- | --- | --- |
| Copyright in the text | ν. 2121/1993 άρθρο 2 §5 | No protection. Quote it freely, at any length. |
| Right in the compilation | ν. 2121/1993 άρθρο 45Α | Belongs to whoever built the database — which is why aggregators are out. |
| Terms of the service used to obtain it | `search.et.gr` Όροι Χρήσης §1.2, §2.4 | Personal, informational, non-commercial. No redistribution of what you pulled. |

**The practical rule this produces:** a downloaded ΦΕΚ never enters git. Quoting a provision in an answer is fine at every layer — that is the copyright question, and it is settled. Committing the corpus is not, and the reason is the third layer alone. It is also why this project's educational, non-commercial framing in [[Home]] is load-bearing rather than decorative: change that and the download itself falls outside §1.2.

**The generalisable mistake to avoid:** "the content is public domain" and "I may republish what I downloaded" are different claims, and the first does not imply the second. The same split appears with permissively-licensed code behind a restrictive API, and with public data behind a terms-bound portal.

## 3. The primary source

**Εθνικό Τυπογραφείο** — `search.et.gr` (simple, advanced and semantic search over ΦΕΚ). Free PDF download of any issue.

**Reachability, checked 2026-09-14:** the ΦΕΚ search on `search.et.gr` is a front end for `nationalprintinghousefek.azurewebsites.net`, which did not resolve from the development machine's network on that date; `et.gr/api/DownloadFek/` returns 404. "Free PDF download of any issue" is therefore the policy, not a verified HTTP route — see the note in [[V2 - Document Ingestion]] for the commands that re-check it.

Accepted cost, carried into [[V2 - Document Ingestion]]: ΦΕΚ are **PDFs, not structured text**. Layout is two-column with headers, footers, page numbers and digital signature blocks that must be stripped. Whether a given issue has a usable text layer or needs OCR must be checked per document before committing to it — an unverified assumption here would be discovered halfway through building the parser.

## Used in

- [[V0 - Project Foundation]] — step 12, choosing the corpus.
- [[V2 - Document Ingestion]] — fetching and parsing; the "official source only" rule binds here.

## Notes

Attribution and version-awareness are *engineering* requirements here, not legal ones — see temporal validity in [[Greek Legislation Structure]] and the scope boundary in [[Home]].
