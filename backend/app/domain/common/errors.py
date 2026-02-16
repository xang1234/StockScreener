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
