"""Resolve free-typed stop names to Stop rows.

Ladder: exact → prefix → substring → fuzzy. Anything short of an exact or
single-prefix hit returns candidates for a numbered picker rather than
auto-selecting — a wrong auto-pick sends someone to the wrong side of the city,
and one extra tap is cheap.

difflib rather than pg_trgm: trigram similarity is PostgreSQL-only, and this
project targets MySQL with SQLite in dev. Over ~120 strings the stdlib matcher
is faster than the round trip anyway, and it unit-tests without a database.
"""

import difflib
from dataclasses import dataclass, field
from enum import Enum

from bot.models import Stop, StopAlias
from bot.utils.text import normalize

FUZZY_CUTOFF = 0.72
MAX_CANDIDATES = 8


class MatchKind(Enum):
    NONE = "none"
    EXACT = "exact"
    CANDIDATES = "candidates"


@dataclass
class MatchResult:
    kind: MatchKind
    stop: Stop | None = None
    candidates: list[Stop] = field(default_factory=list)

    @property
    def resolved(self) -> bool:
        return self.kind is MatchKind.EXACT


def _alias_map() -> dict[str, int]:
    """norm string -> stop_id, covering both canonical names and aliases."""
    mapping = {
        norm: pk
        for norm, pk in Stop.objects.filter(is_active=True).values_list("norm_name", "pk")
        if norm
    }
    for norm, pk in StopAlias.objects.values_list("norm_alias", "stop_id"):
        if norm:
            mapping.setdefault(norm, pk)
    return mapping


def resolve(text: str) -> MatchResult:
    """Resolve user text to a stop."""
    needle = normalize(text)
    if not needle:
        return MatchResult(MatchKind.NONE)

    lookup = _alias_map()

    # 1. Exact on canonical name or alias.
    if needle in lookup:
        stop = Stop.objects.filter(pk=lookup[needle]).first()
        if stop:
            return MatchResult(MatchKind.EXACT, stop=stop)

    # 2. Prefix, then substring, over the same normalized keys.
    prefix_ids = [pk for norm, pk in lookup.items() if norm.startswith(needle)]
    if len(prefix_ids) == 1:
        stop = Stop.objects.filter(pk=prefix_ids[0]).first()
        if stop:
            return MatchResult(MatchKind.EXACT, stop=stop)

    substring_ids = [pk for norm, pk in lookup.items() if needle in norm]
    hit_ids = prefix_ids or substring_ids
    if hit_ids:
        stops = _stops_in_order(hit_ids)
        if len(stops) == 1:
            return MatchResult(MatchKind.EXACT, stop=stops[0])
        return MatchResult(MatchKind.CANDIDATES, candidates=stops[:MAX_CANDIDATES])

    # 3. Fuzzy — never auto-resolves.
    close = difflib.get_close_matches(needle, list(lookup.keys()), n=5, cutoff=FUZZY_CUTOFF)
    if close:
        stops = _stops_in_order([lookup[c] for c in close])
        return MatchResult(MatchKind.CANDIDATES, candidates=stops)

    return MatchResult(MatchKind.NONE)


def _stops_in_order(ids: list[int]) -> list[Stop]:
    """Fetch stops, de-duplicated, preserving the order the ids were scored in."""
    seen, ordered = set(), []
    for pk in ids:
        if pk not in seen:
            seen.add(pk)
            ordered.append(pk)
    by_id = Stop.objects.in_bulk(ordered)
    return [by_id[pk] for pk in ordered if pk in by_id]
