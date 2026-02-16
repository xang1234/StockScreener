"""Enforce import boundary rules for the layered architecture.

Layer rules:
  domain/       → may import ONLY stdlib + domain/
  use_cases/    → may import ONLY stdlib + domain/ (NOT infra/, interfaces/, services/, etc.)

These rules prevent the inner layers from depending on outer/infrastructure
concerns, which is the core invariant of hexagonal architecture.
"""

import ast
import sys
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────

APP_ROOT = Path(__file__).resolve().parents[2] / "app"
DOMAIN_DIR = APP_ROOT / "domain"
USE_CASES_DIR = APP_ROOT / "use_cases"

# ── Stdlib detection ─────────────────────────────────────────────────────

_STDLIB_MODULES: set[str] = set(sys.stdlib_module_names)


def _is_stdlib_or_builtin(top_level: str) -> bool:
    return top_level in _STDLIB_MODULES


# ── AST helpers ──────────────────────────────────────────────────────────


def _collect_imports(filepath: Path) -> list[tuple[int, str, str]]:
    """Return (line_number, top_level_module, full_module) for every import."""
    source = filepath.read_text()
    tree = ast.parse(source, filename=str(filepath))
    imports: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                full = alias.name
                imports.append((node.lineno, full.split(".")[0], full))
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None and node.level == 0:
                full = node.module
                imports.append((node.lineno, full.split(".")[0], full))
    return imports


def _python_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.rglob("*.py"))


# ── Rule checkers ────────────────────────────────────────────────────────

def _check_domain_boundaries() -> list[str]:
    """domain/ may only import stdlib and app.domain.*"""
    violations: list[str] = []
    for py_file in _python_files(DOMAIN_DIR):
        rel = py_file.relative_to(APP_ROOT.parent)
        for lineno, top, full in _collect_imports(py_file):
            if _is_stdlib_or_builtin(top):
                continue
            if top == "app" and full.startswith("app.domain"):
                continue
            violations.append(
                f"  {rel}:{lineno} imports '{full}' "
                f"(domain may only import stdlib and app.domain.*)"
            )
    return violations


_USE_CASE_ALLOWED_PREFIXES = ("app.domain", "app.use_cases")


def _check_use_case_boundaries() -> list[str]:
    """use_cases/ may only import stdlib, app.domain.*, and app.use_cases.*"""
    violations: list[str] = []
    for py_file in _python_files(USE_CASES_DIR):
        rel = py_file.relative_to(APP_ROOT.parent)
        for lineno, top, full in _collect_imports(py_file):
            if _is_stdlib_or_builtin(top):
                continue
            if top == "app" and any(
                full.startswith(p) for p in _USE_CASE_ALLOWED_PREFIXES
            ):
                continue
            violations.append(
                f"  {rel}:{lineno} imports '{full}' "
                f"(use_cases may only import stdlib, app.domain.*, or app.use_cases.*)"
            )
    return violations


# ── Tests ────────────────────────────────────────────────────────────────


class TestLayerBoundaries:
    """Import boundary enforcement — fails CI if layers are violated."""

    def test_domain_imports_only_stdlib_and_domain(self):
        violations = _check_domain_boundaries()
        assert not violations, (
            "Domain layer boundary violations found:\n" + "\n".join(violations)
        )

    def test_use_cases_imports_only_stdlib_and_domain(self):
        violations = _check_use_case_boundaries()
        assert not violations, (
            "Use-case layer boundary violations found:\n" + "\n".join(violations)
        )

    def test_domain_packages_are_importable(self):
        import app.domain
        import app.domain.common
        import app.domain.common.errors
        import app.domain.common.types
        import app.domain.scanning
        import app.domain.feature_store

    def test_use_case_packages_are_importable(self):
        import app.use_cases
        import app.use_cases.scanning
        import app.use_cases.feature_store

    def test_infra_packages_are_importable(self):
        import app.infra
        import app.infra.db
        import app.infra.db.repositories
        import app.infra.cache
        import app.infra.providers
        import app.infra.query

    def test_interface_packages_are_importable(self):
        import app.interfaces
        import app.interfaces.api
        import app.interfaces.tasks

    def test_wiring_package_is_importable(self):
        import app.wiring
