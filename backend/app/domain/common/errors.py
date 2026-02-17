"""Domain-level error hierarchy.

All domain exceptions inherit from DomainError so that interface layers
can catch a single base class and translate to HTTP/Celery-appropriate
responses without leaking domain internals.
"""


class DomainError(Exception):
    """Base class for all domain errors."""


class ValidationError(DomainError):
    """A domain invariant or input constraint was violated."""


class EntityNotFoundError(DomainError):
    """A requested entity does not exist."""

    def __init__(self, entity: str, identifier: object) -> None:
        self.entity = entity
        self.identifier = identifier
        super().__init__(f"{entity} not found: {identifier}")


class DataFetchError(DomainError):
    """One or more data components failed to fetch and allow_partial=False."""

    def __init__(
        self, symbol: str, errors: dict[str, str], partial_data: object = None
    ) -> None:
        self.symbol = symbol
        self.errors = errors
        self.partial_data = partial_data
        summary = "; ".join(f"{k}: {v}" for k, v in errors.items())
        super().__init__(f"Data fetch failed for {symbol}: {summary}")


class InvalidTransitionError(DomainError):
    """An illegal state transition was attempted."""

    def __init__(self, current: object, target: object) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Invalid transition: {current} -> {target}")
