"""Optional LLM proposer behind a verbatim gate (Dependency Inversion).

The model may only *suggest* phrases. ``VerbatimSpanGate`` is the authority:
a proposal is kept only when that exact phrase already appears in the notes.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from archdiag.catalog import ALLOWED_KINDS, ALLOWED_ZONES
from archdiag.components import drop_generic_database
from archdiag.models import CatalogHit, TraceLog
from archdiag.ports import ProposedComponent, SpanProposer
from archdiag.schema import EvidenceSpan
from archdiag.textutil import slug

MIN_PHRASE = 3
MAX_PHRASE = 80


class NullProposer:
    provider_name = "off"

    def propose(self, notes: str, sentences: list[str]) -> list[ProposedComponent]:
        return []


class StaticProposer:
    """Test double: returns a fixed list of proposals."""

    provider_name = "static"

    def __init__(self, proposals: list[ProposedComponent]) -> None:
        self._proposals = proposals

    def propose(self, notes: str, sentences: list[str]) -> list[ProposedComponent]:
        return list(self._proposals)


class VerbatimSpanGate:
    """Rejects any LLM (or fake) phrase that is not a contiguous quote from the notes."""

    def locate(self, phrase: str, notes: str) -> str | None:
        needle = " ".join(phrase.split()).strip()
        if len(needle) < MIN_PHRASE or len(needle) > MAX_PHRASE:
            return None
        haystack = notes
        index = haystack.lower().find(needle.lower())
        if index < 0:
            return None
        return haystack[index : index + len(needle)]

    def sentence_for(self, matched: str, sentences: list[str]) -> tuple[int, str]:
        lowered = matched.lower()
        for index, sentence in enumerate(sentences):
            if lowered in sentence.lower():
                return index, sentence
        return 0, sentences[0] if sentences else matched


class ConstrainedLlmMerger:
    """Merges gated proposals into catalog hits. Does not call a model itself."""

    def __init__(self, gate: VerbatimSpanGate | None = None) -> None:
        self._gate = gate or VerbatimSpanGate()

    def merge(
        self,
        notes: str,
        sentences: list[str],
        hits: dict[str, CatalogHit],
        proposals: list[ProposedComponent],
        trace: TraceLog,
    ) -> tuple[int, int]:
        accepted = 0
        rejected = 0
        for proposal in proposals:
            matched = self._gate.locate(proposal.phrase, notes)
            if matched is None:
                rejected += 1
                trace.add(
                    "llm_rejected",
                    "verbatim_missing",
                    f"Rejected {proposal.phrase!r}: it does not appear verbatim in the notes.",
                    evidence=proposal.phrase,
                )
                continue
            if _already_covered(hits, matched):
                rejected += 1
                trace.add(
                    "llm_rejected",
                    "already_catalogued",
                    f"Rejected {matched!r}: the catalog already covers this phrase.",
                    evidence=matched,
                )
                continue
            component_id = slug(matched)
            if component_id in hits:
                rejected += 1
                trace.add(
                    "llm_rejected",
                    "duplicate_id",
                    f"Rejected {matched!r}: id {component_id!r} already exists.",
                    component_ids=[component_id],
                    evidence=matched,
                )
                continue
            kind = proposal.kind if proposal.kind in ALLOWED_KINDS else "external_system"
            zone = proposal.zone if proposal.zone in ALLOWED_ZONES else "unspecified"
            name = " ".join(proposal.name.split()) or matched
            sentence_index, sentence = self._gate.sentence_for(matched, sentences)
            hit = CatalogHit(
                id=component_id,
                name=name,
                kind=kind,
                zone=zone,
                pattern=re.escape(matched.lower()),
            )
            hit.evidence.append(sentence)
            hit.spans.append(
                EvidenceSpan(
                    sentence_index=sentence_index,
                    sentence=sentence,
                    matched_text=matched,
                    rule="llm:verbatim",
                )
            )
            hits[component_id] = hit
            accepted += 1
            trace.add(
                "llm_accepted",
                "llm:verbatim",
                f"Accepted {matched!r} as {name!r} (phrase occurs in the notes).",
                sentence_index=sentence_index,
                component_ids=[component_id],
                evidence=sentence,
            )
        drop_generic_database(hits)
        return accepted, rejected


def _already_covered(hits: dict[str, CatalogHit], phrase: str) -> bool:
    lowered = phrase.lower()
    return any(re.search(hit.pattern, lowered) for hit in hits.values())


class OpenAiCompatibleProposer:
    """Calls an OpenAI-compatible chat API. Still untrusted until the verbatim gate."""

    provider_name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout_sec: float = 20.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_sec

    def propose(self, notes: str, sentences: list[str]) -> list[ProposedComponent]:
        payload = {
            "model": self._model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": notes},
            ],
        }
        request = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            return []
        content = (
            body.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        return parse_proposal_json(content)


_SYSTEM_PROMPT = """You extract infrastructure and application components from technical notes.
Return JSON only, no markdown: {"components":[{"phrase":"...","name":"...","kind":"...","zone":"..."}]}
Rules:
- phrase MUST be a contiguous copy of words from the notes (same spelling).
- Never invent products, clouds, or boxes that are not written in the notes.
- Skip generic English that is not a system component.
- kind must be one of: client, firewall, load_balancer, application_server, application_service, database, external_system, gateway, cache, storage, queue, cdn, network, proxy, api, network_zone, observability
- zone must be one of: external, edge, application, data, internal
"""


def parse_proposal_json(content: str) -> list[ProposedComponent]:
    text = content.strip()
    fenced = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(0)
    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError:
        return []
    rows = data.get("components", data) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return []
    proposals: list[ProposedComponent] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        phrase = str(row.get("phrase") or "").strip()
        if not phrase:
            continue
        proposals.append(
            ProposedComponent(
                phrase=phrase,
                name=str(row.get("name") or phrase).strip(),
                kind=str(row.get("kind") or "external_system").strip(),
                zone=str(row.get("zone") or "unspecified").strip(),
            )
        )
    return proposals


def proposer_from_env() -> SpanProposer:
    provider = os.getenv("ARCHDIAG_LLM_PROVIDER", "off").strip().lower()
    if provider in {"", "off", "none", "false", "0"}:
        return NullProposer()
    if provider in {"openai", "on", "1", "true"}:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            return NullProposer()
        model = os.getenv("ARCHDIAG_LLM_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
        base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        return OpenAiCompatibleProposer(api_key=api_key, model=model, base_url=base)
    return NullProposer()


def llm_status() -> str:
    proposer = proposer_from_env()
    if isinstance(proposer, NullProposer):
        if os.getenv("ARCHDIAG_LLM_PROVIDER", "off").strip().lower() in {"openai", "on", "1", "true"}:
            if not os.getenv("OPENAI_API_KEY", "").strip():
                return "missing_api_key"
        return "off"
    return proposer.provider_name
