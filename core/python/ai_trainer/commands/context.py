"""Shared plumbing for command handlers."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ..athlete_state import active_session
from ..errors import DomainError
from ..events import expire_proposals, record_event

JSON = dict[str, Any]


class CommandContext:
    """Everything a handler may touch. ``state`` is already a private copy.

    A plain class on purpose: ``dataclasses`` imports ``inspect`` → ``dis`` → ``_opcode``,
    an extension module the embedded iOS runtime does not ship (see tests/test_embedded_imports.py).
    """

    __slots__ = ("arguments", "ids", "library", "now", "state")

    def __init__(self, state: JSON, arguments: JSON, library: JSON, now: float, ids: Iterator[str]) -> None:
        self.state = state
        self.arguments = arguments
        self.library = library
        self.now = now
        self.ids = ids

    def next_id(self) -> str:
        """The next host-supplied UUID. Exhausting the budget is a contract error."""
        try:
            return next(self.ids)
        except StopIteration as exhausted:
            raise DomainError("invalid", "Invalid contract payload.") from exhausted

    def record(self, name: str, reason: str | None = None, occurred_at: float | None = None) -> None:
        record_event(self.state, name, self.now if occurred_at is None else occurred_at, self.next_id(), reason)

    def expire_proposals(self) -> None:
        expire_proposals(self.state)

    def mark_context_changed(self) -> None:
        """Anything that changes what a proposal was computed against."""
        self.state["contextRevision"] += 1
        self.expire_proposals()

    def active_session_or_raise(self) -> JSON:
        session = active_session(self.state)
        if session is None:
            raise DomainError("notFound")
        return session

    def session_by_id(self, session_id: str) -> JSON | None:
        return next((session for session in self.state["sessions"] if session["id"] == session_id), None)
