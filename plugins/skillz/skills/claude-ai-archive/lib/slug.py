"""Turkish-aware slugifier."""
import re

_REPL = [
    (r"[şŞ]", "s"), (r"[ıİ]", "i"), (r"[ğĞ]", "g"),
    (r"[üÜ]", "u"), (r"[öÖ]", "o"), (r"[çÇ]", "c"),
]


def slugify(s: str, maxlen: int = 80) -> str:
    s = s.strip().lower()
    for pat, rep in _REPL:
        s = re.sub(pat, rep, s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if not s:
        s = "untitled"
    return s[:maxlen].rstrip("-")
