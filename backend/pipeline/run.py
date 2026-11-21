"""Run the stages in order (design §1) and return the serializable outputs."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .duplicates import find_possible_duplicates
from .duration import apply_durations, compute_band
from .load import load_file
from .merge import merge_by_id
from .output import build_report, issue_sort_key, issue_to_dict, record_to_dict
from .schema import PART1, PART2


@dataclass
class Outputs:
    songs: list[dict[str, Any]]
    issues: list[dict[str, Any]]
    report: dict[str, Any]


def build(data_dir: Path | str, files: Sequence[str] = (PART1, PART2)) -> Outputs:
    data_dir = Path(data_dir)
    loaded = [load_file(data_dir / f) for f in files]           # 1 load (+ 2 clean)
    rows = [r for l in loaded for r in l.rows]
    band = compute_band(rows)                                     # 3 durations
    apply_durations(rows, band)
    merged = merge_by_id(rows)                                    # 4 merge
    dup_issues = find_possible_duplicates(merged.records)         # 5 duplicates

    issues = sorted([i for l in loaded for i in l.issues] + merged.issues + dup_issues,
                    key=issue_sort_key)                           # 6 assemble
    return Outputs(
        songs=[record_to_dict(r) for r in merged.records],
        issues=[issue_to_dict(i) for i in issues],
        report=build_report(loaded, band, merged.records, issues),
    )
