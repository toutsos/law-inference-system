"""Step 9: golden files — the whole output compared, not a sample of it.

Every other test checks a hand-picked example or a count. These compare the
pipeline's *entire* output against a reviewed copy, so a change that keeps
every count right — a line moved from one paragraph to the next — still fails,
with a diff naming it. They are what makes the deferred ``structure.py`` split
and V6's paragraph pages safe to attempt: a refactor must change nothing here.

Two layers, by the step 9 decision:

- **A — a committed excerpt.** ``tests/fixtures/golden/`` holds 270 real lines
  of ν. 5110/2024's raw extraction (eight pages, cut to quoting scale) and its
  expected chunk and report files. Runs in the default suite; a change shows
  up as a git diff. It starts from text, so it covers everything after pypdf.
- **B — a local snapshot of the full corpus.** ``data/golden/`` holds the four
  files ``poe ingest`` wrote when last accepted. Git-ignored like the rest of
  ``data/``, because a downloaded ΦΕΚ never enters git. Covers pypdf and all
  2 136 chunks.

Accept an intended change with ``uv run pytest --update-golden`` (add
``-m "slow or not slow"`` to include the corpus snapshot), then review the diff.
"""

from pathlib import Path

import pytest

from greek_law.ingestion import DEFAULT_MANIFEST_PATH, CorpusDocument, load_manifest
from greek_law.ingestion.extraction import extract_document
from greek_law.ingestion.ingest import main
from greek_law.ingestion.processed import (
    chunks_path,
    ingest_extracted,
    report_path,
    write_processed,
)
from tests.golden import assert_matches_golden, read_pages

FIXTURES = Path(__file__).parent / "fixtures" / "golden"
EXCERPT_ID = "fek_a_75_2024_excerpt"
EXCERPT_PAGES = FIXTURES / f"{EXCERPT_ID}.pages.txt"
CORPUS_GOLDEN = Path("data/golden")


def _excerpt_entry() -> CorpusDocument:
    """ν. 5110/2024's real manifest entry, under the excerpt's own id.

    The act identity must be the real one — ``chunk_act`` refuses a manifest
    entry for a different act — while the id says these chunks came from the
    excerpt, not from the published file.
    """
    real = next(
        entry
        for entry in load_manifest(DEFAULT_MANIFEST_PATH).documents
        if entry.id == "fek_a_75_2024"
    )
    return real.model_copy(update={"id": EXCERPT_ID})


def test_the_excerpt_reads_as_the_eight_pages_it_names() -> None:
    """The fixture loads as PDF pages 10, 16, 17, 20, 57, 58, 59 and 60.

    The page numbers are the real ones, kept so each line can be traced back
    to the gazette page it was cut from. Page 59 is the real blank page that
    sits between the signatures and the colophon; losing it would drop the
    one case of an empty page from the fixture without anything failing.
    """
    document = read_pages(EXCERPT_PAGES, EXCERPT_ID)

    assert [page.number for page in document.pages] == [10, 16, 17, 20, 57, 58, 59, 60]
    assert document.pages[6].text == ""


def test_the_excerpt_matches_its_golden_files(
    tmp_path: Path, update_golden: bool
) -> None:
    """The excerpt's chunks and report are byte-identical to the committed ones.

    The excerpt was cut to carry the cases that have broken before: a word
    split across a page boundary («λο-» / «γιστών»), a capitals dash kept
    («ΣΚΟΠΟΣ -» / «ΔΙΑΡΚΕΙΑ»), container headings in both namespaces, the
    καταστατικό opening in άρθρο 13 and closing in άρθρο τριακοστό, an
    amendment quoting another act's paragraphs (6 quoted markers), unnumbered
    and numbered paragraphs, and the enactment, signatures, blank page and
    colophon that must all be trimmed. Any change to how any of them comes
    out fails here with a diff.
    """
    entry = _excerpt_entry()
    write_processed(
        tmp_path, ingest_extracted(entry, read_pages(EXCERPT_PAGES, entry.id))
    )

    for path in (chunks_path(tmp_path, entry.id), report_path(tmp_path, entry.id)):
        assert_matches_golden(path, FIXTURES / path.name, update=update_golden)


def test_a_changed_output_fails_and_shows_the_changed_line(tmp_path: Path) -> None:
    """One differing line fails the comparison, and the message contains it.

    A golden helper that passes on any input is the classic way this kind of
    test rots: green forever, checking nothing. The diff in the message is
    what makes a failure actionable instead of a bare "files differ".
    """
    golden = tmp_path / "golden.jsonl"
    output = tmp_path / "output.jsonl"
    golden.write_text('{"text":"υποχρέωση"}\n', encoding="utf-8")
    output.write_text('{"text":"υπο - χρέωση"}\n', encoding="utf-8")

    with pytest.raises(pytest.fail.Exception, match="υπο - χρέωση"):
        assert_matches_golden(output, golden, update=False)


def test_a_missing_golden_file_fails_rather_than_being_created(
    tmp_path: Path,
) -> None:
    """No golden file means failure, and the file is still absent afterwards.

    If a missing golden were written on first run, a never-reviewed output
    would become the reference without anyone choosing it — and a typo in a
    golden path would pass forever by recreating itself each time.
    """
    output = tmp_path / "output.jsonl"
    output.write_text("{}\n", encoding="utf-8")
    golden = tmp_path / "missing" / "golden.jsonl"

    with pytest.raises(pytest.fail.Exception, match="--update-golden"):
        assert_matches_golden(output, golden, update=False)
    assert not golden.exists()


def test_update_overwrites_the_golden_file_with_the_output(tmp_path: Path) -> None:
    """With ``update``, the golden file becomes a copy of the output.

    The one deliberate way to accept a change. If it wrote anywhere else, or
    not at all, ``--update-golden`` would report success while the next plain
    run kept failing against the old file.
    """
    output = tmp_path / "output.jsonl"
    output.write_text('{"text":"νέο"}\n', encoding="utf-8")
    golden = tmp_path / "golden" / "golden.jsonl"

    assert_matches_golden(output, golden, update=True)

    assert golden.read_bytes() == output.read_bytes()


@pytest.mark.slow
def test_every_excerpt_line_is_real_text_from_the_page_it_names() -> None:
    """Each fixture line occurs, verbatim, on its named page of the real PDF.

    The excerpt is quoted, never written: it is only worth having if it is what
    pypdf actually produces. A line edited by hand — or an editor stripping the
    trailing spaces pypdf leaves on half the lines — would turn the fixture into
    something the pipeline never sees, and this names the line that drifted.
    """
    real = next(
        entry
        for entry in load_manifest(DEFAULT_MANIFEST_PATH).documents
        if entry.id == "fek_a_75_2024"
    )
    pages = {
        page.number: page.text.split("\n") for page in extract_document(real).pages
    }

    for page in read_pages(EXCERPT_PAGES, EXCERPT_ID).pages:
        if not page.text:
            assert pages[page.number] == [""], page.number
            continue
        for line in page.text.split("\n"):
            assert line in pages[page.number], (page.number, line)


@pytest.mark.slow
def test_the_corpus_matches_its_local_golden_snapshot(
    tmp_path: Path, update_golden: bool
) -> None:
    """``poe ingest`` reproduces ``data/golden/`` byte for byte, all four files.

    The full-corpus net: pypdf included, every one of the 2 136 chunks and both
    reports. The excerpt cannot catch a change that only shows on the whole
    document — rule 3 choosing a different body run, a page offset drifting on
    page 200 — and this can. The snapshot is local; create it once with
    ``uv run pytest -m "slow or not slow" --update-golden`` after reviewing
    the output of ``poe ingest``.
    """
    assert main(["--out", str(tmp_path)]) == 0

    for path in sorted(tmp_path.iterdir()):
        assert_matches_golden(path, CORPUS_GOLDEN / path.name, update=update_golden)
