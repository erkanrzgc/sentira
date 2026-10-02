"""Single-label lexical topic assignment on as-of comment text (BACKTEST A.2, 0.4).

Only utterances visible at T are assigned, so a comment edited after T belongs to
no topic at T, and publication text such as a video title is never used. The
topic with the most distinct matching keywords wins; a tie goes to the topic
registered first. Every assignment carries the digest of the taxonomy it used.
"""

import re
from dataclasses import dataclass
from functools import lru_cache

from sentira.config.taxonomy import Taxonomy
from sentira.core.document import DocumentKind
from sentira.storage.asof import AsOfResult

WORD = re.compile(r"[^\W\d_]+")


@dataclass(frozen=True, slots=True)
class Assignment:
    doc_hash: str
    topic: str | None
    taxonomy_sha256: str


@lru_cache(maxsize=8)
def _index(topics):
    """Whole words and stems to their topic's position; the taxonomy forbids overlaps."""
    words, stems = {}, {}
    for position, topic in enumerate(topics):
        for keyword in topic.keywords:
            if keyword.endswith("*"):
                stems[keyword[:-1]] = position
            else:
                words[keyword] = position
    shortest = min((len(stem) for stem in stems), default=0)
    return words, stems, shortest


def assign(text, taxonomy):
    """The single topic of a text, or None when no keyword matches."""
    if type(taxonomy) is not Taxonomy:
        raise ValueError("A validated taxonomy is required")
    words, stems, shortest = _index(taxonomy.topics)
    matched = set()
    for word in set(WORD.findall(taxonomy.normalise(text))):
        if word in words:
            matched.add((words[word], word))
        for length in range(shortest, len(word) + 1) if stems else ():
            stem = word[:length]
            if stem in stems:
                matched.add((stems[stem], stem + "*"))
    counts = [0] * len(taxonomy.topics)
    for position, _ in matched:
        counts[position] += 1
    best = max(range(len(counts)), key=lambda position: (counts[position], -position))
    return taxonomy.topics[best].id if counts[best] else None


def assign_visible(result, taxonomy, *, expected_sha256):
    """Assign every comment visible in an as-of read under the registered taxonomy."""
    if type(result) is not AsOfResult or type(taxonomy) is not Taxonomy:
        raise ValueError("An as-of result and a validated taxonomy are required")
    sha256 = taxonomy.sha256
    if sha256 != expected_sha256:
        raise ValueError("The taxonomy does not match its registered digest")
    return tuple(
        Assignment(document.doc_hash, assign(document.text, taxonomy), sha256)
        for document in result.documents
        if document.kind is DocumentKind.UTTERANCE
    )
