"""Research annotations for the descriptive exercise catalog.

The catalog (``apps/ios/Sources/AITrainerCore/Resources/exercises.json``) is the
free-exercise-db snapshot. Its upstream fields stay exactly as imported. This module adds
one optional field per record, ``evidence``: what primary research says about that
exercise for a muscle and a use case, each entry cited to a paper with a locator and a
certainty grade.

The evidence lives in ``docs/research/exercise-evidence.json`` (the reviewed source of
truth) and is copied into the catalog by ``scripts/annotate_catalog.py``. Records the
research does not cover get no ``evidence`` key: unknown stays unknown.

Every source must qualify under AGENTS.md rule 1 (``content.source_problems``). The
annotations may inform exercise selection and substitution (rule 4, ADR-014); they never
drive load progression, which reads only logged sets, and the catalog's upstream
descriptions never inform guidance at all.
"""

from __future__ import annotations

from typing import Any

from .content import certainty_problems, locator_problems, source_problems

JSON = dict[str, Any]

# The catalog's own muscle vocabulary (free-exercise-db ``primaryMuscles``).
MUSCLES = (
    "abdominals",
    "abductors",
    "adductors",
    "biceps",
    "calves",
    "chest",
    "forearms",
    "glutes",
    "hamstrings",
    "lats",
    "lower back",
    "middle back",
    "neck",
    "quadriceps",
    "shoulders",
    "traps",
    "triceps",
)

# What a finding measured. ``muscleActivation`` is surface EMG amplitude, which is not
# evidence of growth or strength; the others are trained outcomes.
OUTCOMES = (
    "muscleActivation",
    "hypertrophy",
    "strength",
    "localEndurance",
    "power",
    "agility",
    "posture",
    "cardiorespiratory",
)

# EMG is always recorded from a named muscle; every other outcome may be whole-body
# (a volume or load finding about muscle growth in general, a VO2max finding).
MUSCLE_SPECIFIC_OUTCOMES = frozenset({"muscleActivation"})

# How one exercise fared in a finding.
RESULTS = ("favoured", "lessFavoured", "noDifference", "studied")

CERTAINTY_GRADES = ("high", "moderate", "low")

# A paraphrase, not a copy of the abstract.
MAXIMUM_FINDING_WORDS = 60

UPSTREAM_KEYS = frozenset(
    {
        "id",
        "name",
        "force",
        "level",
        "mechanic",
        "equipment",
        "primaryMuscles",
        "secondaryMuscles",
        "instructions",
        "category",
        "images",
    }
)


def evidence_problems(evidence: JSON, catalog: list[JSON]) -> list[str]:
    """Everything wrong with the evidence file; empty when it can annotate ``catalog``."""
    problems: list[str] = []
    catalog_ids = {record["id"] for record in catalog}
    sources: JSON = evidence.get("sources") or {}
    for key, source in sources.items():
        problems.extend(source_problems(source, f"sources.{key}"))
    seen_ids: set[str] = set()
    for finding in evidence.get("findings") or []:
        finding_id = finding.get("id")
        label = f"finding {finding_id}"
        if not finding_id or finding_id in seen_ids:
            problems.append(f"{label}: needs a unique id")
        seen_ids.add(finding_id)
        source = sources.get(finding.get("source"))
        if source is None:
            problems.append(f"{label}: unknown source {finding.get('source')!r}")
        else:
            problems.extend(certainty_problems(finding.get("certainty"), source.get("design"), label))
        if not isinstance(finding.get("fullTextRead"), bool):
            problems.append(f"{label}: fullTextRead must say whether this finding was read in the full text")
        if finding.get("outcome") not in OUTCOMES:
            problems.append(f"{label}: outcome must be one of {OUTCOMES}")
        muscles = finding.get("muscles") or []
        if not muscles and finding.get("outcome") in MUSCLE_SPECIFIC_OUTCOMES:
            problems.append(f"{label}: name at least one muscle")
        for muscle in muscles:
            if muscle not in MUSCLES:
                problems.append(f"{label}: unknown muscle {muscle!r}")
        if finding.get("certainty") not in CERTAINTY_GRADES:
            problems.append(f"{label}: certainty must be one of {CERTAINTY_GRADES}")
        if not finding.get("locator"):
            problems.append(f"{label}: say where in the source (section, table or figure)")
        problems.extend(locator_problems(finding.get("locator"), label))
        text = finding.get("finding") or ""
        if not text:
            problems.append(f"{label}: the finding needs a paraphrase")
        elif len(text.split()) > MAXIMUM_FINDING_WORDS:
            problems.append(f"{label}: paraphrase in at most {MAXIMUM_FINDING_WORDS} words")
        exercises = finding.get("exercises") or []
        if not exercises:
            problems.append(f"{label}: name the exercises it compared")
        for exercise in exercises:
            if not exercise.get("name"):
                problems.append(f"{label}: every exercise needs the name the paper used")
            if exercise.get("result") not in RESULTS:
                problems.append(f"{label}: result must be one of {RESULTS}")
            for catalog_id in exercise.get("catalogIDs") or []:
                if catalog_id not in catalog_ids:
                    problems.append(f"{label}: unknown catalog id {catalog_id!r}")
    return problems


def annotate(catalog: list[JSON], evidence: JSON) -> list[JSON]:
    """``catalog`` with each record's ``evidence`` rebuilt from ``evidence``; upstream fields untouched.

    Idempotent: any existing annotation is replaced, and a record with no finding has no
    ``evidence`` key at all.
    """
    entries_by_id: dict[str, list[JSON]] = {}
    sources: JSON = evidence["sources"]
    for finding in evidence["findings"]:
        source = sources[finding["source"]]
        for catalog_id, result in _results_by_catalog_id(finding).items():
            entries_by_id.setdefault(catalog_id, []).append(_entry(finding, result, source))
    annotated: list[JSON] = []
    for record in catalog:
        upstream = {key: value for key, value in record.items() if key in UPSTREAM_KEYS}
        entries = entries_by_id.get(record["id"])
        if entries:
            upstream["evidence"] = entries
        annotated.append(upstream)
    return annotated


def summary(evidence: JSON, catalog: list[JSON]) -> str:
    """A readable Markdown overview of ``evidence``: method, coverage, strongest findings, open questions."""
    sources: JSON = evidence["sources"]
    findings: list[JSON] = evidence["findings"]
    names = {record["id"]: record["name"] for record in catalog}
    annotated = {catalog_id for finding in findings for catalog_id in _results_by_catalog_id(finding)}
    lines = [
        "# Exercise evidence — summary",
        "",
        "Generated by `scripts/annotate_catalog.py` from `docs/research/exercise-evidence.json`; do not edit by hand.",
        "",
        f"- **Version:** `{evidence.get('version', '')}` · retrieved {evidence.get('retrievedOn', '')}",
        f"- **Sources:** {len(sources)} · **findings:** {len(findings)} · "
        f"**catalog exercises annotated:** {len(annotated)} of {len(catalog)}",
        "",
        "## Method",
        "",
        evidence.get("method", ""),
        "",
        "## Read these findings with care",
        "",
    ]
    lines += [f"- {caveat}" for caveat in evidence.get("caveats", [])]
    lines += ["", "## Coverage (findings per muscle and outcome)", ""]
    lines += ["| Muscle | " + " | ".join(OUTCOMES) + " |", "|---|" + "---|" * len(OUTCOMES)]
    for muscle in MUSCLES:
        counts = [
            sum(1 for f in findings if f["outcome"] == outcome and muscle in (f.get("muscles") or []))
            for outcome in OUTCOMES
        ]
        lines.append(f"| {muscle} | " + " | ".join(str(count) if count else "·" for count in counts) + " |")
    whole_body = [sum(1 for f in findings if f["outcome"] == outcome and not f.get("muscles")) for outcome in OUTCOMES]
    lines.append("| *(whole body)* | " + " | ".join(str(count) if count else "·" for count in whole_body) + " |")
    lines += ["", "## Strongest findings (certainty above low)", ""]
    strongest = [f for f in findings if f["certainty"] != "low"]
    if not strongest:
        lines.append("None: every finding is low certainty.")
    for finding in strongest:
        source = sources[finding["source"]]
        exercises = (
            ", ".join(names.get(catalog_id, catalog_id) for catalog_id in _results_by_catalog_id(finding))
            or "no catalog match"
        )
        lines.append(
            f"- **{finding['outcome']}** ({', '.join(finding.get('muscles') or []) or 'whole body'}; "
            f"{finding['certainty']}, "
            f"{source['design']}) — {finding['finding']} *{source['citation']}* {finding['locator']}. "
            f"Catalog: {exercises}."
        )
    questions = evidence.get("openQuestions") or {}
    lines += ["", "## Gaps", ""]
    lines += [f"- **{gap['area']}** — {gap['problem']}" for gap in questions.get("gaps", [])] or ["None recorded."]
    lines += ["", "## Contradictions between studies", ""]
    lines += [f"- {item}" for item in questions.get("contradictions", [])] or ["None recorded."]
    lines += ["", "## Sources", ""]
    for key, source in sources.items():
        ids = " ".join(f"{name}:{source[name]}" for name in ("doi", "pmid") if source.get(name))
        read = "full text" if source["fullTextRead"] else "abstract only"
        lines.append(f"- `{key}` — {source['citation']} {ids} ({source['design']}; {read})")
    return "\n".join(lines) + "\n"


def _results_by_catalog_id(finding: JSON) -> dict[str, str]:
    """How each catalog exercise fared in ``finding``, in first-mention order.

    Two variants the paper compared can map to one catalog record (two bench angles, one
    catalog bench). When they fared differently the catalog record was simply ``studied``.
    """
    results: dict[str, str] = {}
    for exercise in finding["exercises"]:
        for catalog_id in exercise.get("catalogIDs") or []:
            previous = results.get(catalog_id)
            results[catalog_id] = exercise["result"] if previous in (None, exercise["result"]) else "studied"
    return results


def _entry(finding: JSON, result: str, source: JSON) -> JSON:
    """One catalog ``evidence`` entry: the finding as it applies to one exercise, with its citation."""
    entry: JSON = {
        "findingID": finding["id"],
        "outcome": finding["outcome"],
        "muscles": list(finding.get("muscles") or []),
        "result": result,
        "finding": finding["finding"],
        "certainty": finding["certainty"],
        "design": source["design"],
        "citation": source["citation"],
        "locator": finding["locator"],
        "fullTextRead": finding["fullTextRead"],
    }
    for key in ("doi", "pmid"):
        if source.get(key):
            entry[key] = source[key]
    return entry
