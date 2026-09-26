import re


_CLASS_SUFFIX = re.compile(r"(?:\s*,\s*\d{1,2})+\s*$")
_WHITESPACE = re.compile(r"\s+")


def canonical_olympiad_name(name: str) -> str:
    """Remove source-added grade lists while keeping the source's display spelling."""
    return _WHITESPACE.sub(" ", _CLASS_SUFFIX.sub("", name).strip(" ,\t\n"))


def olympiad_name_key(name: str) -> str:
    """Normalize typography and source-added grades for matching olympiad names."""
    name = canonical_olympiad_name(name).casefold()
    name = name.translate(str.maketrans({"—": "-", "–": "-", "−": "-", "/": " "}))
    name = name.translate(str.maketrans("", "", "«»„“”’‘"))
    return _WHITESPACE.sub(" ", name).strip()


def has_grade_suffix(name: str) -> bool:
    return _CLASS_SUFFIX.search(name) is not None
