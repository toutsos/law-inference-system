import hashlib

import pytest

from greek_law.application import (
    GROUNDED_PROMPT_VERSION,
    GROUNDED_SYSTEM_PROMPT,
    NOT_FOUND_ANSWER,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    Question,
    build_grounded_messages,
    build_messages,
    is_not_found,
)
from greek_law.domain import ActIdentity, SourceReference
from greek_law.ingestion.chunking import Chunk

# sha256 of each system prompt as it stood when its version was set.
# "v1" is SYSTEM_PROMPT (no retrieval), "v2" is GROUNDED_SYSTEM_PROMPT.
_PROMPT_FINGERPRINTS = {
    "v1": "ed699e074c14c15b69fa7460d55b5ca001ee01c22c7ddeb3935c49bf6ad8ae91",
    "v2": "22abc8c469c00d5985ccf5256290077d51f33a3ad17062a2680be4c19dd09419",
}

_N5110 = ActIdentity(act_type="ν.", number="5110", year=2024)
_PD62 = ActIdentity(act_type="π.δ.", number="62", year=2025)


def _chunk(
    act: ActIdentity, article: str, paragraph: str | None, title: str | None
) -> Chunk:
    return Chunk(
        document_id="test_doc",
        source=SourceReference(act=act, article=article, paragraph=paragraph),
        article_title=title,
        text=f"Κείμενο του άρθρου {article}.",
    )


_OWNER = _chunk(_N5110, "11", "1", "Πνευματική ιδιοκτησία")
_CARD = _chunk(_PD62, "580", "1", "Ψηφιακή κάρτα εργασίας")


def test_the_system_prompt_comes_first_and_the_question_second() -> None:
    """A no-retrieval call is exactly two messages: system, then user.

    Order and roles are the whole contract with the chat API. Catches the two
    slips that produce a *plausible but wrong* answer rather than an error: the
    question sent under role "system" (the model then treats the user's words as
    its own standing instructions), and the system prompt appended after the
    question, where instruction-tuned models weight it as part of the user's
    text. Both return fluent Greek, so nothing downstream would notice.
    """
    messages = build_messages(Question(text="Τι ισχύει για την καταγγελία;"))

    assert [m.role for m in messages] == ["system", "user"]
    assert messages[0].content == SYSTEM_PROMPT
    assert messages[1].content == "Τι ισχύει για την καταγγελία;"


def test_the_question_text_is_sent_verbatim() -> None:
    """The user's words reach the model unwrapped and unedited.

    Catches a future "helpful" edit to build_messages — prefixing "Ερώτηση:",
    appending "Απάντησε σύντομα", or reformatting the text. Each silently
    changes what was asked, which makes the step 10 baseline answers evidence
    for a question nobody recorded, and makes V7's eval scores incomparable
    across runs.
    """
    text = "  Ποια είναι η προθεσμία;  "

    messages = build_messages(Question(text=text))

    assert messages[1].content == "Ποια είναι η προθεσμία;"


def test_editing_the_system_prompt_requires_bumping_the_prompt_version() -> None:
    """SYSTEM_PROMPT's text is pinned to the PROMPT_VERSION it was written for.

    Answer.metadata records prompt_version, and step 10 saves baseline answers
    labelled with it. Editing the prompt without bumping the version does not
    break anything at runtime — it silently relabels: two answers produced by
    two different prompts are both stamped "v1", so V7's regression comparison
    attributes a prompt change to a retrieval change. This test is the only
    thing that can notice, because the mislabelling is invisible in the output.
    """
    fingerprint = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()

    assert _PROMPT_FINGERPRINTS[PROMPT_VERSION] == fingerprint


def test_editing_the_grounded_prompt_requires_bumping_its_version() -> None:
    """GROUNDED_SYSTEM_PROMPT's text is pinned to GROUNDED_PROMPT_VERSION.

    The same relabelling risk as the v1 test, now for the prompt step 9 will
    compare against V1: an edit made while tuning it, left at "v2", would let
    two different prompts' answers sit side by side under one label in the
    results files.
    """
    fingerprint = hashlib.sha256(GROUNDED_SYSTEM_PROMPT.encode("utf-8")).hexdigest()

    assert _PROMPT_FINGERPRINTS[GROUNDED_PROMPT_VERSION] == fingerprint


def test_the_two_prompts_carry_different_versions() -> None:
    """The grounded prompt never shares a version label with the baseline's.

    Answer.metadata.prompt_version is the only field that says which prompt
    produced an answer. Catches GROUNDED_PROMPT_VERSION copy-pasted as "v1":
    step 9's RAG answers would be stamped like V1's no-retrieval answers.
    """
    assert GROUNDED_PROMPT_VERSION != PROMPT_VERSION


def test_the_system_prompt_quotes_the_not_found_sentence_exactly() -> None:
    """The refusal sentence the model is told to write is NOT_FOUND_ANSWER.

    Steps 9–10 count refusals by matching NOT_FOUND_ANSWER. Catches the two
    drifting apart — the constant reworded while the prompt still asks for the
    old wording, or the reverse — after which every refusal would be counted
    as an answer and the q10 canary could not fire.
    """
    assert f"«{NOT_FOUND_ANSWER}»" in GROUNDED_SYSTEM_PROMPT


def test_a_grounded_call_is_system_rules_then_one_user_message() -> None:
    """Two messages: the fixed rules as system, provisions and question as user.

    Layout B. Catches the provisions leaking into the system message (layout A,
    rejected) or a third message appearing — either changes what step 9
    measures without changing GROUNDED_PROMPT_VERSION, because the fingerprint
    only pins the system text.
    """
    messages = build_grounded_messages(Question(text="Ποιος;"), [_OWNER])

    assert [m.role for m in messages] == ["system", "user"]
    assert messages[0].content == GROUNDED_SYSTEM_PROMPT


def test_each_provision_is_labelled_with_its_exact_citation() -> None:
    """Every chunk appears under «Διάταξη: <citation>», then its text verbatim.

    The model is told to copy the label as its source, and step 8 will check
    cited labels against the retrieved chunks' citations. Catches the label
    built from something else (the key, a number, the header with its title
    glued on): the model's citations would then match nothing step 8 can
    resolve. Also catches the law's text being edited on the way in.
    """
    messages = build_grounded_messages(Question(text="Ποιος;"), [_OWNER, _CARD])

    user = messages[1].content
    assert "Διάταξη: ν. 5110/2024, άρθρο 11 παρ. 1\n" in user
    assert "Διάταξη: π.δ. 62/2025, άρθρο 580 παρ. 1\n" in user
    assert "Κείμενο:\nΚείμενο του άρθρου 11." in user
    assert "Κείμενο:\nΚείμενο του άρθρου 580." in user


def test_provisions_keep_retrieval_order_and_the_question_comes_last() -> None:
    """Provisions in the order given (nearest first), then the question.

    Catches a sort or set() reordering the chunks, which would make an answer
    unexplainable from the retrieval sheet, and the question being placed
    before the provisions, where a small model weights it less than the
    thousands of tokens of law that follow.
    """
    messages = build_grounded_messages(Question(text="  Ποιος;  "), [_CARD, _OWNER])

    user = messages[1].content
    assert user.index("άρθρο 580") < user.index("άρθρο 11")
    assert user.endswith("Ερώτηση: Ποιος;")


def test_a_chunk_without_an_article_title_gets_no_title_line() -> None:
    """No «Τίτλος άρθρου:» line when the article has no title.

    Catches an f-string rendering None as the literal text "None" — which the
    model would read as an article titled «None» and might quote.
    """
    untitled = _chunk(_N5110, "3", None, None)

    messages = build_grounded_messages(Question(text="Ποιος;"), [untitled])

    user = messages[1].content
    assert "Τίτλος άρθρου" not in user
    assert "None" not in user


def test_a_titled_chunk_carries_its_article_title() -> None:
    """The article's title appears on its own line under the citation.

    Short paragraphs often name their subject only in the title (step 6:
    «Ψηφιακή κάρτα εργασίας»). Catches the title being dropped, which leaves
    the model a paragraph with no subject — the reason V2 put it in the header.
    """
    messages = build_grounded_messages(Question(text="Ποιος;"), [_CARD])

    assert "Τίτλος άρθρου: Ψηφιακή κάρτα εργασίας\n" in messages[1].content


def test_no_provisions_is_an_error_not_a_prompt() -> None:
    """An empty chunk list raises instead of building a provision-less prompt.

    With nothing to answer from, rule 4 makes the model write NOT_FOUND_ANSWER
    for every question — a setup failure reported as a legal finding. The
    retriever already refuses to return [] (NoEmbeddingsError); this is the
    same rule at the next layer, so a future retriever cannot reintroduce it.
    """
    with pytest.raises(ValueError):
        build_grounded_messages(Question(text="Ποιος;"), [])


def test_a_refusal_wrapped_in_the_models_own_words_is_detected() -> None:
    """is_not_found finds NOT_FOUND_ANSWER anywhere in the text.

    Step 7's x1 answer wrote the sentence verbatim but after a sentence of its
    own. Catches an equality check: that refusal would be read as an answer,
    the CLI would list five irrelevant provisions under it as its "sources",
    and step 9 would undercount refusals.
    """
    text = f"Η ερώτηση αφορά την κλοπή αυτοκινήτου. {NOT_FOUND_ANSWER}"

    assert is_not_found(text)


def test_an_answer_that_cites_provisions_is_not_a_refusal() -> None:
    """A normal grounded answer is not classified as "not found".

    Catches a check loose enough to match on fragments such as «διατάξεις»,
    which nearly every answer contains: every answer would lose its sources.
    """
    text = "Δικαιούχος είναι ο ανάδοχος (ν. 5110/2024, άρθρο 11 παρ. 1)."

    assert not is_not_found(text)
