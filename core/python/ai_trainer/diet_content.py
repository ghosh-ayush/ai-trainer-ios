"""The diet policy: every number the diet engine uses, cited to research (AGENTS.md rule 1).

A diet bundle lives in ``diet_bundles/<id>/`` as ``manifest.json`` (``id``, ``version``,
``review``, ``evidenceBasis``, ``sources``, and for an approved bundle a ``verification``
record) plus ``content.json`` (``{"policy": {...}}``). Every leaf of the policy is a cited
value — ``{"value", "source", "locator", "certainty"}`` — or an owner decision —
``{"value", "source": "owner", "rationale"}`` — exactly as in a training bundle, and the
same gate applies (``content.source_problems``, ``content.citation_problems``): qualifying
peer-reviewed sources or official reports only, certainty above low only from syntheses,
nothing read from a preprint.

Selection: the newest ``approved`` bundle that passes the gate runs; a ``draft`` never
does. No person approves a bundle (ADR-014, ADR-016). With no runnable bundle the diet
engine withholds targets instead of guessing.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import content

JSON = dict[str, Any]

BUNDLES_DIR = Path(__file__).with_name("diet_bundles")
REVIEW_STATES = ("draft", "approved", "disabled")


def bundle_problems(manifest: JSON, body: JSON) -> list[str]:
    """Everything that stops a diet bundle from running; empty when it passes the gate."""
    problems: list[str] = []
    review = manifest.get("review")
    if review not in REVIEW_STATES:
        problems.append(f"manifest.review must be one of {REVIEW_STATES}")
    for key in ("id", "version", "evidenceBasis"):
        if not manifest.get(key):
            problems.append(f"manifest.{key} is required")
    if review == "approved":
        verification = manifest.get("verification") or {}
        for key in ("method", "verifiedOn"):
            if not verification.get(key):
                problems.append(f"manifest.verification.{key} is required for an approved bundle")
    if "policy" not in body:
        return [*problems, "content.policy is required"]
    sources: JSON = manifest.get("sources") or {}
    for key, source in sources.items():
        problems.extend(content.source_problems(source, f"manifest.sources.{key}"))
    problems.extend(content.citation_problems(body["policy"], "policy", sources))
    for path, value in cited_values(body["policy"]):
        if value["source"] != content.OWNER:
            design = (sources.get(value["source"]) or {}).get("design")
            problems.extend(content.certainty_problems(value.get("certainty"), design, path))
    return problems


def cited_values(policy: JSON, path: str = "policy") -> list[tuple[str, JSON]]:
    """Every cited value or owner decision in ``policy``, as ``(dotted.path, node)``."""
    found: list[tuple[str, JSON]] = []
    _collect(policy, path, found)
    return found


def read_bundle(directory: Path) -> tuple[JSON, JSON]:
    """The raw ``(manifest, content)`` of one diet bundle directory."""
    manifest: JSON = json.loads((directory / "manifest.json").read_text())
    body: JSON = json.loads((directory / "content.json").read_text())
    return manifest, body


def all_bundles() -> dict[str, tuple[JSON, JSON]]:
    """Every diet bundle shipped with the core, by id, raw."""
    if not BUNDLES_DIR.is_dir():
        return {}
    bundles: dict[str, tuple[JSON, JSON]] = {}
    for directory in sorted(path for path in BUNDLES_DIR.iterdir() if path.is_dir()):
        manifest, body = read_bundle(directory)
        bundles[manifest["id"]] = (manifest, body)
    return bundles


def active_policy() -> JSON | None:
    """The resolved policy of the newest approved diet bundle that passes the gate, or None."""
    loaded = _active()
    return None if loaded is None else loaded["policy"]


def active_sources() -> JSON:
    """The ``sources`` of the active bundle (empty when none runs)."""
    loaded = _active()
    return {} if loaded is None else loaded["sources"]


def active_citations() -> list[tuple[str, JSON]]:
    """Every cited value of the active bundle, for the "why these numbers" view."""
    loaded = _active()
    return [] if loaded is None else loaded["citations"]


@lru_cache(maxsize=1)
def _active() -> JSON | None:
    """Read once per process: the embedded interpreter lives as long as the app."""
    runnable = [
        (manifest, body)
        for manifest, body in all_bundles().values()
        if manifest.get("review") == "approved" and not bundle_problems(manifest, body)
    ]
    if not runnable:
        return None
    manifest, body = runnable[-1]
    policy = content.resolve(body["policy"])
    policy["version"] = manifest["version"]
    return {"policy": policy, "sources": manifest["sources"], "citations": cited_values(body["policy"])}


def _collect(node: Any, path: str, found: list[tuple[str, JSON]]) -> None:
    if isinstance(node, dict) and "value" in node and "source" in node:
        found.append((path, node))
    elif isinstance(node, dict):
        for key, item in node.items():
            _collect(item, f"{path}.{key}", found)
