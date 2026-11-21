"""Field specs, reason codes, constants and core types (design §3–4).

All per-field rules live in FIELDS. Other modules read them from here rather
than hard-coding field names or domains.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, StrEnum
from typing import Any, Callable, Literal

# --- Source files ----------------------------------------------------------

PART1 = "songs_part1.json"
PART2 = "songs_part2.json"
BOTH = frozenset({PART1, PART2})

ID_FIELD = "id"

# --- Tunable constants -----------------------------------------------------

DUP_TEMPO_TOL = 0.01       # D2: tempos within 1% (relative)
DUP_DURATION_TOL = 0.02    # D2: durations within 2% (relative)
BAND_FACTOR = 2            # R-DUR-1: band = [median / 2, median * 2]
SECONDS_THRESHOLD = 1000   # R-DUR-2: raw values below this may be seconds


# --- Domain checks (named so they show up readably in reprs and errors) ----

def unit_interval(x: float) -> bool:
    return 0 <= x <= 1


def positive(x: float) -> bool:
    return x > 0


def at_least_one(x: int) -> bool:
    return x >= 1


def binary(x: int) -> bool:
    return x in (0, 1)


# --- Field specs -----------------------------------------------------------

Kind = Literal["str", "float", "int"]


@dataclass(frozen=True)
class FieldSpec:
    name: str
    kind: Kind
    check: Callable[[Any], bool] | None
    sources: frozenset[str]


FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("title", "str", None, BOTH),
    FieldSpec("danceability", "float", unit_interval, BOTH),
    FieldSpec("energy", "float", unit_interval, BOTH),
    FieldSpec("acousticness", "float", unit_interval, BOTH),
    FieldSpec("valence", "float", unit_interval, frozenset({PART2})),
    FieldSpec("tempo", "float", positive, BOTH),
    FieldSpec("duration_ms", "int", positive, BOTH),  # plus R-DUR (duration.py)
    FieldSpec("num_sections", "int", at_least_one, BOTH),
    FieldSpec("num_segments", "int", at_least_one, BOTH),
    FieldSpec("mood", "int", binary, BOTH),  # R-MOOD-1: opaque binary category
)

FIELDS_BY_NAME: dict[str, FieldSpec] = {f.name: f for f in FIELDS}


def columns_for(file: str) -> frozenset[str]:
    """Columns allowed in a given source file (R-ING-4). Empty if unknown file."""
    names = {f.name for f in FIELDS if file in f.sources}
    return frozenset({ID_FIELD, *names}) if names else frozenset()


# --- Reasons ---------------------------------------------------------------

class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Reason(StrEnum):
    MISSING_ABSENT = "missing_absent"
    MISSING_NULL = "missing_null"
    MISSING_NA = "missing_na"
    MISSING_EMPTY = "missing_empty"
    NOT_IN_SOURCE = "not_in_source"
    COERCED_FROM_STRING = "coerced_from_string"
    WHITESPACE_NORMALIZED = "whitespace_normalized"
    UNPARSEABLE = "unparseable"
    NOT_INTEGER = "not_integer"
    OUT_OF_RANGE = "out_of_range"
    IMPLAUSIBLE_DURATION = "implausible_duration"
    UNIT_CORRECTED_S_TO_MS = "unit_corrected_s_to_ms"
    DURATION_UNVERIFIED = "duration_unverified"
    SOURCE_CONFLICT = "source_conflict"
    POSSIBLE_DUPLICATE = "possible_duplicate"
    MISSING_ID = "missing_id"


_I, _W, _E = Severity.INFO, Severity.WARNING, Severity.ERROR

SEVERITY: dict[Reason, Severity] = {
    Reason.MISSING_ABSENT: _W,
    Reason.MISSING_NULL: _W,
    Reason.MISSING_NA: _W,
    Reason.MISSING_EMPTY: _W,
    Reason.NOT_IN_SOURCE: _I,
    Reason.COERCED_FROM_STRING: _I,
    Reason.WHITESPACE_NORMALIZED: _I,
    Reason.UNPARSEABLE: _W,
    Reason.NOT_INTEGER: _W,
    Reason.OUT_OF_RANGE: _W,
    Reason.IMPLAUSIBLE_DURATION: _W,
    Reason.UNIT_CORRECTED_S_TO_MS: _W,
    Reason.DURATION_UNVERIFIED: _I,
    Reason.SOURCE_CONFLICT: _W,
    Reason.POSSIBLE_DUPLICATE: _I,
    Reason.MISSING_ID: _E,
}


# --- ABSENT sentinel -------------------------------------------------------

class _Absent(Enum):
    """Key missing from the source. Kept distinct from JSON null (R-MISS-1)."""

    ABSENT = "ABSENT"

    def __repr__(self) -> str:
        return "ABSENT"


ABSENT = _Absent.ABSENT


# --- Core types ------------------------------------------------------------

class PipelineError(Exception):
    """Structural problem in the inputs. The run stops before writing (design §6)."""


@dataclass(frozen=True)
class Source:
    file: str
    row: str


@dataclass(frozen=True)
class Issue:
    id: str
    field: str
    source: Source | None
    raw_value: Any
    final_value: Any
    reason: Reason
    detail: dict[str, Any] | None = None

    @property
    def severity(self) -> Severity:
        return SEVERITY[self.reason]


@dataclass(frozen=True)
class Cleaned:
    """A cleaned value plus every issue found on the way. None ⇒ ≥1 issue (P2)."""

    value: Any | None
    issues: tuple[Issue, ...] = ()

    def __post_init__(self) -> None:
        if self.value is None and not self.issues:
            raise ValueError("a null value must carry at least one issue (P2)")


@dataclass
class SourceRow:
    id: str
    source: Source
    raw: dict[str, Any] = field(default_factory=dict)
    clean: dict[str, Cleaned] = field(default_factory=dict)
