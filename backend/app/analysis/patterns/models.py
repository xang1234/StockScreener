"""Canonical Setup Engine schema contract and validation helpers.

This module is the single source of truth for the ``setup_engine`` payload:
field names, types, units, nullability, and naming policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import re
from typing import Any, Literal, Mapping, Sequence, TypedDict, cast


SETUP_ENGINE_DEFAULT_SCHEMA_VERSION = "v1"
SETUP_ENGINE_ALLOWED_TIMEFRAMES = frozenset({"daily", "weekly"})
SETUP_ENGINE_NUMERIC_UNITS = frozenset({"pct", "ratio", "days", "weeks", "price"})

_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class PatternCandidate(TypedDict, total=False):
    """Candidate setup emitted by pattern detectors."""

    pattern: str
    confidence_pct: float | None
    pivot_price: float | None
    pivot_type: str | None
    pivot_date: str | None
    distance_to_pivot_pct: float | None
    setup_score: float | None
    quality_score: float | None
    readiness_score: float | None
    timeframe: Literal["daily", "weekly"]


class SetupEngineExplain(TypedDict):
    """Human-readable checks and key levels used by setup_engine."""

    passed_checks: list[str]
    failed_checks: list[str]
    key_levels: dict[str, float | None]
    invalidation_flags: list[str]


class SetupEnginePayload(TypedDict):
    """Top-level payload stored under ``details.setup_engine``."""

    schema_version: str
    timeframe: Literal["daily", "weekly"]

    setup_score: float | None
    quality_score: float | None
    readiness_score: float | None
    setup_ready: bool

    pattern_primary: str | None
    pattern_confidence: float | None
    pivot_price: float | None
    pivot_type: str | None
    pivot_date: str | None

    distance_to_pivot_pct: float | None
    atr14_pct: float | None
    bb_width_pctile_252: float | None
    volume_vs_50d: float | None
    rs_line_new_high: bool

    candidates: list[PatternCandidate]
    explain: SetupEngineExplain


@dataclass(frozen=True)
class SetupEngineFieldSpec:
    """Schema reference row for contract docs and review."""

    name: str
    type_name: str
    nullable: bool
    unit: str | None
    source_module: str
    description: str


SETUP_ENGINE_FIELD_SPECS: tuple[SetupEngineFieldSpec, ...] = (
    SetupEngineFieldSpec(
        name="schema_version",
        type_name="str",
        nullable=False,
        unit=None,
        source_module="backend/app/analysis/patterns/models.py",
        description="Schema version for compatibility gates.",
    ),
    SetupEngineFieldSpec(
        name="timeframe",
        type_name="Literal['daily','weekly']",
        nullable=False,
        unit=None,
        source_module="backend/app/scanners/setup_engine_scanner.py",
        description="Data horizon used for pattern classification.",
    ),
    SetupEngineFieldSpec(
        name="setup_score",
        type_name="float",
        nullable=True,
        unit="pct",
        source_module="backend/app/scanners/setup_engine_scanner.py",
        description="Overall setup quality score on 0..100 scale.",
    ),
    SetupEngineFieldSpec(
        name="quality_score",
        type_name="float",
        nullable=True,
        unit="pct",
        source_module="backend/app/scanners/setup_engine_scanner.py",
        description="Pattern quality score on 0..100 scale.",
    ),
    SetupEngineFieldSpec(
        name="readiness_score",
        type_name="float",
        nullable=True,
        unit="pct",
        source_module="backend/app/scanners/setup_engine_scanner.py",
        description="Breakout readiness score on 0..100 scale.",
    ),
    SetupEngineFieldSpec(
        name="setup_ready",
        type_name="bool",
        nullable=False,
        unit=None,
        source_module="backend/app/scanners/setup_engine_scanner.py",
        description="True when readiness threshold is met and no failed checks remain.",
    ),
    SetupEngineFieldSpec(
        name="pattern_primary",
        type_name="str",
        nullable=True,
        unit=None,
        source_module="backend/app/scanners/setup_engine_scanner.py",
        description="Primary detected pattern label.",
    ),
    SetupEngineFieldSpec(
        name="pattern_confidence",
        type_name="float",
        nullable=True,
        unit="pct",
        source_module="backend/app/scanners/setup_engine_scanner.py",
        description="Confidence in pattern_primary on 0..100 scale.",
    ),
    SetupEngineFieldSpec(
        name="pivot_price",
        type_name="float",
        nullable=True,
        unit="price",
        source_module="backend/app/scanners/setup_engine_scanner.py",
        description="Canonical pivot price for the primary pattern.",
    ),
    SetupEngineFieldSpec(
        name="pivot_type",
        type_name="str",
        nullable=True,
        unit=None,
        source_module="backend/app/scanners/setup_engine_scanner.py",
        description="Pivot family (breakout, pullback, reclaim, etc).",
    ),
    SetupEngineFieldSpec(
        name="pivot_date",
        type_name="str(YYYY-MM-DD)",
        nullable=True,
        unit=None,
        source_module="backend/app/scanners/setup_engine_scanner.py",
        description="Date associated with pivot_price.",
    ),
    SetupEngineFieldSpec(
        name="distance_to_pivot_pct",
        type_name="float",
        nullable=True,
        unit="pct",
        source_module="backend/app/scanners/setup_engine_scanner.py",
        description="Percent distance from current price to pivot.",
    ),
    SetupEngineFieldSpec(
        name="atr14_pct",
        type_name="float",
        nullable=True,
        unit="pct",
        source_module="backend/app/scanners/setup_engine_scanner.py",
        description="ATR(14) as a percentage of current price.",
    ),
    SetupEngineFieldSpec(
        name="bb_width_pctile_252",
        type_name="float",
        nullable=True,
        unit="pct",
        source_module="backend/app/scanners/setup_engine_scanner.py",
        description="252-session Bollinger width percentile on 0..100.",
    ),
    SetupEngineFieldSpec(
        name="volume_vs_50d",
        type_name="float",
        nullable=True,
        unit="ratio",
        source_module="backend/app/scanners/setup_engine_scanner.py",
        description="Volume / 50-day average volume ratio.",
    ),
    SetupEngineFieldSpec(
        name="rs_line_new_high",
        type_name="bool",
        nullable=False,
        unit=None,
        source_module="backend/app/scanners/setup_engine_scanner.py",
        description="True when RS line has made a new high for timeframe.",
    ),
    SetupEngineFieldSpec(
        name="candidates",
        type_name="list[PatternCandidate]",
        nullable=False,
        unit=None,
        source_module="backend/app/scanners/setup_engine_scanner.py",
        description="Alternative pattern candidates for explainability.",
    ),
    SetupEngineFieldSpec(
        name="explain",
        type_name="SetupEngineExplain",
        nullable=False,
        unit=None,
        source_module="backend/app/scanners/setup_engine_scanner.py",
        description="Structured pass/fail checks and key levels.",
    ),
    SetupEngineFieldSpec(
        name="explain.passed_checks",
        type_name="list[str]",
        nullable=False,
        unit=None,
        source_module="backend/app/scanners/setup_engine_scanner.py",
        description="Checks passed by the setup.",
    ),
    SetupEngineFieldSpec(
        name="explain.failed_checks",
        type_name="list[str]",
        nullable=False,
        unit=None,
        source_module="backend/app/scanners/setup_engine_scanner.py",
        description="Checks failed by the setup.",
    ),
    SetupEngineFieldSpec(
        name="explain.key_levels",
        type_name="dict[str, float|None]",
        nullable=False,
        unit="price",
        source_module="backend/app/scanners/setup_engine_scanner.py",
        description="Named price levels (pivot, support, invalidation, etc).",
    ),
    SetupEngineFieldSpec(
        name="explain.invalidation_flags",
        type_name="list[str]",
        nullable=False,
        unit=None,
        source_module="backend/app/scanners/setup_engine_scanner.py",
        description="Reasons this setup should not be acted on.",
    ),
)

SETUP_ENGINE_REQUIRED_KEYS: tuple[str, ...] = (
    "schema_version",
    "timeframe",
    "setup_score",
    "quality_score",
    "readiness_score",
    "setup_ready",
    "pattern_primary",
    "pattern_confidence",
    "pivot_price",
    "pivot_type",
    "pivot_date",
    "distance_to_pivot_pct",
    "atr14_pct",
    "bb_width_pctile_252",
    "volume_vs_50d",
    "rs_line_new_high",
    "candidates",
    "explain",
)


def is_snake_case(name: str) -> bool:
    """Return True when *name* follows snake_case."""
    return bool(_SNAKE_CASE_RE.fullmatch(name))


def normalize_iso_date(value: str | date | datetime | None) -> str | None:
    """Normalize date-ish input to ``YYYY-MM-DD`` or return None."""
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    if not isinstance(value, str):
        raise ValueError(f"Date value must be str/date/datetime, got {type(value)!r}")

    if not _ISO_DATE_RE.fullmatch(value):
        raise ValueError(
            "Date value must use YYYY-MM-DD format"
        )

    # Verifies calendar validity (e.g. 2026-02-30 is invalid).
    date.fromisoformat(value)
    return value


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_setup_engine_payload(payload: Mapping[str, Any]) -> list[str]:
    """Validate contract compliance and return human-readable errors."""
    errors: list[str] = []

    for key in SETUP_ENGINE_REQUIRED_KEYS:
        if key not in payload:
            errors.append(f"Missing required top-level key: {key}")

    for key in payload.keys():
        if not is_snake_case(key):
            errors.append(f"Top-level key is not snake_case: {key}")

    timeframe = payload.get("timeframe")
    if timeframe not in SETUP_ENGINE_ALLOWED_TIMEFRAMES:
        errors.append(
            "timeframe must be one of: daily, weekly"
        )

    pivot_date = payload.get("pivot_date")
    try:
        normalize_iso_date(cast(str | date | datetime | None, pivot_date))
    except ValueError as exc:
        errors.append(f"pivot_date invalid: {exc}")

    explain = payload.get("explain")
    if not isinstance(explain, Mapping):
        errors.append("explain must be an object")
    else:
        for required in ("passed_checks", "failed_checks", "key_levels", "invalidation_flags"):
            if required not in explain:
                errors.append(f"explain missing key: {required}")

        key_levels = explain.get("key_levels")
        if isinstance(key_levels, Mapping):
            for level_name, level_value in key_levels.items():
                if not is_snake_case(str(level_name)):
                    errors.append(
                        f"explain.key_levels key must be snake_case: {level_name}"
                    )
                if level_value is not None and not _is_number(level_value):
                    errors.append(
                        f"explain.key_levels[{level_name}] must be numeric or null"
                    )
        else:
            errors.append("explain.key_levels must be an object")

    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        errors.append("candidates must be a list")
    else:
        for index, candidate in enumerate(candidates):
            if not isinstance(candidate, Mapping):
                errors.append(f"candidates[{index}] must be an object")
                continue

            for key in candidate.keys():
                if not is_snake_case(str(key)):
                    errors.append(
                        f"candidates[{index}] key is not snake_case: {key}"
                    )

            candidate_date = candidate.get("pivot_date")
            try:
                normalize_iso_date(cast(str | date | datetime | None, candidate_date))
            except ValueError as exc:
                errors.append(f"candidates[{index}].pivot_date invalid: {exc}")

            candidate_timeframe = candidate.get("timeframe")
            if (
                candidate_timeframe is not None
                and candidate_timeframe not in SETUP_ENGINE_ALLOWED_TIMEFRAMES
            ):
                errors.append(
                    f"candidates[{index}].timeframe must be daily or weekly"
                )

    return errors


def assert_valid_setup_engine_payload(payload: Mapping[str, Any]) -> None:
    """Raise ValueError if payload does not satisfy the contract."""
    errors = validate_setup_engine_payload(payload)
    if errors:
        raise ValueError("; ".join(errors))
