"""PNR generation.

Requirements this alphabet satisfies: readable aloud to a conductor on a noisy
bus, typeable on a phone keypad, and unguessable. Sequential ids would let
anyone text IB000123 and read a stranger's ticket, so this uses `secrets`.
"""

import secrets

# 30 characters. Dropped: 0/O, 1/I/L (visually ambiguous), U (sounds like V).
ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"
PREFIX = "IB"
LENGTH = 6


class PNRGenerationError(RuntimeError):
    pass


def generate_pnr(attempts: int = 5) -> str:
    """Return an unused PNR such as ``IB7K4Q2M``.

    30**6 ≈ 729 million values, so collisions are vanishingly rare; the
    ``exists()`` probe is an optimisation and the unique index on
    ``Booking.pnr`` is the actual guarantee — callers retry on IntegrityError.
    """
    from bot.models import Booking

    for _ in range(attempts):
        pnr = PREFIX + "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))
        if not Booking.objects.filter(pnr=pnr).exists():
            return pnr
    raise PNRGenerationError("Could not allocate a unique PNR")


def looks_like_pnr(text: str) -> bool:
    candidate = (text or "").strip().upper().replace(" ", "")
    if len(candidate) != len(PREFIX) + LENGTH:
        return False
    if not candidate.startswith(PREFIX):
        return False
    return all(ch in ALPHABET for ch in candidate[len(PREFIX):])
