"""Single-label lexical topic assignment on as-of comment text (BACKTEST A.2, 0.4).

Only utterances visible at T are assigned, so a comment edited after T belongs to
no topic at T, and publication text such as a video title is never used. The
topic with the most distinct matching keywords wins; a tie goes to the topic
registered first. Every assignment carries the digest of the taxonomy it used.
"""

import re
from dataclasses import dataclass

from sentira.config.taxonomy import Taxonomy
from sentira.core.document import DocumentKind
from sentira.storage.asof import AsOfResult

WORD = re.compile(r"[^\W\d_]+")


@dataclass(frozen=True, slots=True)
class Assignment:
    doc_hash: str
    topic: str | None
    taxonomy_sha256: str


def _matches(words, keyword):
    if keyword.endswith("*"):
        stem = keyword[:-1]
        return any(word.startswith(stem) for word in words)
    return keyword in words


def assign(text, taxonomy):
    """The single topic of a text, or None when no keyword matches."""
    if type(taxonomy) is not Taxonomy:
        raise ValueError("A validated taxonomy is required")
    words = set(WORD.findall(taxonomy.normalise(text)))
    best, best_count = None, 0
    for topic in taxonomy.topics:
        count = sum(_matches(words, keyword) for keyword in topic.keywords)
        if count > best_count:
            best, best_count = topic.id, count
    return best


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
