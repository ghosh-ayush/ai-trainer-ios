"""Compatibility alias. The C bridge imports ``ai_trainer.service.dispatch_json``.

New code should import from :mod:`ai_trainer.api`.
"""

from .api import VERSION, dispatch, dispatch_json

__all__ = ["VERSION", "dispatch", "dispatch_json"]
