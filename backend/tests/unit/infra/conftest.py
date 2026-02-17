"""Override the global autouse stub — infra tests need the real DataPreparationLayer."""

import pytest


@pytest.fixture(autouse=True)
def _stub_external_data():
    """No-op: let infra tests exercise the real prepare_data code paths."""
    yield
