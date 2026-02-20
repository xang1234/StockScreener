# SE-C7 Cross-Detector Normalization and Confidence Calibration

## Scope
- Source code:
  - `backend/app/analysis/patterns/calibration.py`
  - `backend/app/analysis/patterns/aggregator.py`
- Purpose:
  - normalize detector score scales before aggregation
  - align confidence semantics across pattern families
  - provide deterministic, inspectable primary tie-breaking

## Calibration Policy (v1)
- Each detector family has an expected raw envelope for:
  - `quality_score`
  - `readiness_score`
  - `confidence`
- Raw values are mapped into a shared `0..1` normalized space, then projected back to:
  - `quality_score` in `0..100`
  - `readiness_score` in `0..100`
  - `confidence` in `0.05..0.95`

## Confidence Semantics
- Calibrated confidence is blended from three normalized components:
  - detector raw confidence (`55%`)
  - detector quality (`25%`)
  - detector readiness (`20%`)
- A small per-detector bias adjusts family aggressiveness (example: trigger patterns are slightly penalized vs base-structure patterns).
- Resulting confidence means the same thing for every detector: relative confidence after family-aware normalization.

## Canonical Metric Keys Added to Every Candidate
- `calibration_version`
- `calibration_source_detector`
- `raw_quality_score`
- `raw_readiness_score`
- `raw_confidence`
- `raw_confidence_pct`
- `normalized_quality_score_0_1`
- `normalized_readiness_score_0_1`
- `normalized_confidence_0_1`
- `calibrated_quality_score`
- `calibrated_readiness_score`
- `calibrated_confidence`
- `calibrated_confidence_pct`
- `aggregation_rank_score`

These keys provide a stable debugging surface so all detectors expose the same calibration artifacts.

## Before/After Scaling Examples

### Example A: Same raw values across different detector families
- Input (both detectors): `quality=60`, `readiness=62`, `confidence=0.60`
- `nr7_inside_day` (trigger family envelope):
  - normalized quality/readiness become high (`~0.89`, `~0.83`)
  - calibrated output: quality/readiness near upper-mid range
- `vcp` (base-structure envelope):
  - normalized quality/readiness become moderate (`~0.30`, `~0.34`)
  - calibrated output: quality/readiness in mid range

Rationale: identical raw numbers do not imply identical confidence of setup quality across different detector families.

### Example B: Primary tie-break fairness
- Candidate 1 (`nr7_inside_day`): raw confidence `0.78`, moderate quality/readiness.
- Candidate 2 (`vcp`): raw confidence `0.72`, strong quality/readiness.
- Pre-calibration (raw-confidence-only ranking): Candidate 1 would win.
- Post-calibration (composite calibrated rank): Candidate 2 wins due to stronger normalized structure/readiness support.

Rationale: primary selection should not be dominated by detector-specific confidence ceilings.
