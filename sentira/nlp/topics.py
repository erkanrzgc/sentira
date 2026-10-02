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


def _matcher(taxonomy):
    """Build the keyword index once; the taxonomy forbids overlapping keywords."""
    if type(taxonomy) is not Taxonomy:
        raise ValueError("A validated taxonomy is required")
    positions = {
        keyword: position
        for position, topic in enumerate(taxonomy.topics)
        for keyword in topic.keywords
    }
    lengths = sorted({len(keyword) - 1 for keyword in positions if keyword.endswith("*")})
    ids = tuple(topic.id for topic in taxonomy.topics)

    def match(text):
        matched = set()
        for word in set(WORD.findall(taxonomy.normalise(text))):
            if word in positions:
                matched.add(word)
            # At most one stem can cover a word, so the first hit is the only one.
            for length in lengths:
                if length > len(word):
                    break
                if word[:length] + "*" in positions:
                    matched.add(word[:length] + "*")
                    break
        # Distinct keywords count, not the words that matched them.
        counts = [0] * len(ids)
        for keyword in matched:
            counts[positions[keyword]] += 1
        best = max(range(len(ids)), key=lambda position: (counts[position], -position))
        return ids[best] if counts[best] else None

    return match


def assign(text, taxonomy):
    """The single topic of a text, or None when no keyword matches."""
    return _matcher(taxonomy)(text)


def assign_visible(result, taxonomy, *, expected_sha256):
    """Assign every comment visible in an as-of read under the registered taxonomy."""
    if type(result) is not AsOfResult or type(taxonomy) is not Taxonomy:
        raise ValueError("An as-of result and a validated taxonomy are required")
    sha256 = taxonomy.sha256
    if sha256 != expected_sha256:
        raise ValueError("The taxonomy does not match its registered digest")
    match = _matcher(taxonomy)
    return tuple(
        Assignment(document.doc_hash, match(document.text), sha256)
        for document in result.documents
        if document.kind is DocumentKind.UTTERANCE
    )
