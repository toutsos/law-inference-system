import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from greek_law.ingestion import (
    DEFAULT_MANIFEST_PATH,
    CheckOutcome,
    CorpusDocument,
    Manifest,
    check_document,
    check_manifest,
    load_manifest,
    sha256_of,
)
from greek_law.ingestion.verify import main

_CONTENT = "ΦΕΚ".encode()
_CONTENT_SHA256 = hashlib.sha256(_CONTENT).hexdigest()


def _entry(**overrides: object) -> dict[str, object]:
    """A valid manifest entry, so each test can break exactly one field."""
    entry: dict[str, object] = {
        "id": "fek_a_75_2024",
        "act": {"act_type": "ν.", "number": "5110", "year": 2024, "fek": "Α' 75"},
        "title": "Ίδρυση Ελληνικού Κέντρου Αμυντικής Καινοτομίας",
        "file": "data/raw/fek_a_75_2024.pdf",
        "sha256": _CONTENT_SHA256,
        "size_bytes": len(_CONTENT),
        "source_url": "https://search.et.gr/el/fek/?fekId=1",
        "retrieved_on": "2026-09-07",
    }
    entry.update(overrides)
    return entry


def _manifest(*entries: dict[str, object]) -> Manifest:
    return Manifest.model_validate({"manifest_version": 1, "documents": list(entries)})


def _write_corpus(root: Path, content: bytes = _CONTENT) -> None:
    """Put the file the default entry claims exists on disk under `root`."""
    raw = root / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "fek_a_75_2024.pdf").write_bytes(content)


def test_the_committed_manifest_parses() -> None:
    """corpus/manifest.json is valid against the schema, as committed.

    The manifest is hand-edited JSON — a trailing comma, a hash pasted with a
    stray space, or a missing field are all one keystroke away. Nothing else in
    the suite reads the real file, so without this the corpus could be
    undescribable and every test would still be green until someone ran an
    ingest.
    """
    manifest = load_manifest(DEFAULT_MANIFEST_PATH)

    assert manifest.documents, "the manifest describes no documents"


def test_a_misspelled_field_name_is_rejected() -> None:
    """An unknown key fails validation instead of being ignored.

    `extra="forbid"` is doing load-bearing work here. With Pydantic's default,
    writing "sha_256" instead of "sha256" would parse, and the entry would then
    be missing its hash — so verification would compare against nothing and the
    provenance claim would be silently empty.
    """
    with pytest.raises(ValidationError):
        Manifest.model_validate(
            {"manifest_version": 1, "documents": [_entry(sha_256=_CONTENT_SHA256)]}
        )


def test_a_hash_that_is_not_a_sha256_is_rejected() -> None:
    """The sha256 field must be 64 lowercase hex characters.

    Catches the two realistic paste accidents: copying `shasum`'s full output
    ("<hash>  data/raw/x.pdf") into the field, and copying an MD5 or SHA-1 from
    some other tool. Both would make every future check report MISMATCH, and
    the manifest — not the corpus — would be the thing at fault.
    """
    with pytest.raises(ValidationError):
        CorpusDocument.model_validate(_entry(sha256=f"{_CONTENT_SHA256}  file.pdf"))


def test_sha256_of_a_file_matches_hashlib() -> None:
    """sha256_of reads bytes, not text, and uses SHA-256.

    Greek filenames and Greek content make an accidental text-mode read or a
    locale-dependent encoding plausible, and either would produce a stable but
    wrong digest — stable enough that it would look correct until a second
    machine computed a different one and the corpus appeared corrupt.
    """
    path = Path(__file__).parent / "fixtures_sha256_probe.bin"
    path.write_bytes(_CONTENT)
    try:
        assert sha256_of(path) == _CONTENT_SHA256
    finally:
        path.unlink()


def test_a_present_and_unmodified_file_is_ok(tmp_path: Path) -> None:
    """The happy path: file on disk, bytes match the manifest.

    The baseline in V1 transcribed ground truth by hand from one PDF. This is
    the assertion that the PDF on this machine is that PDF; if it never
    returned OK the check would be decoration.
    """
    _write_corpus(tmp_path)

    result = check_document(_manifest(_entry()).documents[0], tmp_path)

    assert result.outcome is CheckOutcome.OK


def test_an_absent_file_is_reported_as_missing_with_its_url(tmp_path: Path) -> None:
    """A file not on disk reports MISSING and names where to get it.

    `data/` is git-ignored, so a fresh clone has an empty corpus — this is the
    normal first-run state, not a corruption. The URL belongs in the message
    because the manifest is the only place it exists, and a reader who has to
    go find the manifest to act on the error is one step from guessing.
    """
    result = check_document(_manifest(_entry()).documents[0], tmp_path)

    assert result.outcome is CheckOutcome.MISSING
    assert "https://search.et.gr/el/fek/?fekId=1" in result.detail


def test_changed_bytes_are_reported_as_mismatch(tmp_path: Path) -> None:
    """A file whose content differs reports MISMATCH, not OK.

    This is the check's reason to exist: et.gr could re-issue a corrected ΦΕΚ
    under the same URL, or a download could truncate. Either leaves a
    plausible-looking PDF in place, and the answers measured against it would
    be attributed to the wrong text.
    """
    _write_corpus(tmp_path, content=b"a different document")

    result = check_document(_manifest(_entry()).documents[0], tmp_path)

    assert result.outcome is CheckOutcome.MISMATCH


def test_every_document_is_checked_even_after_one_fails(tmp_path: Path) -> None:
    """Checking does not stop at the first failure.

    With five documents and three missing, a fail-fast loop makes the learner
    re-run the command three times, downloading one file per round. Catches a
    refactor to `next(...)` or an early return.
    """
    _write_corpus(tmp_path)
    manifest = _manifest(
        _entry(id="missing_one", file="data/raw/absent.pdf"),
        _entry(),
    )

    results = check_manifest(manifest, tmp_path)

    assert [r.outcome for r in results] == [CheckOutcome.MISSING, CheckOutcome.OK]


def test_verify_exits_nonzero_when_a_document_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The CLI's exit code is 1 when anything is missing or altered.

    An exit code is the only part of this a CI step or a shell `&&` can see.
    Catches the command printing MISSING in red and still returning 0, which
    would let a later pipeline run against a corpus nobody verified.
    """
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"manifest_version": 1, "documents": [_entry()]}),
        encoding="utf-8",
    )

    exit_code = main(["--manifest", str(manifest_path), "--root", str(tmp_path)])

    assert exit_code == 1
    assert "MISSING" in capsys.readouterr().out


def test_verify_exits_zero_when_the_corpus_is_intact(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The CLI returns 0 and says how many documents it verified.

    The counterpart to the test above: an exit code that is always 1 is as
    useless as one that is always 0, and `1/1 documents verified.` is what
    tells a human the check actually ran rather than finding an empty list.
    """
    _write_corpus(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"manifest_version": 1, "documents": [_entry()]}),
        encoding="utf-8",
    )

    exit_code = main(["--manifest", str(manifest_path), "--root", str(tmp_path)])

    assert exit_code == 0
    assert "1/1 documents verified." in capsys.readouterr().out


def test_every_document_the_baseline_experiment_names_is_in_the_manifest() -> None:
    """questions.json's corpus_document_id resolves to a real manifest entry.

    V1's ground truth was transcribed by hand from one PDF, and `data/` is
    git-ignored, so the manifest entry is the only committed statement of which
    document that was. A typo in the id, or an entry deleted from the manifest,
    would leave the experiment pointing at nothing — and the failure would
    surface as an unexplained drop in V3's retrieval scores, not as an error.
    """
    questions = json.loads(
        Path("experiments/baseline_no_rag/questions.json").read_text(encoding="utf-8")
    )
    known = {document.id for document in load_manifest(DEFAULT_MANIFEST_PATH).documents}

    assert questions["source"]["corpus_document_id"] in known
