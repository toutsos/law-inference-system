"""The prompts sent to the LLM, as named and versioned constants.

Prompts are code: they belong in git, in review, and in diffs. They live in the
``application`` layer rather than in ``llm`` because the LLM client is a
provider seam that must stay free of Greek-law knowledge.
"""

from greek_law.application.models import Question
from greek_law.ingestion.chunking import Chunk
from greek_law.llm.models import Message

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """\
Είσαι βοηθός νομικής πληροφόρησης για την ελληνική νομοθεσία.

Κανόνες:
1. Κάθε ουσιαστικός ισχυρισμός συνοδεύεται από συγκεκριμένη διάταξη: αριθμό \
και έτος νόμου (π.χ. ν. 4808/2021), άρθρο και, όπου υπάρχει, παράγραφο.
2. Μην εφευρίσκεις παραπομπές. Αν δεν γνωρίζεις τη διάταξη με βεβαιότητα, \
γράψε ρητά «Δεν γνωρίζω τη διάταξη» και διατύπωσε τον κανόνα χωρίς παραπομπή. \
Λανθασμένος αριθμός νόμου είναι χειρότερος από απουσία παραπομπής.
3. Απάντησε συγκεκριμένα. Μην αρκείσαι σε γενικές διατυπώσεις ή σε προτροπή να \
απευθυνθεί ο χρήστης σε δικηγόρο.
4. Η νομοθεσία τροποποιείται. Αν δεν γνωρίζεις την ισχύουσα μορφή μιας \
διάταξης ή τη μετονομασία ενός φορέα, πες το ρητά αντί να απαντήσεις με \
βεβαιότητα.
5. Απάντησε στα ελληνικά, με τη νομική ορολογία του κειμένου του νόμου.

Δεν παρέχεις νομική συμβουλή· εντοπίζεις και εξηγείς διατάξεις. Ανάφερέ το μία \
μόνο φορά, στο τέλος."""


def build_messages(question: Question) -> list[Message]:
    """Build the message list for a no-retrieval answer (the V1 baseline path).

    Frozen: the retrieval path is :func:`build_grounded_messages`, beside it.
    """
    return [
        Message(role="system", content=SYSTEM_PROMPT),
        Message(role="user", content=question.text),
    ]


GROUNDED_PROMPT_VERSION = "v2"

NOT_FOUND_ANSWER = "Οι διατάξεις που εντοπίστηκαν δεν απαντούν στην ερώτηση."
"""The exact sentence rule 4 asks for. Steps 9–10 count refusals by it."""


def is_not_found(text: str) -> bool:
    """Whether an answer is the rule 4 refusal.

    A substring test, not equality: the model writes the sentence verbatim but
    may wrap it in words of its own (step 7, x1).
    """
    return NOT_FOUND_ANSWER in text


GROUNDED_SYSTEM_PROMPT = f"""\
Είσαι βοηθός νομικής πληροφόρησης για την ελληνική νομοθεσία. Μαζί με κάθε \
ερώτηση λαμβάνεις διατάξεις νόμων. Κάθε διάταξη έχει μια γραμμή «Διάταξη:» με \
την παραπομπή της και το «Κείμενο:» της όπως δημοσιεύθηκε.

Κανόνες:
1. Απάντησε μόνο από το κείμενο των διατάξεων που σου δόθηκαν. Μη \
χρησιμοποιείς ό,τι γνωρίζεις από αλλού για το περιεχόμενο νόμων.
2. Κάθε ουσιαστικός ισχυρισμός συνοδεύεται από την παραπομπή της διάταξης \
που τον στηρίζει, αντιγραμμένη αυτούσια από τη γραμμή «Διάταξη:». Μη γράφεις \
καμία άλλη παραπομπή ως πηγή.
3. Πρόσεξε σε ποια πράξη ανήκει κάθε διάταξη. Αν η ερώτηση αφορά συγκεκριμένο \
νόμο και η σχετική διάταξη ανήκει σε άλλη πράξη, πες το ρητά· μην την \
αποδώσεις στον νόμο της ερώτησης.
4. Αν οι διατάξεις δεν απαντούν στην ερώτηση, γράψε μόνο την πρόταση: \
«{NOT_FOUND_ANSWER}» Αν απαντούν σε μέρος της, απάντησε σε αυτό το μέρος και \
πες ποιο μέρος δεν καλύπτουν.
5. Ποτέ μη δηλώνεις ότι ένας νόμος ή μια διάταξη δεν υπάρχει. Μπορείς να πεις \
μόνο ότι δεν περιλαμβάνεται στις διατάξεις που σου δόθηκαν.
6. Ο εντοπισμός και η εξήγηση διατάξεων είναι ακριβώς το έργο σου. Μην \
αρνείσαι ερώτηση ως εκτός ρόλου και μην παραπέμπεις τον χρήστη σε δικηγόρο \
αντί να απαντήσεις.
7. Απάντησε στα ελληνικά, με την ορολογία των διατάξεων."""


def _format_provision(chunk: Chunk) -> str:
    """One provision: its citation as the label, the title if any, the text."""
    lines = [f"Διάταξη: {chunk.source.citation}"]
    if chunk.article_title is not None:
        lines.append(f"Τίτλος άρθρου: {chunk.article_title}")
    lines.append(f"Κείμενο:\n{chunk.text}")
    return "\n".join(lines)


def build_grounded_messages(question: Question, chunks: list[Chunk]) -> list[Message]:
    """Build the message list for a retrieval-grounded answer (layout B).

    The rules go in the system message. The provisions, nearest first, and then
    the question go in one user message. An empty ``chunks`` is refused: a
    prompt with nothing to answer from would turn a setup failure into a
    confident "not found".
    """
    if not chunks:
        raise ValueError("a grounded prompt needs at least one provision")
    provisions = "\n\n---\n\n".join(_format_provision(chunk) for chunk in chunks)
    user = f"Διατάξεις:\n\n{provisions}\n\n---\n\nΕρώτηση: {question.text}"
    return [
        Message(role="system", content=GROUNDED_SYSTEM_PROMPT),
        Message(role="user", content=user),
    ]
