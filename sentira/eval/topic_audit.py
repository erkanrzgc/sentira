"""Blind, seeded, stratified topic audit (BACKTEST A.9 and Phase 1 exit criterion e).

Candidates are drawn per stratum with a registered seed. A development audit
draws only from before the first origin and a confirmatory audit only from after
it. Audit items carry an opaque identifier and the text, nothing else, and are
shuffled across strata; the key that links them to documents is kept apart.
Precision and recall are reported with Wilson score intervals. Estimates are
unweighted across strata.
"""

import math
import random
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction

from sentira.core.document import utc
from sentira.core.registration import integer, slug

MODES = frozenset({"development", "confirmatory"})
Z_95 = 1.959963984540054


@dataclass(frozen=True, slots=True)
class Candidate:
    doc_hash: str
    text: str
    published_at: datetime
    stratum: str
    assigned: str | None

    def __post_init__(self):
        object.__setattr__(self, "published_at", utc(self.published_at))
        slug(self.stratum)
        if self.assigned is not None:
            slug(self.assigned)


@dataclass(frozen=True, slots=True)
class AuditItem:
    audit_id: str
    text: str


def draw_audit(candidates, *, per_stratum, seed, origin, mode):
    """Return (items, key): blind items and the key from item to candidate."""
    if mode not in MODES:
        raise ValueError("The audit mode is development or confirmatory")
    integer(per_stratum, 1, 100_000)
    integer(seed, 0, 2**63 - 1)
    origin = utc(origin)
    pool = {}
    for candidate in candidates:
        if type(candidate) is not Candidate:
            raise ValueError("Validated candidates are required")
        before = candidate.published_at < origin
        if before == (mode == "development"):
            pool.setdefault(candidate.stratum, []).append(candidate)
    chosen = []
    for stratum in sorted(pool):
        members = sorted(pool[stratum], key=lambda candidate: candidate.doc_hash)
        generator = random.Random(f"{seed}:{stratum}")
        chosen.extend(generator.sample(members, min(per_stratum, len(members))))
    random.Random(f"{seed}:order").shuffle(chosen)
    key = {f"item-{index:05d}": candidate for index, candidate in enumerate(chosen)}
    items = tuple(AuditItem(audit_id, candidate.text) for audit_id, candidate in key.items())
    return items, key


def wilson(successes, n, z=Z_95):
    """Wilson score interval for a binomial proportion."""
    integer(n, 1, 10**12)
    integer(successes, 0, n)
    p = successes / n
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


@dataclass(frozen=True, slots=True)
class Rate:
    successes: int
    n: int
    low: float
    high: float

    @property
    def value(self):
        return self.successes / self.n


def _rate(successes, n):
    return Rate(successes, n, *wilson(successes, n)) if n else None


def audit_metrics(key, annotations):
    """Per topic: (precision, recall) as Wilson-bounded rates, or None without items."""
    if set(annotations) != set(key):
        raise ValueError("Every audit item needs exactly one annotation")
    topics = {candidate.assigned for candidate in key.values()} | set(annotations.values())
    metrics = {}
    for topic in sorted(topic for topic in topics if topic is not None):
        assigned = [audit_id for audit_id, item in key.items() if item.assigned == topic]
        actual = [audit_id for audit_id, label in annotations.items() if label == topic]
        precision = sum(annotations[audit_id] == topic for audit_id in assigned)
        recall = sum(key[audit_id].assigned == topic for audit_id in actual)
        metrics[topic] = (_rate(precision, len(assigned)), _rate(recall, len(actual)))
    return metrics


def cohen_kappa(first, second):
    """Agreement beyond chance between two labellings; None when chance is certain."""
    first, second = list(first), list(second)
    if not first or len(first) != len(second):
        raise ValueError("Two labellings of the same non-empty items are required")
    n = len(first)
    observed = Fraction(sum(a == b for a, b in zip(first, second, strict=True)), n)
    labels = set(first) | set(second)
    chance = sum(Fraction(first.count(label) * second.count(label), n * n) for label in labels)
    if chance == 1:
        return None
    return float((observed - chance) / (1 - chance))
