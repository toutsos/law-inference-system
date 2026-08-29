import pytest
from pydantic import ValidationError

from greek_law.domain.article import Article


def test_article_keeps_the_values_it_was_given():
    article = Article(number="4", title="Ορισμοί")

    assert article.number == "4"
    assert article.title == "Ορισμοί"


def test_title_is_optional_and_defaults_to_none():
    article = Article(number="4")

    assert article.title is None


def test_number_is_required():
    with pytest.raises(ValidationError) as exc_info:
        Article(title="Ορισμοί")

    assert "number" in str(exc_info.value)
    assert "Field required" in str(exc_info.value)


def test_number_is_not_silently_coerced_from_an_int():
    with pytest.raises(ValidationError) as exc_info:
        Article(number=4)

    assert "string_type" in str(exc_info.value)


def test_greek_article_number_is_preserved_and_differs_from_its_latin_lookalike():
    greek = Article(number="3Α")  # Α is U+0391, Greek capital alpha
    latin = Article(number="3A")  # A is U+0041, Latin capital A

    assert greek.number == "3Α"
    assert greek.number != latin.number
