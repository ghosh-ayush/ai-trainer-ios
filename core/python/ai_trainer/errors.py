"""Typed domain errors that cross the Swift boundary as ``{code, message}``.

Codes map one-to-one onto Swift ``TrainerError`` cases:
``invalid``, ``notFound``, ``conflict``, ``staleProposal``, ``unsupported``.
"""

from __future__ import annotations


class DomainError(Exception):
    """A rule or precondition failure. The host shows ``message`` to the user."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message or code)


def require(condition: bool, code: str = "conflict", message: str | None = None) -> None:
    """Raise ``DomainError(code, message)`` unless ``condition`` holds."""
    if not condition:
        raise DomainError(code, message)
