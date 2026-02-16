"""Unit of Work port — defines transactional boundary for use cases.

The UoW is a domain concept: "these operations must succeed or fail
together."  The concrete implementation (SQLAlchemy session) lives in
infra/db/uow.py.
"""

from __future__ import annotations

import abc
from typing import Self


class UnitOfWork(abc.ABC):
    """Abstract transactional boundary.

    Usage in a use case::

        with uow:
            uow.scans.create(scan_id=..., ...)
            uow.commit()
        # auto-rollback on unhandled exception
    """

    @abc.abstractmethod
    def __enter__(self) -> Self:
        ...

    @abc.abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        ...

    @abc.abstractmethod
    def commit(self) -> None:
        ...

    @abc.abstractmethod
    def rollback(self) -> None:
        ...
