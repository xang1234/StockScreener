# SE-B2 PatternCandidate and Shared Output Schemas

## Canonical Candidate Model
- Source: `backend/app/analysis/patterns/models.py`
- Typed model: `PatternCandidateModel`
- Serialized shape: `PatternCandidate` (TypedDict)

## Required/Optional Core Fields
- Required:
  - `pattern`
  - `timeframe`
- Optional metadata:
  - `source_detector`
  - `pivot_price`, `pivot_type`, `pivot_date`
  - `distance_to_pivot_pct`

## Score/Confidence Conventions
- Scores (`setup_score`, `quality_score`, `readiness_score`): `0..100`
- Confidence:
  - canonical internal field: `confidence` in `0..1`
  - serialized compatibility alias: `confidence_pct` in `0..100`

## Shared Payloads
- `metrics: dict[str, JsonScalar]`
- `checks: dict[str, bool]`
- `notes: list[str]`

All keys in `metrics` and `checks` must be `snake_case` for stable query/UI mapping.

## Consumption Path
1. Detector emits `PatternCandidateModel` or mapping.
2. Aggregator and scanner call `coerce_pattern_candidate(...)`.
3. Canonical candidate enters `setup_engine.candidates[]` with deterministic shape.
