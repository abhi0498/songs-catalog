"""Merge cleaned source rows by id (design §5.4, R-ID, D1).

No file is preferred over another: when sources disagree, the field becomes
null with source_conflict. Because no source "wins", the order the inputs
come in cannot change the result (P5).
"""
from __future__ import annotations

import dataclasses
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable

from .load import row_key
from .schema import ABSENT, FIELDS, Cleaned, Issue, Reason, Source, SourceRow


@dataclass
class Record:
    id: str
    sources: list[Source]
    values: dict[str, Any]                  # every field, in schema order
    field_flags: dict[str, list[Reason]]    # reasons explaining each field's final state
    possible_duplicates: list[str] = field(default_factory=list)


@dataclass
class MergeResult:
    records: list[Record]   # sorted by id
    issues: list[Issue]     # every issue, for the log


def source_key(s: Source) -> tuple:
    return (s.file, row_key(s.row))


def merge_by_id(rows: Iterable[SourceRow]) -> MergeResult:
    groups: dict[str, list[SourceRow]] = defaultdict(list)
    for r in rows:
        groups[r.id].append(r)

    records: list[Record] = []
    issues: list[Issue] = []
    for id_ in sorted(groups):
        group = sorted(groups[id_], key=lambda r: source_key(r.source))
        values: dict[str, Any] = {}
        flags: dict[str, list[Reason]] = {}
        for spec in FIELDS:
            value, field_flags, field_issues = _resolve(id_, spec.name, group)
            values[spec.name] = value
            if field_flags:
                flags[spec.name] = sorted(set(field_flags))
            issues.extend(field_issues)
        records.append(Record(id=id_, sources=[r.source for r in group],
                              values=values, field_flags=flags))
    return MergeResult(records=records, issues=issues)


def _resolve(id_: str, name: str, group: list[SourceRow]) -> tuple[Any, list[Reason], list[Issue]]:
    """Final value, flags on the record, and log entries for one field of one id."""
    present: list[tuple[Source, Cleaned]] = [(r.source, r.clean[name]) for r in group if name in r.clean]
    lacking = [r.source for r in group if name not in r.clean]
    usable = [(s, c) for s, c in present if c.value is not None]

    distinct: list[Any] = []
    for _, c in usable:
        if c.value not in distinct:
            distinct.append(c.value)

    if len(distinct) == 1:
        value = distinct[0]
        flags = [i.reason for _, c in usable for i in c.issues]
        log = [dataclasses.replace(i, final_value=value) for _, c in present for i in c.issues]
        return value, flags, log  # not_in_source is not logged when a value was found

    log = [dataclasses.replace(i, final_value=None) for _, c in present for i in c.issues]
    log += [Issue(id=id_, field=name, source=s, raw_value=ABSENT, final_value=None,
                  reason=Reason.NOT_IN_SOURCE) for s in lacking]

    if len(distinct) > 1:  # D1: sources disagree → null, nobody wins
        conflict = Issue(
            id=id_, field=name, source=None,
            raw_value=[c.value for _, c in usable], final_value=None,
            reason=Reason.SOURCE_CONFLICT,
            detail={"values": [{"file": s.file, "row": s.row, "value": c.value} for s, c in usable]},
        )
        return None, [Reason.SOURCE_CONFLICT], log + [conflict]

    flags = [i.reason for i in log]
    return None, flags, log
