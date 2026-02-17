"""Boundary test: feature store domain modules must not import infrastructure.

Regex-scans models.py, quality.py, and publish_policy.py to ensure
no SQLAlchemy, FastAPI, Pydantic, Redis, or Celery imports leak in.
Also verifies each module defines an __all__ export list.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Root of the feature_store domain package
_PKG_DIR = (
    Path(__file__).resolve().parents[3]
    / "app"
    / "domain"
    / "feature_store"
)

_DOMAIN_MODULES = ["models.py", "quality.py", "publish_policy.py"]

FORBIDDEN_IMPORTS = re.compile(
    r"^\s*(from|import)\s+(sqlalchemy|fastapi|pydantic|redis|celery)\b",
    re.MULTILINE,
)


class TestNoIOLeakage:
    """Domain modules must be free of infrastructure imports."""

    @pytest.mark.parametrize("filename", _DOMAIN_MODULES)
    def test_no_forbidden_imports(self, filename: str):
        source = (_PKG_DIR / filename).read_text()
        matches = FORBIDDEN_IMPORTS.findall(source)
        assert not matches, (
            f"{filename} contains forbidden imports: {matches}"
        )

    @pytest.mark.parametrize("filename", _DOMAIN_MODULES)
    def test_has_all_export(self, filename: str):
        source = (_PKG_DIR / filename).read_text()
        assert "__all__" in source, f"{filename} is missing __all__"
