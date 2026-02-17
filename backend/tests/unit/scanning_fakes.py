"""Shared test fakes for the scanning bounded context.

All fakes have been consolidated in ``tests/unit/use_cases/conftest.py``.
This module re-exports them for backward compatibility with test files
that haven't been moved into the ``use_cases/`` directory yet.
"""

from tests.unit.use_cases.conftest import (  # noqa: F401
    FakeScan as _ScanRecord,
    FakeScanRepository,
    FakeScanResultRepository,
    FakeUnitOfWork,
    FakeUniverseRepository,
    make_domain_item,
    setup_scan,
)

__all__ = [
    "_ScanRecord",
    "FakeScanRepository",
    "FakeScanResultRepository",
    "FakeUnitOfWork",
    "FakeUniverseRepository",
    "make_domain_item",
    "setup_scan",
]
