import pytest
from pydantic import ValidationError

from greek_law.domain import (
    Act,
    ActIdentity,
    Article,
    Case,
    Paragraph,
    SourceReference,
    StructuralUnit,
)


def test_unnumbered_paragraph_carries_article_text():
    """An article's opening text, before παρ. 1, is a Paragraph with no number.

    Greek articles often begin with unnumbered text. Modelling it as a normal
    Paragraph avoids a second type for "the bit at the top". Catches `number`
    becoming required, which would force ingestion to invent numbers that do
    not exist in the source — and inventing citations is the one failure this
    project cannot tolerate.
    """
    paragraph = Paragraph(text="Για την εφαρμογή του παρόντος νόμου...")

    assert paragraph.number is None


def test_cases_nest_recursively():
    """περιπτώσεις contain υποπεριπτώσεις, to arbitrary depth.

    Catches a flattening "simplification" — a single `cases: list[str]`, or a
    fixed two-level model. Either would make the deepest provision uncitable,
    and depth is exactly where legal obligations tend to live.
    """
    paragraph = Paragraph(
        number="2",
        text="Ο εργοδότης υποχρεούται:",
        cases=[
            Case(
                number="α",
                text="να ενημερώνει",
                subcases=[Case(number="αα", text="εγγράφως")],
            )
        ],
    )

    assert paragraph.cases[0].subcases[0].number == "αα"


def test_article_carries_its_container_path_without_a_class_per_container():
    """Μέρος/Κεφάλαιο/Τμήμα are data in a path, not one class each.

    Pins the V0 decision to model the hierarchy as `list[StructuralUnit]`.
    Catches the drift back toward `Part`/`Chapter`/`Section` classes, which
    would need a new type — and a new parser branch — for every container name
    the corpus turns out to use.
    """
    article = Article(
        number="4",
        title="Ορισμοί",
        path=[
            StructuralUnit(kind="Μέρος", number="Α΄"),
            StructuralUnit(kind="Κεφάλαιο", number="Β΄", title="Προστασία"),
        ],
    )

    assert [unit.kind for unit in article.path] == ["Μέρος", "Κεφάλαιο"]


def test_a_typo_in_a_field_name_is_rejected():
    """A misspelled field name raises instead of being quietly ignored.

    Without `extra="forbid"`, `titel=` would be dropped and the article would
    silently have no title. The bug would then look like a *parser* fault — the
    title vanished — with nothing pointing at the keyword typo that caused it.
    """
    with pytest.raises(ValidationError) as exc_info:
        Article(number="4", titel="Ορισμοί")  # type: ignore[call-arg]

    assert "titel" in str(exc_info.value)


def test_act_holds_its_identity_separately_from_its_content():
    """What an act *is* (type, number, year, ΦΕΚ) is separate from what it says.

    Identity is small, citable and stable; content is large and gets chunked.
    Keeping them apart is what lets a SourceReference name a provision without
    dragging the whole act along. Catches the two being flattened into one
    model, which would put the full text inside every citation.
    """
    act = Act(
        identity=ActIdentity(
            act_type="Ν.", number="4808", year=2021, fek="Α΄ 101/19.06.2021"
        ),
        title="Για την προστασία της εργασίας",
        articles=[Article(number="4")],
    )

    assert act.identity.year == 2021
    assert act.articles[0].number == "4"


@pytest.fixture
def act_identity():
    """A minimal citable act, shared by the citation and key tests below."""
    return ActIdentity(act_type="Ν.", number="4808", year=2021)


def test_citation_is_rendered_from_the_structure(act_identity):
    """The canonical Greek citation is derived, never stored as a string.

    Pins the exact conventional form, tonos and all. Catches a refactor that
    reorders the parts or drops a level: a citation a Greek lawyer cannot
    recognise makes the answer unverifiable, which is the whole product.
    """
    reference = SourceReference(
        act=act_identity, article="4", paragraph="2", cases=["α"]
    )

    assert reference.citation == "Ν. 4808/2021, άρθρο 4 παρ. 2 περ. α΄"


def test_citation_of_unnumbered_article_text_omits_the_paragraph(act_identity):
    """With no paragraph, the citation stops at the article.

    The boundary case for the renderer. Catches naive string building that
    would emit "άρθρο 4 παρ. None" — the classic optional-field-in-an-f-string
    bug, which produces output that looks authoritative and is nonsense.
    """
    reference = SourceReference(act=act_identity, article="4")

    assert reference.citation == "Ν. 4808/2021, άρθρο 4"


def test_subcase_citation_names_its_level(act_identity):
    """A nested case is cited as υποπερ., not as a second περ.

    Catches the renderer treating the `cases` list uniformly and labelling
    every level "περ." — which would cite a different provision from the one
    actually retrieved, while looking perfectly well-formed.
    """
    reference = SourceReference(
        act=act_identity, article="4", paragraph="2", cases=["α", "αα"]
    )

    assert reference.citation.endswith("περ. α΄ υποπερ. αα΄")


def test_retrieval_key_stays_in_the_greek_alphabet(act_identity):
    """The lookup key keeps Greek characters; it is not transliterated.

    Catches an ASCII-folding step added for "safe" identifiers. Latinising
    "3Α" to "3A" would collide with a genuinely different article and make
    retrieval return the wrong provision — silently, and only for the articles
    whose numbers happen to contain a confusable letter.
    """
    reference = SourceReference(
        act=act_identity, article="3Α", paragraph="2", cases=["α"]
    )

    assert reference.key == "Ν.4808/2021/άρθρο-3Α/παρ-2/περ-α"


def test_key_is_derived_and_cannot_be_set(act_identity):
    """`key` is computed from the structure and rejects being passed in.

    If it were an ordinary field, an ingestion bug could store a key that
    disagrees with the reference's own citation — the same provision indexed
    under two identities, which is unfixable once the store is populated.
    """
    with pytest.raises(ValidationError):
        SourceReference(act=act_identity, article="4", key="anything")  # type: ignore[call-arg]


def test_models_are_read_only():
    """Assigning to a field after construction raises.

    `frozen=True`, stated as a test. Everything downstream — caching, sharing
    instances between articles, using them as dict keys — assumes a model never
    changes after it is built. This is the assertion that assumption rests on.
    """
    article = Article(number="4", title="Ορισμοί")

    with pytest.raises(ValidationError) as exc_info:
        article.title = "Κάτι άλλο"  # type: ignore[misc]

    assert "frozen" in str(exc_info.value)


def test_a_shared_container_cannot_be_edited_through_one_article():
    """One shared StructuralUnit cannot be mutated via any article holding it.

    A parser hands the same StructuralUnit to every article in a chapter.
    Without frozen=True, editing it through one article silently rewrites the
    breadcrumb of every other article in that chapter — action at a distance,
    appearing as corrupted citations in documents nobody touched.
    """
    chapter = StructuralUnit(kind="Κεφάλαιο", number="Α΄", title="Γενικές διατάξεις")
    article_3 = Article(number="3", path=[chapter])
    article_4 = Article(number="4", path=[chapter])

    assert article_3.path[0] is article_4.path[0]

    with pytest.raises(ValidationError):
        article_3.path[0].title = "ΤΥΠΟΓΡΑΦΙΚΟ ΛΑΘΟΣ"  # type: ignore[misc]

    assert article_4.path[0].title == "Γενικές διατάξεις"


def test_structural_units_are_hashable_so_they_can_key_a_tree():
    """Two equal units hash alike and can be used as dict keys.

    Frozen models are hashable with value semantics, which is what lets a
    parser group articles under their chapter without an id scheme. Catches
    `frozen=True` being dropped: the model stays usable everywhere else, and
    only this — grouping — breaks, with a bare TypeError deep in the parser.
    """
    chapter = StructuralUnit(kind="Κεφάλαιο", number="Α΄", title="Γενικές διατάξεις")
    same = StructuralUnit(kind="Κεφάλαιο", number="Α΄", title="Γενικές διατάξεις")

    assert {chapter: ["3", "4"]}[same] == ["3", "4"]
