"""The committed description of a git-ignored corpus.

``data/`` is not in git — it is too large, and the terms of use of
``search.et.gr`` do not permit redistributing what was downloaded from it. So
the repository cannot contain the corpus, only a *description* of it precise
enough that a second machine can rebuild the same corpus and prove it did.

"Prove" is the word that matters. A list of URLs is a claim; a list of URLs
plus a SHA-256 per file is a claim that can fail. The hash is what ties
``experiments/baseline_no_rag/questions.json`` — whose ground truth was
transcribed by hand from one PDF — to the exact bytes it was transcribed from.
"""

import hashlib
from datetime import date
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from greek_law.domain import ActIdentity

DEFAULT_MANIFEST_PATH = Path("corpus/manifest.json")


class CorpusDocument(BaseModel):
    """One downloaded document, and everything needed to obtain it again."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    act: ActIdentity
    title: str
    file: Path
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(gt=0)
    source_url: HttpUrl
    retrieved_on: date
    note: str | None = None


class Manifest(BaseModel):
    """Every document in the corpus, as one committed file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_version: int
    documents: list[CorpusDocument]


class CheckOutcome(StrEnum):
    """The three states a manifest entry can be in against the disk."""

    OK = "ok"
    MISSING = "missing"
    MISMATCH = "mismatch"


class CheckResult(BaseModel):
    """What checking one entry found. Data, so the CLI owns the formatting."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: str
    outcome: CheckOutcome
    detail: str


def load_manifest(path: Path = DEFAULT_MANIFEST_PATH) -> Manifest:
    """Read and validate the manifest, or raise."""
    return Manifest.model_validate_json(path.read_text(encoding="utf-8"))


def sha256_of(path: Path) -> str:
    """Hash a file without loading it into memory."""
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def check_document(document: CorpusDocument, root: Path = Path()) -> CheckResult:
    """Compare one manifest entry against the file it claims is on disk."""
    path = root / document.file
    if not path.is_file():
        return CheckResult(
            document_id=document.id,
            outcome=CheckOutcome.MISSING,
            detail=f"not on disk at {path} — download it from {document.source_url}",
        )

    found = sha256_of(path)
    if found != document.sha256:
        return CheckResult(
            document_id=document.id,
            outcome=CheckOutcome.MISMATCH,
            detail=f"expected sha256 {document.sha256}, found {found}",
        )

    return CheckResult(
        document_id=document.id, outcome=CheckOutcome.OK, detail=str(path)
    )


def check_manifest(manifest: Manifest, root: Path = Path()) -> list[CheckResult]:
    """Check every entry. Never stops at the first failure — a partial corpus
    should report all of what is wrong with it in one run."""
    return [check_document(document, root) for document in manifest.documents]
