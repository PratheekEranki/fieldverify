"""Text normalization used before any comparison. Pure functions, no I/O."""
import re
import unicodedata

NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "md", "do", "phd", "rn", "np", "pa", "dds", "dpm"}

STREET_ABBREVIATIONS = {
    "st": "street", "str": "street", "ave": "avenue", "av": "avenue", "rd": "road", "dr": "drive",
    "blvd": "boulevard", "ln": "lane", "ct": "court", "pl": "place", "pkwy": "parkway", "hwy": "highway",
    "cir": "circle", "ter": "terrace", "trl": "trail", "sq": "square",
    "north": "n", "south": "s", "east": "e", "west": "w",
}
# Unit designators: the designator and the token after it are dropped (unit numbers aren't compared).
UNIT_WORDS = {"apt", "apartment", "ste", "suite", "unit", "#", "rm", "room", "fl", "floor", "bldg"}


def _ascii_fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def normalize_text(text: str | None) -> str:
    """Lowercase, strip accents, turn hyphens into spaces, drop other punctuation, collapse whitespace."""
    if not text:
        return ""
    text = _ascii_fold(text).lower().replace("-", " ")
    text = re.sub(r"[^a-z0-9#\s]", "", text)
    return " ".join(text.split())


def normalize_name(name: str | None) -> str:
    tokens = [t for t in normalize_text(name).split() if t not in NAME_SUFFIXES]
    return " ".join(tokens)


def normalize_street(street: str | None) -> str:
    tokens = normalize_text(street).replace("#", " # ").split()
    out: list[str] = []
    skip_next = False
    for tok in tokens:
        if skip_next:
            skip_next = False
            continue
        if tok in UNIT_WORDS:
            skip_next = True
            continue
        out.append(STREET_ABBREVIATIONS.get(tok, tok))
    return " ".join(out)


def house_number(street: str | None) -> str | None:
    match = re.match(r"\s*(\d+)", street or "")
    return match.group(1) if match else None


def digits_only(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")
