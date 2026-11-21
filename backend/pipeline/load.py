"""Read column-oriented source JSON into SourceRows (design §5.1).

Source layout: {column: {row_index: value}}. Rows are rebuilt from the row
indexes of the "id" column (R-ING-1). Anything structurally unexpected stops
the run with a PipelineError (R-ING-4). Data problems never do: they become
issues.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .clean import clean_field
from .schema import (
    ABSENT,
    FIELDS,
    ID_FIELD,
    Issue,
    PipelineError,
    Reason,
    Source,
    SourceRow,
    columns_for,
)


@dataclass
class LoadedFile:
    file: str
    sha256: str
    row_count: int  # rows in the source, including skipped ones
    rows: list[SourceRow] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)  # file-level, e.g. missing_id


def row_key(row: str) -> tuple[int, int | str]:
    """Sort row indexes numerically, falling back to text for non-digit indexes."""
    return (0, int(row)) if row.isdigit() else (1, row)


def _keep_constant(literal: str) -> str:
    """json parse_constant hook: keep NaN/Infinity as text so cleaning rejects them."""
    return literal


def load_file(path: Path | str) -> LoadedFile:
    path = Path(path)
    file = path.name
    allowed = columns_for(file)
    if not allowed:
        raise PipelineError(f"{file}: unknown source file (expected one of the configured parts)")

    try:
        data_bytes = path.read_bytes()
    except OSError as e:
        raise PipelineError(f"{file}: cannot read {path} ({e.strerror})") from e
    try:
        data = json.loads(data_bytes.decode("utf-8"), parse_constant=_keep_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise PipelineError(f"{file}: invalid JSON ({e})") from e

    _check_structure(file, data, allowed)

    loaded = LoadedFile(
        file=file,
        sha256=hashlib.sha256(data_bytes).hexdigest(),
        row_count=len(data[ID_FIELD]),
    )
    specs = [s for s in FIELDS if file in s.sources]

    for row in sorted(data[ID_FIELD], key=row_key):
        source = Source(file, row)
        raw_id = data[ID_FIELD][row]
        if not isinstance(raw_id, str) or raw_id.strip() == "":
            loaded.issues.append(
                Issue(id="", field=ID_FIELD, source=source, raw_value=raw_id,
                      final_value=None, reason=Reason.MISSING_ID)
            )
            continue

        raw = {s.name: data.get(s.name, {}).get(row, ABSENT) for s in specs}
        clean = {s.name: clean_field(s, raw[s.name], id=raw_id, source=source) for s in specs}
        loaded.rows.append(SourceRow(id=raw_id, source=source, raw=raw, clean=clean))

    return loaded


def _check_structure(file: str, data: Any, allowed: frozenset[str]) -> None:
    if not isinstance(data, dict):
        raise PipelineError(f"{file}: top level must be an object of columns")
    if ID_FIELD not in data:
        raise PipelineError(f"{file}: missing '{ID_FIELD}' column")
    for name, column in data.items():
        if name not in allowed:
            raise PipelineError(f"{file}: unknown column '{name}'")
        if not isinstance(column, dict):
            raise PipelineError(f"{file}: column '{name}' must be an object of row_index -> value")
    ids = data[ID_FIELD].keys()
    for name, column in data.items():
        extra = sorted(set(column) - set(ids), key=row_key)
        if extra:
            raise PipelineError(
                f"{file}: column '{name}' has row index '{extra[0]}' that is not in '{ID_FIELD}'"
            )
