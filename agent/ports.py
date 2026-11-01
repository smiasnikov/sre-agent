"""External source boundary; the investigation owns no provider or filesystem setup."""

from typing import Protocol
from .constants import ErrorCode
from .schemas import Incident, Scope, SourceRequest


class SourceTransport(Protocol):
    def call(self, request: SourceRequest) -> object: ...


class IncidentStore(Protocol):
    def create(self, incident: Incident) -> None: ...

    def save(self, incident: Incident, expected_revision: int) -> None: ...

    def load(self, incident_id: str, scope: Scope) -> Incident: ...


class RevisionConflict(ValueError):
    def __init__(self, expected_revision: int, current: Incident) -> None:
        super().__init__(ErrorCode.REVISION_CONFLICT.value)
        self.expected_revision = expected_revision
        self.current = current
