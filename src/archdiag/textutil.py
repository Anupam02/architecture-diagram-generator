from __future__ import annotations

import re


def normalize_notes(notes: str) -> str:
    return " ".join(notes.split()).strip()


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def extract_protocol(sentence: str) -> str | None:
    lowered = sentence.lower()
    for name in ("https", "http", "ssh", "tls", "tcp", "udp"):
        if re.search(rf"\b{name}\b", lowered):
            return name.upper()
    return None


def extract_port(sentence: str) -> str | None:
    match = re.search(r"port\s+(\d+)", sentence.lower())
    if match:
        return match.group(1)
    match = re.search(r":(\d{2,5})\b", sentence)
    return match.group(1) if match else None


def first_index(text: str, pattern: str) -> int:
    match = re.search(pattern, text)
    return match.start() if match else 10_000


def slug(phrase: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", phrase.lower()).strip("-")
    return value or "named-component"
