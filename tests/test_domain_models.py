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
    paragraph = Paragraph(text="Για την εφαρμογή του παρόντος νόμου...")

    assert paragraph.number is None


def test_cases_nest_recursively():
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
    with pytest.raises(ValidationError) as exc_info:
        Article(number="4", titel="Ορισμοί")

    assert "titel" in str(exc_info.value)


def test_act_holds_its_identity_separately_from_its_content():
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
    return ActIdentity(act_type="Ν.", number="4808", year=2021)


def test_citation_is_rendered_from_the_structure(act_identity):
    reference = SourceReference(
        act=act_identity, article="4", paragraph="2", cases=["α"]
    )

    assert reference.citation == "Ν. 4808/2021, άρθρο 4 παρ. 2 περ. α΄"


def test_citation_of_unnumbered_article_text_omits_the_paragraph(act_identity):
    reference = SourceReference(act=act_identity, article="4")

    assert reference.citation == "Ν. 4808/2021, άρθρο 4"


def test_subcase_citation_names_its_level(act_identity):
    reference = SourceReference(
        act=act_identity, article="4", paragraph="2", cases=["α", "αα"]
    )

    assert reference.citation.endswith("περ. α΄ υποπερ. αα΄")


def test_retrieval_key_stays_in_the_greek_alphabet(act_identity):
    reference = SourceReference(
        act=act_identity, article="3Α", paragraph="2", cases=["α"]
    )

    assert reference.key == "Ν.4808/2021/άρθρο-3Α/παρ-2/περ-α"


def test_key_is_derived_and_cannot_be_set(act_identity):
    with pytest.raises(ValidationError):
        SourceReference(act=act_identity, article="4", key="anything")


def test_models_are_read_only():
    article = Article(number="4", title="Ορισμοί")

    with pytest.raises(ValidationError) as exc_info:
        article.title = "Κάτι άλλο"

    assert "frozen" in str(exc_info.value)


def test_a_shared_container_cannot_be_edited_through_one_article():
    """A parser hands the same StructuralUnit to every article in a chapter.

    Without frozen=True, editing it through one article silently rewrites the
    breadcrumb of every other article in that chapter.
    """
    chapter = StructuralUnit(kind="Κεφάλαιο", number="Α΄", title="Γενικές διατάξεις")
    article_3 = Article(number="3", path=[chapter])
    article_4 = Article(number="4", path=[chapter])

    assert article_3.path[0] is article_4.path[0]

    with pytest.raises(ValidationError):
        article_3.path[0].title = "ΤΥΠΟΓΡΑΦΙΚΟ ΛΑΘΟΣ"

    assert article_4.path[0].title == "Γενικές διατάξεις"


def test_structural_units_are_hashable_so_they_can_key_a_tree():
    chapter = StructuralUnit(kind="Κεφάλαιο", number="Α΄", title="Γενικές διατάξεις")
    same = StructuralUnit(kind="Κεφάλαιο", number="Α΄", title="Γενικές διατάξεις")

    assert {chapter: ["3", "4"]}[same] == ["3", "4"]
