"""Pure per-value cleaning functions (design §5.2).

Each step either passes a value on or reports a Reason. clean_field() chains
them for one field and turns the reasons into Issues. Nothing here invents a
value: a value is kept, parsed into its proper type, or nulled (P1, P2).
"""
from __future__ import annotations

import math
import re
import unicodedata
from typing import Any

from .schema import ABSENT, Cleaned, FieldSpec, Issue, Reason, Source

DURATION_FIELD = "duration_ms"  # domain handled by duration.py, not check_range

# Plain decimal / scientific notation, ASCII digits only. This is stricter
# than float(), which also accepts "nan", "inf", "1_000" and non-ASCII digits.
_NUMBER_RE = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_WS_RE = re.compile(r"\s+")


def classify_missing(raw: Any) -> Reason | None:
    """Return the missing-value reason for raw, or None if it is present (R-MISS-1)."""
    if raw is ABSENT:
        return Reason.MISSING_ABSENT
    if raw is None:
        return Reason.MISSING_NULL
    if isinstance(raw, str):
        stripped = raw.strip()
        if stripped == "":
            return Reason.MISSING_EMPTY
        if stripped.casefold() == "n/a":
            return Reason.MISSING_NA
    return None


def normalize_text(s: str) -> str:
    """NFC, collapse runs of whitespace to one space, trim (R-TXT-1, R-TXT-2)."""
    return _WS_RE.sub(" ", unicodedata.normalize("NFC", s)).strip()


def to_number(raw: Any) -> tuple[int | float | None, Reason | None]:
    """Parse raw into a finite number.

    Returns (value, None) for a native number, (value, COERCED_FROM_STRING)
    for a numeric string, and (None, UNPARSEABLE) for anything else.
    """
    if isinstance(raw, bool):  # bool is an int subclass; never a number (R-TYPE-4)
        return None, Reason.UNPARSEABLE
    if isinstance(raw, int):
        return raw, None
    if isinstance(raw, float):
        return (raw, None) if math.isfinite(raw) else (None, Reason.UNPARSEABLE)
    if isinstance(raw, str):
        s = raw.strip()
        if _NUMBER_RE.fullmatch(s):
            value = float(s)
            if math.isfinite(value):  # e.g. "1e999" overflows to inf
                return value, Reason.COERCED_FROM_STRING
    return None, Reason.UNPARSEABLE


def to_int(value: int | float) -> tuple[int | None, Reason | None]:
    """Accept ints and integral floats (8.0 -> 8). Anything else is NOT_INTEGER (R-TYPE-3)."""
    if isinstance(value, int):
        return value, None
    if value.is_integer():
        return int(value), None
    return None, Reason.NOT_INTEGER


def check_range(spec: FieldSpec, value: Any) -> Reason | None:
    """OUT_OF_RANGE if value fails the field's domain check. Never clamps."""
    if spec.check is None or spec.check(value):
        return None
    return Reason.OUT_OF_RANGE


def clean_field(spec: FieldSpec, raw: Any, *, id: str, source: Source) -> Cleaned:
    """Clean one raw source value for one field into a Cleaned value + issues."""
    value, reasons = _clean_value(spec, raw)
    issues = tuple(
        Issue(id=id, field=spec.name, source=source, raw_value=raw, final_value=value, reason=r)
        for r in reasons
    )
    return Cleaned(value, issues)


def _clean_value(spec: FieldSpec, raw: Any) -> tuple[Any, list[Reason]]:
    """The actual chain. Returns (final value, reasons in the order found)."""
    missing = classify_missing(raw)
    if missing is not None:
        return None, [missing]

    if spec.kind == "str":
        if not isinstance(raw, str):
            return None, [Reason.UNPARSEABLE]
        text = normalize_text(raw)
        if text == "":  # backstop; classify_missing normally catches this (R-TXT-3)
            return None, [Reason.MISSING_EMPTY]
        # Only whitespace changes are reported. NFC alone does not change meaning.
        changed = text != unicodedata.normalize("NFC", raw)
        return text, [Reason.WHITESPACE_NORMALIZED] if changed else []

    reasons: list[Reason] = []
    number, why = to_number(raw)
    if number is None:
        return None, [why]
    if why is not None:
        reasons.append(why)

    if spec.kind == "int":
        number, why = to_int(number)
        if number is None:
            return None, reasons + [why]
    else:
        number = float(number)

    if spec.name != DURATION_FIELD:
        why = check_range(spec, number)
        if why is not None:
            return None, reasons + [why]

    return number, reasons
