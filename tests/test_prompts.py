import hashlib

from greek_law.application import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    Question,
    build_messages,
)

# sha256 of SYSTEM_PROMPT as it stood when PROMPT_VERSION was set to "v1".
_PROMPT_FINGERPRINTS = {
    "v1": "ed699e074c14c15b69fa7460d55b5ca001ee01c22c7ddeb3935c49bf6ad8ae91",
}


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
