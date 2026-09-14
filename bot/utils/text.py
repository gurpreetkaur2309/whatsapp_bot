"""Text normalization for stop-name matching.

Deliberately free of Django/model imports: both ``bot.models`` (to persist
``norm_name``) and ``bot.services.matching`` (to normalize user input) depend on
this, and they must normalize *identically* or exact-match lookups silently miss.
"""

import re
import unicodedata

# Abbreviations people actually type on a phone. Expanding these turns most
# "fuzzy" cases into deterministic exact matches, which is why this map earns
# its keep over a smarter matcher.
ABBREVIATIONS = {
    "ngr": "nagar",
    "ngar": "nagar",
    "sq": "square",
    "sqr": "square",
    "chowk": "square",
    "chauraha": "square",
    "chrha": "square",
    "rd": "road",
    "stn": "station",
    "jn": "junction",
    "jnc": "junction",
    "hosp": "hospital",
    "clg": "college",
    "mkt": "market",
    "gdn": "garden",
    "nr": "near",
    "bh": "bhawan",
    "bhavan": "bhawan",
    "vihar": "vihar",
    "clny": "colony",
}

# Tokens that carry no discriminating information for a bus stop.
NOISE_TOKENS = {"stop", "bus", "stand", "the", "at", "to", "for", "please", "plz"}

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Fold a stop name or user message into a canonical comparison form.

    ``"  Vijay  Ngr. Sq!"`` and ``"vijay nagar square"`` both become
    ``"vijay nagar square"``.
    """
    if not text:
        return ""

    # Strip accents and any emoji/symbol characters.
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()
    text = _PUNCT_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()

    if not text:
        return ""

    tokens = [ABBREVIATIONS.get(tok, tok) for tok in text.split(" ")]
    tokens = [tok for tok in tokens if tok not in NOISE_TOKENS]

    # If the message was *entirely* noise ("bus stop"), keep the original
    # tokens rather than returning empty — an empty needle matches everything.
    if not tokens:
        tokens = text.split(" ")

    return " ".join(tokens)
