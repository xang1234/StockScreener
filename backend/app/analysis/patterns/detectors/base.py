"""Detector interfaces, outcome taxonomy, and graceful-failure semantics.

Every detector subclass must:
1. Define a ``name`` class attribute (snake_case string).
2. Implement ``detect()`` returning ``PatternDetectorResult``.

Callers should invoke ``detect_safe()`` (not ``detect()`` directly) to get
exception guarding, result validation, and logging for free.
"""

from __future__ import annotations

import abc
import enum
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Mapping

from app.analysis.patterns.config import SetupEngineParameters
from app.analysis.patterns.models import (
    PatternCandidate,
    PatternCandidateModel,
    coerce_pattern_candidate,
    is_snake_case,
)

if TYPE_CHECKING:
    from app.analysis.patterns.normalization import NormalizedOHLCV

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Outcome taxonomy
# ---------------------------------------------------------------------------

class DetectorOutcome(enum.Enum):
    """Single source of truth for detector result classification.

    Use ``DetectorOutcome.VALUE.value`` in check strings to avoid
    separate constant namespaces drifting out of sync.
    """

    DETECTED = "detected"
    NOT_DETECTED = "not_detected"
    INSUFFICIENT_DATA = "insufficient_data"
    NOT_IMPLEMENTED = "not_implemented"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Detector input
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PatternDetectorInput:
    """Detector input payload independent from scanner infrastructure.

    Data orientation:
    - Price/feature sequences are oldest -> newest.
    - Detector implementations must treat missing feature keys as unavailable,
      not as implicit pass/fail signals.
    """

    symbol: str
    timeframe: str
    daily_bars: int
    weekly_bars: int
    features: Mapping[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Detector result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PatternDetectorResult:
    """Detector output with candidates and diagnostics.

    Conventions:
    - ``candidates`` holds zero or more matches (plural replaces old singular).
    - ``outcome`` is derived from structural fields — never stored.
    - Use the factory class methods for standard outcomes.
    """

    detector_name: str
    candidates: tuple[PatternCandidate | PatternCandidateModel, ...] = ()
    passed_checks: tuple[str, ...] = ()
    failed_checks: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    error_detail: str | None = None

    # -- backward-compat property -------------------------------------------

    @property
    def candidate(self) -> PatternCandidate | PatternCandidateModel | None:
        """First candidate or None (backward compat)."""
        return self.candidates[0] if self.candidates else None

    # -- derived outcome ----------------------------------------------------

    @property
    def outcome(self) -> DetectorOutcome:
        """Derive outcome from structural fields."""
        if self.candidates:
            return DetectorOutcome.DETECTED
        if DetectorOutcome.NOT_IMPLEMENTED.value in self.failed_checks:
            return DetectorOutcome.NOT_IMPLEMENTED
        if DetectorOutcome.ERROR.value in self.failed_checks:
            return DetectorOutcome.ERROR
        if DetectorOutcome.INSUFFICIENT_DATA.value in self.failed_checks:
            return DetectorOutcome.INSUFFICIENT_DATA
        return DetectorOutcome.NOT_DETECTED

    # -- factory class methods ----------------------------------------------

    @classmethod
    def detected(
        cls,
        detector_name: str,
        candidate_or_candidates: (
            PatternCandidate
            | PatternCandidateModel
            | tuple[PatternCandidate | PatternCandidateModel, ...]
            | list[PatternCandidate | PatternCandidateModel]
        ),
        *,
        passed_checks: tuple[str, ...] = (),
        warnings: tuple[str, ...] = (),
    ) -> PatternDetectorResult:
        """One or more candidates detected."""
        if isinstance(candidate_or_candidates, (tuple, list)):
            cands = tuple(candidate_or_candidates)
        else:
            cands = (candidate_or_candidates,)
        return cls(
            detector_name=detector_name,
            candidates=cands,
            passed_checks=(DetectorOutcome.DETECTED.value, *passed_checks),
            warnings=warnings,
        )

    @classmethod
    def no_detection(
        cls,
        detector_name: str,
        *,
        failed_checks: tuple[str, ...] = (),
        warnings: tuple[str, ...] = (),
    ) -> PatternDetectorResult:
        """No candidates found after a valid analysis run."""
        return cls(
            detector_name=detector_name,
            failed_checks=(DetectorOutcome.NOT_DETECTED.value, *failed_checks),
            warnings=warnings,
        )

    @classmethod
    def insufficient_data(
        cls,
        detector_name: str,
        *,
        normalized: NormalizedOHLCV | None = None,
        failed_checks: tuple[str, ...] = (),
        warnings: tuple[str, ...] = (),
    ) -> PatternDetectorResult:
        """Prerequisites not met — insufficient input data."""
        extra_failed = normalized.failed_checks if normalized else ()
        extra_warnings = normalized.warnings if normalized else ()
        return cls(
            detector_name=detector_name,
            failed_checks=(
                DetectorOutcome.INSUFFICIENT_DATA.value,
                *extra_failed,
                *failed_checks,
            ),
            warnings=(*extra_warnings, *warnings),
        )

    @classmethod
    def not_implemented(
        cls,
        detector_name: str,
        *,
        warnings: tuple[str, ...] = (),
    ) -> PatternDetectorResult:
        """Detector stub that has no real logic yet."""
        return cls(
            detector_name=detector_name,
            failed_checks=(DetectorOutcome.NOT_IMPLEMENTED.value,),
            warnings=warnings,
        )

    @classmethod
    def error(
        cls,
        detector_name: str,
        exc: BaseException,
        *,
        warnings: tuple[str, ...] = (),
    ) -> PatternDetectorResult:
        """Detector raised an unhandled exception."""
        return cls(
            detector_name=detector_name,
            failed_checks=(DetectorOutcome.ERROR.value,),
            warnings=warnings,
            error_detail=f"{type(exc).__name__}: {exc}",
        )


# ---------------------------------------------------------------------------
# Abstract detector base
# ---------------------------------------------------------------------------

class PatternDetector(abc.ABC):
    """Abstract detector contract for analysis-layer pattern modules.

    Subclasses must define a ``name`` class attribute (snake_case) and
    implement ``detect()``.  Callers use ``detect_safe()`` for the full
    exception-guard + validation wrapper.
    """

    name: str

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Skip validation on abstract intermediaries (they may not define name).
        # Note: __init_subclass__ fires before ABCMeta sets __abstractmethods__,
        # so we inspect the class body directly for abstract methods.
        has_own_abstract = any(
            getattr(v, "__isabstractmethod__", False)
            for v in vars(cls).values()
        )
        if has_own_abstract:
            return
        if not hasattr(cls, "name") or not isinstance(
            getattr(cls, "name", None), str
        ):
            raise TypeError(
                f"{cls.__name__} must define a 'name' class attribute (str)"
            )
        if not is_snake_case(cls.name):
            raise TypeError(
                f"{cls.__name__}.name must be snake_case, got {cls.name!r}"
            )

    @abc.abstractmethod
    def detect(
        self,
        detector_input: PatternDetectorInput,
        parameters: SetupEngineParameters,
    ) -> PatternDetectorResult:
        """Return a candidate or an explicit no-candidate result."""
        raise NotImplementedError

    def detect_safe(
        self,
        detector_input: PatternDetectorInput,
        parameters: SetupEngineParameters,
    ) -> PatternDetectorResult:
        """Public API: calls detect() with exception guard and validation.

        - Catches all exceptions and converts to ``error`` outcome.
        - Validates ``detector_name`` matches ``self.name``.
        - Coerces all candidates to canonical ``PatternCandidate`` shape
          (using ``detector_input.timeframe`` as default) so the aggregator
          does not need to re-coerce.
        """
        try:
            result = self.detect(detector_input, parameters)
        except Exception as exc:
            logger.warning(
                "Detector %s failed for %s: %s",
                self.name,
                detector_input.symbol,
                exc,
                exc_info=True,
            )
            return PatternDetectorResult.error(self.name, exc)

        # Contract: detector_name must match
        if result.detector_name != self.name:
            err = ValueError(
                f"detector_name mismatch: {result.detector_name!r} != {self.name!r}"
            )
            logger.warning(
                "Detector %s contract violation: %s", self.name, err
            )
            return PatternDetectorResult.error(self.name, err)

        # Coerce candidates to canonical shape (validates + normalizes).
        if not result.candidates:
            return result

        coerced: list[PatternCandidate] = []
        for cand in result.candidates:
            try:
                coerced.append(
                    coerce_pattern_candidate(
                        cand,
                        default_timeframe=detector_input.timeframe,
                    )
                )
            except ValueError as exc:
                logger.warning(
                    "Detector %s produced invalid candidate: %s",
                    self.name,
                    exc,
                )
                return PatternDetectorResult.error(self.name, exc)

        return PatternDetectorResult(
            detector_name=result.detector_name,
            candidates=tuple(coerced),
            passed_checks=result.passed_checks,
            failed_checks=result.failed_checks,
            warnings=result.warnings,
            error_detail=result.error_detail,
        )
