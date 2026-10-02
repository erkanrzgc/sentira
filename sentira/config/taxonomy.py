"""Strict TOML input for the frozen topic taxonomy (BACKTEST A.2, D.8).

Topics are standing institutional subjects named without reference to any event.
Their order is registered: it breaks ties in the single-label priority rule. A
keyword is a whole word or a stem of at least four letters ending in "*", written
in its normalised form. The case map registers language-specific case folding,
applied before lower-casing, so the matching rule is data rather than code.
"""

import tomllib
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from sentira.core.document import utc
from sentira.core.registration import digest, exact, sequence, slug, text

MIN_TOPICS, MAX_TOPICS = 2, 30
MAX_KEYWORDS = 500
MIN_STEM = 4


@dataclass(frozen=True, slots=True)
class Topic:
    id: str
    keywords: tuple[str, ...]

    def __post_init__(self):
        slug(self.id)
        if type(self.keywords) is not tuple or not 0 < len(self.keywords) <= MAX_KEYWORDS:
            raise ValueError("A topic needs a bounded, non-empty tuple of keywords")
        if len(set(self.keywords)) != len(self.keywords):
            raise ValueError("Keywords repeat within a topic")
        for keyword in self.keywords:
            word = keyword[:-1] if isinstance(keyword, str) and keyword.endswith("*") else keyword
            if not isinstance(word, str) or not word.isalpha():
                raise ValueError("A keyword is a word or a stem of letters only")
            if keyword.endswith("*") and len(word) < MIN_STEM:
                raise ValueError("A stem needs at least four letters")


@dataclass(frozen=True, slots=True)
class Taxonomy:
    mode: str
    version: str
    frozen_at: datetime
    case_map: tuple[tuple[str, str], ...]
    topics: tuple[Topic, ...]

    def __post_init__(self):
        if self.mode != "synthetic":
            raise ValueError("Only synthetic taxonomies are supported")
        slug(self.version)
        object.__setattr__(self, "frozen_at", utc(self.frozen_at))
        pairs = self.case_map
        if type(pairs) is not tuple or any(
            type(pair) is not tuple
            or len(pair) != 2
            or any(not isinstance(char, str) or len(char) != 1 for char in pair)
            for pair in pairs
        ):
            raise ValueError("The case map is a tuple of single-character pairs")
        if len({source for source, _ in pairs}) != len(pairs):
            raise ValueError("A character is folded more than once")
        topics = self.topics
        if type(topics) is not tuple or not MIN_TOPICS <= len(topics) <= MAX_TOPICS:
            raise ValueError("A taxonomy needs a bounded number of topics")
        if any(type(topic) is not Topic for topic in topics):
            raise ValueError("Validated topics are required")
        if len({topic.id for topic in topics}) != len(topics):
            raise ValueError("Topic identifiers must be unique")
        keywords = [keyword for topic in topics for keyword in topic.keywords]
        if len(set(keywords)) != len(keywords):
            raise ValueError("A keyword may belong to one topic only")
        if any(self.normalise(keyword) != keyword for keyword in keywords):
            raise ValueError("Keywords must be written in their normalised form")
        # One word may match at most one keyword: a stem may not cover another
        # keyword, in its own topic or any other.
        for stem in (keyword[:-1] for keyword in keywords if keyword.endswith("*")):
            for keyword in keywords:
                if keyword != stem + "*" and keyword.rstrip("*").startswith(stem):
                    raise ValueError("A stem covers another keyword")

    @classmethod
    def from_mapping(cls, raw):
        exact(raw, ("mode", "version", "frozen_at", "case_map", "topics"))
        if not isinstance(raw["case_map"], list) or not isinstance(raw["topics"], list):
            raise ValueError("The case map and the topics must be lists")
        return cls(
            mode=raw["mode"],
            version=raw["version"],
            frozen_at=raw["frozen_at"],
            case_map=tuple(
                tuple(pair) if isinstance(pair, list) else pair for pair in raw["case_map"]
            ),
            topics=tuple(
                Topic(id=item["id"], keywords=sequence(item["keywords"], text))
                for item in (exact(entry, ("id", "keywords")) for entry in raw["topics"])
            ),
        )

    @property
    def sha256(self):
        return digest(self)

    def normalise(self, text):
        """Fold registered characters, then lower-case."""
        return text.translate(_fold_table(self.case_map)).lower()


@lru_cache(maxsize=32)
def _fold_table(case_map):
    return {ord(source): target for source, target in case_map}


def load_taxonomy(path):
    with Path(path).open("rb") as stream:
        return Taxonomy.from_mapping(tomllib.load(stream))
