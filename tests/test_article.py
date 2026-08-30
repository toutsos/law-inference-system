import pytest
from pydantic import ValidationError

from greek_law.domain.article import Article


def test_article_keeps_the_values_it_was_given():
    """The constructor stores number and title unchanged.

    The cheap anchor every other test builds on: if a field is renamed, dropped,
    or a validator starts rewriting input, this fails first and points at the
    model rather than at whatever downstream code noticed the damage.
    """
    article = Article(number="4", title="Ορισμοί")

    assert article.number == "4"
    assert article.title == "Ορισμοί"


def test_title_is_optional_and_defaults_to_none():
    """An article may legitimately have no title.

    Many articles in Greek legislation are untitled. If `title` ever became
    required, ingestion would reject valid corpus documents — and the failure
    would surface as a parser bug rather than as a model decision.
    """
    article = Article(number="4")

    assert article.title is None


def test_number_is_required():
    """An article without a number cannot exist.

    The number is what makes an article citable, and citation is the product
    promise. Catches a default such as `number: str = ""` sneaking in, which
    would let uncitable articles into the store and only fail much later, at
    retrieval time, with no clue where they came from.
    """
    with pytest.raises(ValidationError) as exc_info:
        Article(title="Ορισμοί")  # type: ignore[call-arg]

    assert "number" in str(exc_info.value)
    assert "Field required" in str(exc_info.value)


def test_number_is_not_silently_coerced_from_an_int():
    """Article numbers are strings, and passing an int is an error, not a hint.

    Real numbers include "3Α" and "4α", so the field cannot be an int. Catches
    someone "simplifying" it to `int`, or enabling Pydantic's lax coercion:
    either would destroy "3Α" outright and silently collapse "04" into "4".
    """
    with pytest.raises(ValidationError) as exc_info:
        Article(number=4)  # type: ignore[arg-type]

    assert "string_type" in str(exc_info.value)


def test_greek_article_number_is_preserved_and_differs_from_its_latin_lookalike():
    """Greek Α (U+0391) and Latin A (U+0041) stay distinct.

    They are visually identical, so a normalisation or transliteration step
    added during ingestion could merge "άρθρο 3Α" with a Latin-typed "3A" and
    silently return the wrong provision — a citation error impossible to spot
    by reading the output.
    """
    greek = Article(number="3Α")  # Α is U+0391, Greek capital alpha
    latin = Article(number="3A")  # A is U+0041, Latin capital A

    assert greek.number == "3Α"
    assert greek.number != latin.number
