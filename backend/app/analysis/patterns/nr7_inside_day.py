"""NR7/Inside-Day trigger detector entrypoint.

Expected input orientation:
- Daily bars in chronological order.
- Trigger bars are evaluated on completed bars only.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.analysis.patterns.config import SetupEngineParameters
from app.analysis.patterns.detectors.base import (
    PatternDetector,
    PatternDetectorInput,
    PatternDetectorResult,
)
from app.analysis.patterns.models import PatternCandidateModel
from app.analysis.patterns.normalization import normalize_detector_input_ohlcv

_NR7_LOOKBACK_BARS = 7
_MAX_TRIGGER_CANDIDATES = 5
_RECENT_TRIGGER_BARS = 20
_TRIGGER_RANGE_REFERENCE_PCT = 4.0
_VOLUME_NEUTRAL_RATIO = 1.05


@dataclass(frozen=True)
class _TriggerSignal:
    idx: int
    trigger_subtype: str
    trigger_is_nr7: bool
    trigger_is_inside_day: bool
    trigger_high: float
    trigger_low: float
    trigger_range_points: float
    trigger_range_pct: float
    range_min_7d_points: float
    range_rank_7d: int
    trigger_volume: float
    volume_mean_20d: float
    volume_ratio_20d: float
    ema21_trigger: float | None
    close_above_ema21: bool
    recency_bars: int
    score: float


class NR7InsideDayDetector(PatternDetector):
    """Compile-safe entrypoint for trigger-family detection."""

    name = "nr7_inside_day"

    def detect(
        self,
        detector_input: PatternDetectorInput,
        parameters: SetupEngineParameters,
    ) -> PatternDetectorResult:
        del parameters
        normalized = normalize_detector_input_ohlcv(
            features=detector_input.features,
            timeframe="daily",
            min_bars=10,
            feature_key="daily_ohlcv",
            fallback_bar_count=detector_input.daily_bars,
        )
        if not normalized.prerequisites_ok:
            return PatternDetectorResult.insufficient_data(
                self.name, normalized=normalized
            )

        if normalized.frame is None:
            return PatternDetectorResult.insufficient_data(
                self.name,
                failed_checks=("missing_daily_ohlcv_for_nr7_inside_day",),
                warnings=normalized.warnings,
            )

        frame = normalized.frame
        if len(frame) < _NR7_LOOKBACK_BARS:
            return PatternDetectorResult.no_detection(
                self.name,
                failed_checks=("nr7_window_insufficient",),
                warnings=normalized.warnings,
            )

        high = frame["High"]
        low = frame["Low"]
        close = frame["Close"]
        volume = frame["Volume"]
        ranges = high - low
        ema21 = close.ewm(span=21, adjust=False).mean()

        signals: list[_TriggerSignal] = []
        for idx in range(_NR7_LOOKBACK_BARS - 1, len(frame)):
            trigger_range_points = float(ranges.iat[idx])
            if pd.isna(trigger_range_points) or trigger_range_points < 0.0:
                continue

            range_window = ranges.iloc[
                idx - _NR7_LOOKBACK_BARS + 1 : idx + 1
            ]
            if range_window.empty:
                continue
            range_min_7d_points = float(range_window.min())
            trigger_is_nr7 = bool(
                trigger_range_points <= range_min_7d_points + 1e-9
            )

            prev_idx = idx - 1
            trigger_is_inside_day = bool(
                prev_idx >= 0
                and float(high.iat[idx]) < float(high.iat[prev_idx])
                and float(low.iat[idx]) > float(low.iat[prev_idx])
            )
            if not (trigger_is_nr7 or trigger_is_inside_day):
                continue

            trigger_subtype = _trigger_subtype(
                trigger_is_nr7=trigger_is_nr7,
                trigger_is_inside_day=trigger_is_inside_day,
            )
            trigger_high = float(high.iat[idx])
            trigger_low = float(low.iat[idx])
            trigger_range_pct = (
                (trigger_range_points / max(abs(trigger_high), 1e-9)) * 100.0
            )
            range_rank_7d = int(
                (range_window <= (trigger_range_points + 1e-9)).sum()
            )
            trigger_volume = float(volume.iat[idx])
            volume_mean_20d = float(volume.iloc[max(0, idx - 19) : idx + 1].mean())
            if volume_mean_20d <= 0.0 or pd.isna(volume_mean_20d):
                volume_ratio_20d = 1.0
            else:
                volume_ratio_20d = trigger_volume / volume_mean_20d

            ema21_trigger_raw = float(ema21.iat[idx])
            if pd.isna(ema21_trigger_raw):
                ema21_trigger = None
                close_above_ema21 = False
            else:
                ema21_trigger = ema21_trigger_raw
                close_above_ema21 = bool(float(close.iat[idx]) >= ema21_trigger)

            recency_bars = (len(frame) - 1) - idx
            score = _signal_score(
                trigger_subtype=trigger_subtype,
                trigger_range_pct=trigger_range_pct,
                volume_ratio_20d=volume_ratio_20d,
                close_above_ema21=close_above_ema21,
                recency_bars=recency_bars,
            )
            signals.append(
                _TriggerSignal(
                    idx=idx,
                    trigger_subtype=trigger_subtype,
                    trigger_is_nr7=trigger_is_nr7,
                    trigger_is_inside_day=trigger_is_inside_day,
                    trigger_high=trigger_high,
                    trigger_low=trigger_low,
                    trigger_range_points=trigger_range_points,
                    trigger_range_pct=trigger_range_pct,
                    range_min_7d_points=range_min_7d_points,
                    range_rank_7d=range_rank_7d,
                    trigger_volume=trigger_volume,
                    volume_mean_20d=volume_mean_20d,
                    volume_ratio_20d=volume_ratio_20d,
                    ema21_trigger=ema21_trigger,
                    close_above_ema21=close_above_ema21,
                    recency_bars=recency_bars,
                    score=score,
                )
            )

        if not signals:
            return PatternDetectorResult.no_detection(
                self.name,
                failed_checks=("nr7_inside_day_trigger_not_found",),
                warnings=normalized.warnings,
            )

        signals.sort(
            key=lambda signal: (
                -signal.score,
                signal.recency_bars,
                signal.trigger_subtype != "nr7_inside_day",
                -signal.idx,
            )
        )

        last_close = float(close.iat[-1])
        candidates: list[PatternCandidateModel] = []
        for rank, signal in enumerate(signals[:_MAX_TRIGGER_CANDIDATES], start=1):
            recency_component = max(
                0.0, 1.0 - (signal.recency_bars / _RECENT_TRIGGER_BARS)
            )
            confidence = min(0.78, max(0.05, 0.20 + signal.score * 0.55))
            quality_score = min(65.0, max(0.0, 20.0 + signal.score * 55.0))
            readiness_score = min(
                70.0,
                max(
                    0.0,
                    24.0
                    + (recency_component * 22.0)
                    + (8.0 if signal.trigger_subtype == "nr7_inside_day" else 4.0)
                    + (4.0 if signal.close_above_ema21 else 0.0),
                ),
            )

            candidates.append(
                PatternCandidateModel(
                    pattern=self.name,
                    timeframe="daily",
                    source_detector=self.name,
                    pivot_price=signal.trigger_high,
                    pivot_type=f"{signal.trigger_subtype}_trigger_high",
                    pivot_date=frame.index[signal.idx].date().isoformat(),
                    distance_to_pivot_pct=(
                        ((signal.trigger_high - last_close) / max(abs(last_close), 1e-9))
                        * 100.0
                    ),
                    confidence=confidence,
                    quality_score=quality_score,
                    readiness_score=readiness_score,
                    metrics={
                        "trigger_rank": rank,
                        "trigger_subtype": signal.trigger_subtype,
                        "trigger_is_nr7": signal.trigger_is_nr7,
                        "trigger_is_inside_day": signal.trigger_is_inside_day,
                        "trigger_high": round(signal.trigger_high, 4),
                        "trigger_low": round(signal.trigger_low, 4),
                        "trigger_range_points": round(
                            signal.trigger_range_points, 6
                        ),
                        "trigger_range_pct": round(signal.trigger_range_pct, 6),
                        "range_min_7d_points": round(
                            signal.range_min_7d_points, 6
                        ),
                        "range_rank_7d": signal.range_rank_7d,
                        "trigger_volume": round(signal.trigger_volume, 4),
                        "volume_mean_20d": round(signal.volume_mean_20d, 4),
                        "volume_ratio_20d": round(signal.volume_ratio_20d, 6),
                        "ema21_trigger": (
                            round(signal.ema21_trigger, 6)
                            if signal.ema21_trigger is not None
                            else None
                        ),
                        "close_above_ema21": signal.close_above_ema21,
                        "trigger_recency_bars": signal.recency_bars,
                        "trigger_score": round(signal.score, 6),
                    },
                    checks={
                        "trigger_detected": True,
                        "trigger_is_nr7": bool(signal.trigger_is_nr7),
                        "trigger_is_inside_day": bool(signal.trigger_is_inside_day),
                        "trigger_is_combined": bool(
                            signal.trigger_subtype == "nr7_inside_day"
                        ),
                        "range_is_7d_min": bool(signal.trigger_is_nr7),
                        "inside_day_structure_valid": bool(
                            signal.trigger_is_inside_day
                        ),
                        "volume_not_expanded": bool(
                            signal.volume_ratio_20d <= _VOLUME_NEUTRAL_RATIO
                        ),
                        "context_close_above_ema21": bool(
                            signal.close_above_ema21
                        ),
                    },
                    notes=(
                        "trigger_detector_lightweight_scoring",
                        f"subtype_{signal.trigger_subtype}",
                    ),
                )
            )

        return PatternDetectorResult.detected(
            self.name,
            tuple(candidates),
            passed_checks=(
                "nr7_inside_day_trigger_found",
                "trigger_subtypes_labeled",
            ),
            warnings=normalized.warnings,
        )


def _trigger_subtype(*, trigger_is_nr7: bool, trigger_is_inside_day: bool) -> str:
    if trigger_is_nr7 and trigger_is_inside_day:
        return "nr7_inside_day"
    if trigger_is_nr7:
        return "nr7"
    return "inside_day"


def _signal_score(
    *,
    trigger_subtype: str,
    trigger_range_pct: float,
    volume_ratio_20d: float,
    close_above_ema21: bool,
    recency_bars: int,
) -> float:
    subtype_bonus = {
        "nr7_inside_day": 0.18,
        "nr7": 0.10,
        "inside_day": 0.08,
    }.get(trigger_subtype, 0.05)
    range_tight_component = max(
        0.0, 1.0 - (trigger_range_pct / _TRIGGER_RANGE_REFERENCE_PCT)
    )
    volume_dry_component = max(
        0.0, 1.0 - min(max(volume_ratio_20d, 0.0), 2.0)
    )
    recency_component = max(0.0, 1.0 - (recency_bars / _RECENT_TRIGGER_BARS))

    return (
        0.20
        + subtype_bonus
        + (range_tight_component * 0.28)
        + (volume_dry_component * 0.12)
        + (0.08 if close_above_ema21 else 0.0)
        + (recency_component * 0.14)
    )
