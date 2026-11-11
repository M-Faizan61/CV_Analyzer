"""Small text helpers shared by the other services."""
import re
from functools import lru_cache

# Words that say nothing about what a requirement is really about.
_FILLER_WORDS = frozenset("""
    a an and or the of in on at to for with by from as is are be been will should must
    have has having had can you your we our who that this these those it its their they
    required require requires requirement requirements mandatory essential need needs needed
    necessary preferred preferably prefer desirable nice good plus bonus minimum least
    year years yr yrs experience experienced knowledge skill skills ability able strong
    solid excellent great proven working work understanding familiarity familiar background
    expertise hands relevant professional candidate candidates applicant applicants very
    well also etc including such like similar related field more than over role position
    job industry company team demonstrated total overall
""".split())


def normalize(text: str) -> str:
    """Ignore case and spacing when comparing text."""
    return " ".join(text.split()).casefold()


def is_verbatim(quote: str, text: str) -> bool:
    """True when a quote really appears in the text (used to check AI answers)."""
    cleaned = normalize(quote)
    return bool(cleaned) and cleaned in normalize(text)


@lru_cache(maxsize=None)
def _term_pattern(term: str) -> re.Pattern:
    # Lookarounds instead of \b so that "c++" and ".net" work. A space in the term
    # may be any whitespace because PDF text wraps. "no-" stops "no-sql" counting as SQL.
    body = re.escape(term).replace(r"\ ", r"\s+")
    return re.compile(r"(?<![\w])(?<!no-)" + body + r"(?![\w])", re.I)


def contains(text: str, term: str) -> bool:
    """Whole-word search: "SQL" is not found inside "MySQL" or "NoSQL"."""
    return bool(_term_pattern(term).search(text))


def remove_term(text: str, term: str) -> str:
    return _term_pattern(term).sub(" ", text)


def split_statements(text: str) -> list[str]:
    """Break text into lines and sentences, without bullets."""
    parts = re.split(r"\n|;|(?<=[.!?])\s+", text)
    cleaned = (part.strip(" \t•*-–—▪●") for part in parts)
    return [part for part in cleaned if part]


def key_terms(text: str) -> list[str]:
    """The meaningful words of a sentence, without filler or numbers."""
    words = (word.strip(".") for word in re.findall(r"[a-z0-9+#.]+", text.lower()))
    return [word for word in words if word and word not in _FILLER_WORDS and not re.fullmatch(r"[\d.+]+", word)]


def has_word(statement: str, word: str) -> bool:
    """Like contains(), but also accepts word forms: "plugin" finds "plugins"."""
    if len(word) <= 4:
        return contains(statement, word)
    return bool(re.search(r"(?<![\w])" + re.escape(word[:6]), statement, re.I))
