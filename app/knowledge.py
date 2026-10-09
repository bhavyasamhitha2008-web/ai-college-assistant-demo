import re
from pathlib import Path
from typing import Any


STOP_WORDS = {
    "a",
    "about",
    "am",
    "an",
    "and",
    "are",
    "can",
    "do",
    "does",
    "for",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "please",
    "should",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}
ALIASES = {
    "absence": "attend",
    "absent": "attend",
    "attended": "attend",
    "attending": "attend",
    "attendance": "attend",
    "attend": "attend",
    "class": "class",
    "classes": "class",
    "lecture": "class",
    "lectures": "class",
    "miss": "attend",
    "missed": "attend",
    "exam": "exam",
    "exams": "exam",
    "examination": "exam",
    "examinations": "exam",
    "final": "exam",
    "finals": "exam",
    "test": "exam",
    "tests": "exam",
    "leave": "leave",
    "sick": "leave",
    "ill": "leave",
    "illness": "leave",
}


def _terms(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.casefold())
    return {
        ALIASES.get(word, word)
        for word in words
        if word not in STOP_WORDS and len(word) > 1
    }


def retrieve_passage(
    question: str, documents_dir: str | Path
) -> dict[str, Any]:
    question_terms = _terms(question)
    best_match: tuple[int, Path, str] | None = None

    for path in sorted(Path(documents_dir).glob("*.md")):
        text = path.read_text(encoding="utf-8")
        passages = [
            passage.strip()
            for passage in re.split(r"\n\s*\n", text)
            if passage.strip() and not passage.lstrip().startswith("#")
        ]
        for passage in passages:
            score = len(question_terms & _terms(passage))
            if score and (best_match is None or score > best_match[0]):
                best_match = (score, path, passage)

    if best_match is None:
        return {
            "found": False,
            "answer": "The policy documents do not provide enough information to answer that.",
            "source": None,
        }

    _, path, passage = best_match
    return {"found": True, "answer": passage, "source": path.name}
