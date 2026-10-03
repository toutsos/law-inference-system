import pytest
from pydantic import ValidationError

from greek_law.domain import (
    Act,
    ActIdentity,
    Article,
    Case,
    Paragraph,
    RatifiedInstrument,
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


def test_a_multi_word_article_number_produces_a_key_with_no_whitespace():
    """Spelled-out article numbers slug into the key instead of keeping spaces.

    Not hypothetical: ν. 5110/2024 ratifies a καταστατικό whose articles are
    written out — «Άρθρο δέκατο πέμπτο» — so the V3 corpus produces these on the
    first ingest. `key` is documented as a flat identifier for the vector store,
    and a whitespace-bearing id is the kind of thing a store accepts on write
    and mangles on read: URL-encoded in one code path, split on whitespace in
    another, so the provision is indexed under one id and looked up under
    another. Retrieval then returns nothing for exactly the articles a citation
    question is most likely to ask about.

    Written before `instrument` existed, with no instrument set — which built a
    reference V2 step 5b established is *wrong*, since ν. 5110/2024 has no
    «άρθρο δέκατο πέμπτο» of its own. The instrument is supplied now so the
    fixture is a provision that exists; the whitespace assertion is what the
    test is for and is unchanged.
    """
    reference = SourceReference(
        act=ActIdentity(act_type="ν.", number="5110", year=2024),
        instrument=KATASTATIKO,
        article="δέκατο πέμπτο",
        paragraph="1",
    )

    assert reference.key == "ν.5110/2024/άρθρο-13/άρθρο-δέκατο-πέμπτο/παρ-1"
    assert " " not in reference.key


KATASTATIKO = RatifiedInstrument(cited_as="του καταστατικού", ratifying_article="13")
"""The καταστατικό of the ΕΛΚΑΚ, ratified by άρθρο 13 of ν. 5110/2024.

Real: PDF page 10 of ΦΕΚ Α' 75/2024 reads «Κυρώνεται το αρχικό καταστατικό του
Ελληνικού Κέντρου Αμυντικής Καινοτομίας, το οποίο έχει ως εξής:» followed by
thirty articles numbered «πρώτο» to «τριακοστό».
"""

ELKAK = ActIdentity(act_type="ν.", number="5110", year=2024)


def test_a_ratified_instruments_article_is_not_cited_as_the_acts_own():
    """«άρθρο δέκατο πέμπτο» cites the καταστατικό, naming the article that enacted it.

    The bug this field exists to remove. ν. 5110/2024 has articles 1–82 in
    digits and no «άρθρο δέκατο πέμπτο» at all, so the old rendering —
    «ν. 5110/2024, άρθρο δέκατο πέμπτο» — pointed at an address that does not
    exist. Either the reader fails to find it and the answer is unverifiable,
    or they read it as «άρθρο 15» and land on *Εκπαίδευση - Κέντρα Αριστείας*,
    a provision about centres of excellence, instead of the composition of a
    board of directors. Well-formed and wrong, which is this version's
    recurring failure shape.
    """
    reference = SourceReference(
        act=ELKAK, instrument=KATASTATIKO, article="δέκατο πέμπτο"
    )

    assert reference.citation == (
        "άρθρο δέκατο πέμπτο του καταστατικού που κυρώθηκε με το άρθρο 13 ν. 5110/2024"
    )


def test_the_ratification_clause_is_rendered_after_the_paragraph():
    """παρ. 1 attaches to the instrument's article, not to the ratifying one.

    The reason a nested citation is rendered act-last. The ratification clause
    ends in an article number — «…με το άρθρο 13» — so anything appended after
    it reads as belonging to *that* article. Act-first would produce «ν.
    5110/2024, άρθρο δέκατο πέμπτο του καταστατικού που κυρώθηκε με το άρθρο 13
    παρ. 1», citing a paragraph of the law's άρθρο 13 — which has no paragraphs
    — rather than of the καταστατικό's άρθρο δέκατο πέμπτο, which has six.
    """
    reference = SourceReference(
        act=ELKAK, instrument=KATASTATIKO, article="δέκατο πέμπτο", paragraph="1"
    )

    assert reference.citation == (
        "άρθρο δέκατο πέμπτο παρ. 1 του καταστατικού "
        "που κυρώθηκε με το άρθρο 13 ν. 5110/2024"
    )


def test_the_key_nests_the_instrument_under_its_ratifying_article():
    """The key path records the nesting; the instrument's name stays out of it.

    Two provisions of one ΦΕΚ must get different store ids, and the path has to
    say which namespace each belongs to or V5 cannot filter the instrument's
    articles from the act's own. The ratifying article carries that, and is
    preferred over `cited_as` because an article number is unique within an act
    and stable, while `cited_as` is prose in a grammatical case — slugging «του
    καταστατικού» into an id would put the Greek genitive article in every key.
    """
    own = SourceReference(act=ELKAK, article="15")
    nested = SourceReference(act=ELKAK, instrument=KATASTATIKO, article="δέκατο πέμπτο")

    assert own.key == "ν.5110/2024/άρθρο-15"
    assert nested.key == "ν.5110/2024/άρθρο-13/άρθρο-δέκατο-πέμπτο"


def test_an_instrument_cannot_be_named_without_the_article_that_ratified_it():
    """Half an address is unconstructible rather than merely invalid.

    The whole argument for a nested type over two optional fields on
    `SourceReference`. With flat fields, `instrument="του καταστατικού"` and no
    ratifying article is a well-typed object that renders a citation missing
    the only clause that makes it resolvable — and nothing would raise. Here
    the two facts live in one object, so the omission is a construction error.
    """
    with pytest.raises(ValidationError):
        RatifiedInstrument(cited_as="του καταστατικού")  # type: ignore[call-arg]


def test_cited_as_carries_its_own_grammatical_case():
    """«της Σύμβασης» keeps its feminine article; the renderer adds no «του».

    π.δ. 62/2025 cites three ratified instruments of different genders — «του
    ΚΝΥ ΑΕ» (masculine), «του καταστατικού» (neuter), «της Σύμβασης της
    Ουάσιγκτον» (feminine) — and Greek case and gender cannot be derived from a
    bare noun. A renderer hard-coding «του» would emit «του Σύμβασης», which is
    not Greek. So the stored form includes the article, and this test is what
    stops a later refactor from "tidying" it into the template.
    """
    convention = RatifiedInstrument(
        cited_as="της Σύμβασης της Ουάσιγκτον", ratifying_article="πρώτο"
    )
    reference = SourceReference(
        act=ActIdentity(act_type="ν.", number="2269", year=1920),
        instrument=convention,
        article="3",
    )

    assert reference.citation == (
        "άρθρο 3 της Σύμβασης της Ουάσιγκτον "
        "που κυρώθηκε με το άρθρο πρώτο ν. 2269/1920"
    )


def test_an_act_without_an_instrument_cites_exactly_as_before():
    """The act-first form is untouched when `instrument` is None.

    `instrument` is optional and almost every reference will leave it unset, so
    the regression that matters most is the one where nothing changed. A
    renderer refactored around the nested branch could easily move the comma or
    the act to the end for every citation in the system.
    """
    reference = SourceReference(
        act=ActIdentity(act_type="Ν.", number="4808", year=2021),
        article="4",
        paragraph="2",
        cases=["α"],
    )

    assert reference.citation == "Ν. 4808/2021, άρθρο 4 παρ. 2 περ. α΄"


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
