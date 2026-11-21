"""Possible-duplicate detection (design §5.5, R-DUP, D2).

Flags only. Records are never merged and values are never changed (R-ID-6).
"""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Iterable

from .merge import Record
from .schema import DUP_DURATION_TOL, DUP_TEMPO_TOL, FIELDS, Issue, Reason

RECORD_FIELD = "record"  # Issue.field for record-level findings


def rel_diff(a: float, b: float) -> float:
    top = max(abs(a), abs(b))
    return 0.0 if top == 0 else abs(a - b) / top


def is_possible_duplicate(a: Record, b: Record) -> bool:
    ta, tb = a.values["tempo"], b.values["tempo"]
    da, db = a.values["duration_ms"], b.values["duration_ms"]
    if None in (ta, tb, da, db):
        return False
    return rel_diff(ta, tb) <= DUP_TEMPO_TOL and rel_diff(da, db) <= DUP_DURATION_TOL


def find_possible_duplicates(records: Iterable[Record]) -> list[Issue]:
    """Link look-alike records both ways. Returns issues sorted by (id, other_id)."""
    groups: dict[str, list[Record]] = defaultdict(list)
    for r in records:
        title = r.values["title"]
        if title is not None:
            groups[title.casefold()].append(r)

    issues: list[Issue] = []
    for group in groups.values():
        for a, b in combinations(sorted(group, key=lambda r: r.id), 2):
            if not is_possible_duplicate(a, b):
                continue
            a.possible_duplicates.append(b.id)
            b.possible_duplicates.append(a.id)
            issues.append(_issue(a, b))
            issues.append(_issue(b, a))

    for group in groups.values():
        for r in group:
            r.possible_duplicates.sort()
    return sorted(issues, key=lambda i: (i.id, i.detail["other_id"]))


def _issue(me: Record, other: Record) -> Issue:
    diffs = {
        f.name: [me.values[f.name], other.values[f.name]]
        for f in FIELDS
        if me.values[f.name] != other.values[f.name]
    }
    detail = {
        "other_id": other.id,
        "tempo_diff_pct": round(100 * rel_diff(me.values["tempo"], other.values["tempo"]), 3),
        "duration_diff_pct": round(
            100 * rel_diff(me.values["duration_ms"], other.values["duration_ms"]), 3),
        "field_diffs": diffs,
    }
    return Issue(id=me.id, field=RECORD_FIELD, source=None, raw_value=None,
                 final_value=None, reason=Reason.POSSIBLE_DUPLICATE, detail=detail)
