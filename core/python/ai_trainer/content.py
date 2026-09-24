"""Content bundles and their gating: which exercises and policies may drive guidance.

Training content ships as data, one directory per bundle under ``bundles/``:

- ``manifest.json`` — ``id``, ``version``, ``review`` (``fixture`` · ``draft`` ·
  ``approved`` · ``disabled``), ``evidenceBasis``, the ``sources`` it cites and, once
  approved, a ``verification`` record (how and when its sources were checked — ADR-014).
- ``content.json`` — ``exercises``, the progression ``policy`` and the program ``template``.

In every bundle except a fixture, each policy and template parameter is a *cited
value* — ``{"value", "source", "locator", "certainty"}`` — or an explicit owner
decision — ``{"value", "source": "owner", "rationale"}``. Each exercise names the
sources behind its inclusion. :func:`bundle_problems` enforces this; the rules only
ever see the resolved plain values.

Every source a non-fixture bundle cites must qualify (AGENTS.md rule 1): a peer-reviewed
publication with a DOI or PMID, a ``design`` from :data:`QUALIFYING_DESIGNS`, and an honest
``fullTextRead`` flag. Videos, blogs, influencers and other internet content never qualify.

Selection: ``approved`` means the bundle passed this automated gate — no person signs it. An
approved bundle that :func:`bundle_problems` accepts always runs. Without one, the fixture
runs, and the existing gates allow it only when the host permits fixtures (Debug). A
``draft`` bundle (research still in progress) never runs.
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

JSON = dict[str, Any]

BUNDLES_DIR = Path(__file__).with_name("bundles")
REVIEW_STATES = ("fixture", "draft", "approved", "disabled")
CERTAINTY_GRADES = ("high", "moderate", "low")
OWNER = "owner"

# Peer-reviewed study designs, and official reference reports (DRI, FAO/WHO), a bundle
# may cite. Anything else (video, blog, website, preprint, book, app, animal or cadaver
# study, opinion column) is refused, however popular.
QUALIFYING_DESIGNS = (
    "positionStand",
    "officialGuideline",
    "umbrellaReview",
    "metaAnalysis",
    "systematicReview",
    "randomisedTrial",
    "crossoverTrial",
    "nonRandomisedTrial",
    "cohortStudy",
    "crossSectionalStudy",
    "narrativeReview",
)

# Only a synthesis or an official reference can support more than low certainty: one
# trial, one acute study or a narrative review is low by definition (research rubric).
SYNTHESIS_DESIGNS = frozenset(
    {"positionStand", "officialGuideline", "umbrellaReview", "metaAnalysis", "systematicReview"}
)
FIXTURE_BUNDLE_ID = "fixture-1"

# Tests and the simulator smoke run pin the fixture with this variable, so rule tests do not
# change whenever research updates the shipped content. Pinning never bypasses a gate: only a
# fixture (still Debug-only) or an approved bundle that passes the gate can be pinned.
PINNED_BUNDLE_ENV = "AI_TRAINER_CONTENT_BUNDLE"

# Keys that identify or label a record rather than prescribe training; they need no citation.
_IDENTIFIERS = frozenset({"id", "name", "version", "review", "exerciseID", "equipmentKind", "protocolID"})


def load_library(permits_fixtures: bool) -> JSON:
    """The library the rules run against: exercises, policy, template and the fixture flag."""
    bundle = _active_bundle()
    return {
        "exercises": bundle["exercises"],
        "policy": bundle["policy"],
        "template": bundle["template"],
        "permitsFixtures": permits_fixtures,
    }


def public_library(library: JSON) -> JSON:
    """The ``Library`` record the host displays (names, alternatives, policy version)."""
    return {key: library[key] for key in ("exercises", "policy", "permitsFixtures")}


def is_enabled(review_status: str, library: JSON) -> bool:
    if review_status == "approved":
        return True
    return review_status == "fixture" and bool(library["permitsFixtures"])


def policy_is_enabled(library: JSON) -> bool:
    return is_enabled(library["policy"]["review"], library)


def exercises_by_id(library: JSON) -> dict[str, JSON]:
    return {exercise["id"]: exercise for exercise in library["exercises"]}


# --- bundles ---------------------------------------------------------------------------------


def read_bundle(directory: Path) -> tuple[JSON, JSON]:
    """The raw ``(manifest, content)`` of one bundle directory, exactly as written."""
    manifest: JSON = json.loads((directory / "manifest.json").read_text())
    content: JSON = json.loads((directory / "content.json").read_text())
    return manifest, content


def bundle_problems(manifest: JSON, content: JSON) -> list[str]:
    """Everything that stops a bundle from being loaded; empty when it is well formed."""
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
    for section in ("exercises", "policy", "template"):
        if section not in content:
            problems.append(f"content.{section} is required")
    if problems or review == "fixture":
        return problems  # fixtures are test data: no citations to check
    sources = manifest.get("sources") or {}
    for key, source in sources.items():
        problems.extend(source_problems(source, f"manifest.sources.{key}"))
    if resolve(content["policy"]).get("review") != review:
        problems.append(f"policy.review must match the manifest ({review})")
    for section in ("policy", "template"):
        problems.extend(_citation_problems(content[section], section, sources))
    for path, value in cited_parameters(content):
        source = sources.get(value["source"]) or {}
        if value["source"] != OWNER:
            problems.extend(certainty_problems(value.get("certainty"), source.get("design"), path))
    for exercise in content["exercises"]:
        if exercise.get("review") != review:
            problems.append(f"exercise {exercise.get('id')}: review must match the manifest ({review})")
        citations = exercise.get("sources") or []
        if not citations:
            problems.append(f"exercise {exercise.get('id')}: name at least one source for its inclusion")
        for citation in citations:
            label = f"exercise {exercise.get('id')}"
            if citation.get("source") not in sources:
                problems.append(f"{label}: unknown source {citation.get('source')!r}")
            if not citation.get("locator"):
                problems.append(f"{label}: say where in the source (section, table or page)")
            problems.extend(locator_problems(citation.get("locator"), label))
    return problems


def source_problems(source: JSON, path: str) -> list[str]:
    """Why ``source`` is not a qualifying, well-cited research source; empty when it is."""
    problems: list[str] = []
    if not source.get("citation"):
        problems.append(f"{path}.citation is required")
    doi, pmid, isbn = str(source.get("doi") or ""), str(source.get("pmid") or ""), str(source.get("isbn") or "")
    identified = bool(doi or pmid)
    if source.get("design") == "officialGuideline":
        identified = identified or bool(isbn)  # FAO/WHO reports carry an ISBN, not a DOI
    if not identified:
        problems.append(f"{path} needs a doi or a pmid: only published, peer-reviewed research counts")
    if doi and not _DOI.match(doi):
        problems.append(f"{path}.doi is not a DOI (10.<registrant>/<suffix>)")
    if pmid and not pmid.isdigit():
        problems.append(f"{path}.pmid must be a PubMed number")
    if isbn and not _ISBN.match(isbn):
        problems.append(f"{path}.isbn is not an ISBN")
    text = f"{doi} {source.get('citation', '')}".lower()
    if any(marker in text for marker in _PREPRINT_MARKERS):
        problems.append(f"{path} is a preprint: cite the peer-reviewed paper")
    if source.get("design") not in QUALIFYING_DESIGNS:
        problems.append(f"{path}.design must be one of {QUALIFYING_DESIGNS}")
    if not isinstance(source.get("fullTextRead"), bool):
        problems.append(f"{path}.fullTextRead must say whether the full text was read")
    return problems


_PREPRINT_MARKERS = ("preprint", "sportrxiv", "biorxiv", "medrxiv", "10.51224/", "10.1101/", "arxiv", "ssrn", "osf.io")
_DOI = re.compile(r"^10\.\d{4,9}/\S+$")
_ISBN = re.compile(r"^(97[89][- ]?)?\d{1,5}[- ]?\d{1,7}[- ]?\d{1,7}[- ]?[\dXx]$")


def locator_problems(locator: object, path: str) -> list[str]:
    """Why ``locator`` points at text a qualifying source did not publish; empty when it does not.

    A finding read from a preprint of a later peer-reviewed paper is still a preprint
    reading: its numbers may differ from what was published (AGENTS.md rule 1).
    """
    text = str(locator or "").lower()
    if any(marker in text for marker in _PREPRINT_MARKERS):
        return [f"{path}: cite what the peer-reviewed paper published, not a preprint of it"]
    return []


def certainty_problems(certainty: object, design: object, path: str) -> list[str]:
    """Why ``certainty`` is graded higher than a source of ``design`` can support; empty when it is not."""
    if certainty in ("high", "moderate") and design not in SYNTHESIS_DESIGNS:
        return [f"{path}: a {design} supports at most low certainty"]
    return []


def citation_problems(node: Any, path: str, sources: JSON) -> list[str]:
    """Every value under ``node`` that is neither cited nor an explained owner decision."""
    return _citation_problems(node, path, sources)


def cited_parameters(content: JSON) -> list[tuple[str, JSON]]:
    """Every cited value in a bundle's policy and template, as ``(dotted.path, cited value)``."""
    found: list[tuple[str, JSON]] = []
    for section in ("policy", "template"):
        _collect(content[section], section, found)
    return found


def resolve(node: Any) -> Any:
    """Replace every cited value with its plain ``value``, leaving everything else as it is."""
    if isinstance(node, dict):
        if _is_cited(node):
            return resolve(node["value"])
        return {key: resolve(item) for key, item in node.items()}
    if isinstance(node, list):
        return [resolve(item) for item in node]
    return node


def all_bundles() -> dict[str, tuple[JSON, JSON]]:
    """Every bundle shipped with the core, by id, raw."""
    bundles: dict[str, tuple[JSON, JSON]] = {}
    for directory in sorted(path for path in BUNDLES_DIR.iterdir() if path.is_dir()):
        manifest, content = read_bundle(directory)
        bundles[manifest["id"]] = (manifest, content)
    return bundles


@lru_cache(maxsize=1)
def _active_bundle() -> JSON:
    """The approved bundle if one passes the gate, otherwise the fixture. Never a draft.

    Read once per process: the embedded interpreter lives as long as the app.
    """
    bundles = all_bundles()
    pinned = os.environ.get(PINNED_BUNDLE_ENV)
    if pinned:
        return _resolved(_pinned_bundle(bundles, pinned))
    approved = [
        (manifest, content)
        for manifest, content in bundles.values()
        if manifest.get("review") == "approved" and not bundle_problems(manifest, content)
    ]
    _, body = approved[-1] if approved else bundles[FIXTURE_BUNDLE_ID]
    return _resolved(body)


def _pinned_bundle(bundles: dict[str, tuple[JSON, JSON]], bundle_id: str) -> JSON:
    """The content of the bundle named by ``PINNED_BUNDLE_ENV``; refuses anything the gate would not run."""
    if bundle_id not in bundles:
        raise ValueError(f"{PINNED_BUNDLE_ENV} names no bundle: {bundle_id!r}")
    manifest, body = bundles[bundle_id]
    if manifest.get("review") not in ("fixture", "approved") or bundle_problems(manifest, body):
        raise ValueError(f"{PINNED_BUNDLE_ENV} may name only the fixture or an approved bundle that passes the gate")
    return body


def _resolved(body: JSON) -> JSON:
    """A bundle's content with plain values, in the shape the rules run against."""
    resolved: JSON = resolve(body)
    # Citations are for review; the contract's Exercise record carries no ``sources``.
    resolved["exercises"] = [
        {key: value for key, value in exercise.items() if key != "sources"} for exercise in resolved["exercises"]
    ]
    return resolved


def _is_cited(node: JSON) -> bool:
    return "value" in node and "source" in node


def _citation_problems(node: Any, path: str, sources: JSON) -> list[str]:
    if isinstance(node, dict) and _is_cited(node):
        return _cited_value_problems(node, path, sources)
    if isinstance(node, dict):
        problems: list[str] = []
        for key, item in node.items():
            if key not in _IDENTIFIERS:
                problems.extend(_citation_problems(item, f"{path}.{key}", sources))
        return problems
    return [f"{path} needs a source: write it as a cited value or an owner decision"]


def _cited_value_problems(node: JSON, path: str, sources: JSON) -> list[str]:
    if node["source"] == OWNER:
        return [] if node.get("rationale") else [f"{path}: an owner decision needs a rationale"]
    problems = []
    if node["source"] not in sources:
        problems.append(f"{path}: unknown source {node['source']!r}")
    if not node.get("locator"):
        problems.append(f"{path}: say where in the source (section, table or page)")
    problems.extend(locator_problems(node.get("locator"), path))
    if node.get("certainty") not in CERTAINTY_GRADES:
        problems.append(f"{path}: certainty must be one of {CERTAINTY_GRADES}")
    return problems


def _collect(node: Any, path: str, found: list[tuple[str, JSON]]) -> None:
    if isinstance(node, dict) and _is_cited(node):
        found.append((path, node))
    elif isinstance(node, dict):
        for key, item in node.items():
            _collect(item, f"{path}.{key}", found)
