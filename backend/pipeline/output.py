"""Build and write songs.json, issues.json, report.json (design §5.6, R-OUT).

Output is deterministic: fixed key order, fixed sort order, no timestamps (P5).
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .duration import Band
from .load import LoadedFile, row_key
from .merge import Record
from .schema import ABSENT, FIELDS, Issue, Reason, Source

SONGS_FILE, ISSUES_FILE, REPORT_FILE = "songs.json", "issues.json", "report.json"


def _jsonable(v: Any) -> Any:
    if v is ABSENT:
        return None  # the reason code (missing_absent / not_in_source) says it was absent
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    return v


def _source(s: Source | None) -> dict[str, str] | None:
    return None if s is None else {"file": s.file, "row": s.row}


def record_to_dict(rec: Record) -> dict[str, Any]:
    field_flags = {f.name: [str(r) for r in rec.field_flags[f.name]]
                   for f in FIELDS if f.name in rec.field_flags}
    flags = {r for reasons in rec.field_flags.values() for r in reasons}
    if rec.possible_duplicates:
        flags.add(Reason.POSSIBLE_DUPLICATE)
    return {
        "id": rec.id,
        **{f.name: rec.values[f.name] for f in FIELDS},
        "sources": [_source(s) for s in rec.sources],
        "field_flags": field_flags,
        "flags": sorted(str(r) for r in flags),
        "possible_duplicates": list(rec.possible_duplicates),
    }


def issue_sort_key(i: Issue) -> tuple:
    src = (i.source.file, row_key(i.source.row)) if i.source else ("", (-1, 0))
    return (i.id, i.field, src, str(i.reason))


def issue_to_dict(i: Issue) -> dict[str, Any]:
    return {
        "id": i.id,
        "field": i.field,
        "source": _source(i.source),
        "raw_value": _jsonable(i.raw_value),
        "final_value": _jsonable(i.final_value),
        "reason": str(i.reason),
        "severity": str(i.severity),
        "detail": _jsonable(i.detail),
    }


def build_report(loaded: Iterable[LoadedFile], band: Band, records: list[Record],
                 issues: list[Issue]) -> dict[str, Any]:
    by_reason = Counter(str(i.reason) for i in issues)
    nulls: dict[str, dict[str, int]] = {}
    for f in FIELDS:
        counts = Counter(str(r) for rec in records if rec.values[f.name] is None
                         for r in rec.field_flags.get(f.name, []))
        if counts:
            nulls[f.name] = dict(sorted(counts.items()))
    return {
        "inputs": [{"file": l.file, "sha256": l.sha256, "rows": l.row_count}
                   for l in sorted(loaded, key=lambda l: l.file)],
        "band": {"median": round(band.median, 3), "low": round(band.low, 3),
                 "high": round(band.high, 3), "n": band.n},
        "records": len(records),
        "merged": sum(len({s.file for s in r.sources}) > 1 for r in records),
        "nulls_by_field_and_reason": nulls,
        "corrections": by_reason[Reason.UNIT_CORRECTED_S_TO_MS],
        "conflicts": by_reason[Reason.SOURCE_CONFLICT],
        "possible_duplicate_pairs": by_reason[Reason.POSSIBLE_DUPLICATE] // 2,
        "by_reason": dict(sorted(by_reason.items())),
        "by_severity": dict(sorted(Counter(str(i.severity) for i in issues).items())),
    }


def dumps(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def write_outputs(out_dir: Path, songs: list, issues: list, report: dict) -> None:
    """Plain writes (design §5.6). All input errors are raised before this runs."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, obj in ((SONGS_FILE, songs), (ISSUES_FILE, issues), (REPORT_FILE, report)):
        (out_dir / name).write_text(dumps(obj), encoding="utf-8")
