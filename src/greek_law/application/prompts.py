"""The prompts sent to the LLM, as named and versioned constants.

Prompts are code: they belong in git, in review, and in diffs. They live in the
``application`` layer rather than in ``llm`` because the LLM client is a
provider seam that must stay free of Greek-law knowledge.
"""

from greek_law.application.models import Question
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

    V3 inserts the retrieved provisions between the system prompt and the
    question; the signature is the seam where that happens.
    """
    return [
        Message(role="system", content=SYSTEM_PROMPT),
        Message(role="user", content=question.text),
    ]
