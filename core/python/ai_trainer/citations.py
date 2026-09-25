"""What a content bundle's values rest on, in words (ADR-014, ADR-023).

The rules run on plain values (``content.load_library``). This module reads the same bundle with
its citations kept (``content.active_bundle_raw``) to say where a number comes from: its source,
certainty and note, or, for a value the literature gives no number for, that it is the app's own
rule and which cited sources its rationale is built from. It never changes a value.
"""

from __future__ import annotations

import re
from typing import Any

JSON = dict[str, Any]

# Source keys as the bundles write them (ACSM26, SCHOENFELD17V): capitals, then two digits.
SOURCE_KEY = re.compile(r"\b[A-Z][A-Z]+\d{2}[A-Z]*\b")


class Citations:
    """The citations of one bundle, given as its raw ``(manifest, content)``."""

    def __init__(self, bundle: tuple[JSON, JSON]) -> None:
        self.manifest, self.raw = bundle
        self.sources: JSON = self.manifest.get("sources", {})

    def cited(self, *path: str) -> JSON | None:
        """The cited value at ``path`` in the raw bundle, or ``None`` when it is absent or uncited."""
        node: Any = self.raw
        for key in path:
            if not isinstance(node, dict) or key not in node:
                return None
            node = node[key]
        if isinstance(node, dict) and "value" in node and "source" in node:
            return node
        return None

    def basis(self, node: JSON | None) -> tuple[str, list[str]]:
        """How a cited value is backed, as a sentence, and the source keys it names."""
        if node is None:
            return "This content cites nothing for it.", []
        if node["source"] == "owner":
            rationale = str(node.get("rationale", ""))
            sentence = f"No study gives this exact number, so it is the app's own rule. {rationale}"
            return sentence, self.keys_in(rationale)
        sentence = f"From {self.short_citation(node['source'])}"
        if node.get("certainty"):
            sentence += f" ({node['certainty']} certainty)"
        sentence += "."
        note = str(node.get("note", ""))
        if note:
            sentence += f" {note}"
        return sentence, [node["source"], *(key for key in self.keys_in(note) if key != node["source"])]

    def brief_basis(self, node: JSON | None) -> tuple[str, list[str]]:
        """``basis`` in a few words: the source and certainty, or "the app's own rule"."""
        if node is None:
            return "no citation", []
        if node["source"] == "owner":
            return "the app's own rule, built from cited research", self.keys_in(str(node.get("rationale", "")))
        certainty = f", {node['certainty']} certainty" if node.get("certainty") else ""
        return f"{self.short_citation(node['source'])}{certainty}", [node["source"]]

    def keys_in(self, text: str) -> list[str]:
        """The bundle's source keys named in ``text``, once each, in order."""
        found: list[str] = []
        for key in SOURCE_KEY.findall(text):
            if key in self.sources and key not in found:
                found.append(key)
        return found

    def short_citation(self, key: str) -> str:
        """ "Baz-Valle et al. 2022" or "American College of Sports Medicine 2009" from the citation."""
        source = self.sources.get(key)
        if source is None:
            return key
        citation = str(source["citation"])
        authors = citation.split(". ")[0]
        first = authors.split(",")[0].strip()
        if "," in authors:
            first = first.split(" ")[0] + " et al."
        year = re.search(r"\b(?:19|20)\d{2}\b", citation)
        return f"{first} {year.group(0)}" if year else first

    def entries(self, keys: list[str]) -> list[JSON]:
        """``{key, citation, doi?, pmid?}`` for each key the bundle lists, in order (``ChatSource``)."""
        found: list[JSON] = []
        for key in keys:
            source = self.sources.get(key)
            if source is None:
                continue
            entry: JSON = {"key": key, "citation": source["citation"]}
            for identifier in ("doi", "pmid"):
                if source.get(identifier):
                    entry[identifier] = str(source[identifier])
            found.append(entry)
        return found
