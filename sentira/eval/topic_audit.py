"""Blind, seeded, stratified topic audit (BACKTEST A.9 and Phase 1 exit criterion e).

Candidates are drawn per stratum with a registered seed. A development audit
draws only from before the first origin and a confirmatory audit only from after
it. Audit items carry an opaque identifier and the text, nothing else, and are
shuffled across strata; the key that links them to documents is kept apart.

Strata are sampled at different rates, so every rate is weighted by the stratum's
population over its sample. Intervals are Wilson score intervals at the Kish
effective sample size, an approximation that reduces to the plain Wilson interval
when every weight is equal. Accuracy is reported beside a majority-class and a
random baseline. Every draw and report carries the taxonomy digest.
"""

import math
import random
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from types import MappingProxyType

from sentira.config.taxonomy import Taxonomy
from sentira.core.document import DocumentKind, utc, valid_hash
from sentira.core.registration import integer, slug
from sentira.nlp.topics import Assignment
from sentira.storage.asof import VisibleDocument

MODES = frozenset({"development", "confirmatory"})
Z_95 = 1.959963984540054


@dataclass(frozen=True, slots=True)
class Candidate:
    doc_hash: str
    text: str
    published_at: datetime
    stratum: str
    assigned: str | None
    taxonomy_sha256: str

    def __post_init__(self):
        if not valid_hash(self.doc_hash) or not valid_hash(self.taxonomy_sha256):
            raise ValueError("A candidate needs a document hash and a taxonomy digest")
        object.__setattr__(self, "published_at", utc(self.published_at))
        slug(self.stratum)
        if self.assigned is not None:
            slug(self.assigned)

    @classmethod
    def from_assignment(cls, assignment, document, *, stratum):
        """A candidate from an as-of comment and its assignment, keeping the digest."""
        if type(assignment) is not Assignment or type(document) is not VisibleDocument:
            raise ValueError("An assignment and its as-of document are required")
        if document.kind is not DocumentKind.UTTERANCE:
            raise ValueError("Only comments are audited")
        if assignment.doc_hash != document.doc_hash:
            raise ValueError("The assignment belongs to another document")
        return cls(
            document.doc_hash,
            document.text,
            document.published_at,
            stratum,
            assignment.topic,
            assignment.taxonomy_sha256,
        )


@dataclass(frozen=True, slots=True)
class AuditItem:
    audit_id: str
    text: str


def _check_candidate(candidate, sha256, topics):
    if type(candidate) is not Candidate:
        raise ValueError("Validated candidates are required")
    if candidate.taxonomy_sha256 != sha256:
        raise ValueError("A candidate was assigned under another taxonomy digest")
    if candidate.assigned is not None and candidate.assigned not in topics:
        raise ValueError("A candidate is assigned to an unregistered topic")


@dataclass(frozen=True, slots=True)
class AuditDraw:
    """Blind items, the key kept apart from them, and what weighting needs.

    The draw checks itself on construction, so a hand-built or edited draw
    meets the same rules as one from draw_audit. Topics and digest are read
    from the taxonomy, so neither can be changed apart from it.
    """

    taxonomy: Taxonomy
    mode: str
    seed: int
    per_stratum: int
    population: Mapping[str, int]
    items: tuple[AuditItem, ...]
    key: Mapping[str, Candidate]

    def __post_init__(self):
        if type(self.taxonomy) is not Taxonomy:
            raise ValueError("A validated taxonomy is required")
        if self.mode not in MODES:
            raise ValueError("The audit mode is development or confirmatory")
        integer(self.per_stratum, 1, 100_000)
        integer(self.seed, 0, 2**63 - 1)
        if not isinstance(self.population, Mapping) or not isinstance(self.key, Mapping):
            raise ValueError("The population and the key are mappings")
        population = {
            slug(stratum): self.population[stratum] for stratum in sorted(self.population)
        }
        for size in population.values():
            integer(size, 1, 10**9)
        key, sha256, topics = dict(self.key), self.taxonomy.sha256, self.topics
        counts = dict.fromkeys(population, 0)
        for candidate in key.values():
            _check_candidate(candidate, sha256, topics)
            if candidate.stratum not in counts:
                raise ValueError("A candidate's stratum has no recorded population")
            counts[candidate.stratum] += 1
        if len({candidate.doc_hash for candidate in key.values()}) != len(key):
            raise ValueError("A document may enter the audit once")
        if any(counts[stratum] != min(self.per_stratum, population[stratum]) for stratum in counts):
            raise ValueError("Each stratum is sampled at its registered size or taken whole")
        expected = tuple(AuditItem(audit_id, candidate.text) for audit_id, candidate in key.items())
        if type(self.items) is not tuple or self.items != expected:
            raise ValueError("The items must follow the key")
        object.__setattr__(self, "population", MappingProxyType(population))
        object.__setattr__(self, "key", MappingProxyType(key))

    @property
    def taxonomy_sha256(self):
        return self.taxonomy.sha256

    @property
    def topics(self):
        return tuple(topic.id for topic in self.taxonomy.topics)

    @property
    def sampled(self):
        counts = dict.fromkeys(self.population, 0)
        for candidate in self.key.values():
            counts[candidate.stratum] += 1
        return MappingProxyType(counts)

    @property
    def shortfall(self):
        """Strata smaller than the registered size, taken whole."""
        return MappingProxyType(
            {
                stratum: self.per_stratum - size
                for stratum, size in self.population.items()
                if size < self.per_stratum
            }
        )


def draw_audit(candidates, taxonomy, *, expected_sha256, per_stratum, seed, origin, mode):
    """Draw blind audit items per stratum from the span the mode allows."""
    if type(taxonomy) is not Taxonomy:
        raise ValueError("A validated taxonomy is required")
    sha256 = taxonomy.sha256
    if sha256 != expected_sha256:
        raise ValueError("The taxonomy does not match its registered digest")
    if mode not in MODES:
        raise ValueError("The audit mode is development or confirmatory")
    integer(per_stratum, 1, 100_000)
    integer(seed, 0, 2**63 - 1)
    origin = utc(origin)
    topics = tuple(topic.id for topic in taxonomy.topics)
    seen, pool = set(), {}
    for candidate in candidates:
        _check_candidate(candidate, sha256, topics)
        if candidate.doc_hash in seen:
            raise ValueError("A document may enter the audit once")
        seen.add(candidate.doc_hash)
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
    return AuditDraw(
        taxonomy=taxonomy,
        mode=mode,
        seed=seed,
        per_stratum=per_stratum,
        population={stratum: len(members) for stratum, members in pool.items()},
        items=tuple(AuditItem(audit_id, candidate.text) for audit_id, candidate in key.items()),
        key=key,
    )


def _interval(p, n, z):
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def wilson(successes, n, z=Z_95):
    """Wilson score interval for a binomial proportion."""
    integer(n, 1, 10**12)
    integer(successes, 0, n)
    return _interval(successes / n, n, z)


@dataclass(frozen=True, slots=True)
class Rate:
    """Audited counts, the population-weighted estimate and its interval."""

    successes: int
    n: int
    estimate: float
    effective_n: float
    low: float
    high: float


def _rate(pairs):
    """A weighted rate from (weight, success) pairs, or None without items."""
    if not pairs:
        return None
    total = sum(weight for weight, _ in pairs)
    estimate = sum(weight for weight, success in pairs if success) / total
    effective = total * total / sum(weight * weight for weight, _ in pairs)
    low, high = _interval(float(estimate), float(effective), Z_95)
    successes = sum(1 for _, success in pairs if success)
    return Rate(successes, len(pairs), float(estimate), float(effective), low, high)


@dataclass(frozen=True, slots=True)
class TopicRates:
    precision: Rate | None
    recall: Rate | None
    prevalence: float
    assigned_share: float


@dataclass(frozen=True, slots=True)
class AuditReport:
    taxonomy_sha256: str
    mode: str
    topics: Mapping[str, TopicRates]
    accuracy: Rate
    majority_label: str | None
    majority_baseline: float
    random_baseline: float


def audit_metrics(draw, annotations):
    """Weighted precision and recall per topic, and accuracy beside its baselines."""
    if type(draw) is not AuditDraw:
        raise ValueError("An audit draw is required")
    if not draw.key:
        raise ValueError("An audit needs at least one item")
    if not isinstance(annotations, Mapping) or set(annotations) != set(draw.key):
        raise ValueError("Every audit item needs exactly one annotation")
    for label in annotations.values():
        if label is not None and (not isinstance(label, str) or label not in draw.topics):
            raise ValueError("An annotation names an unregistered topic")
    sampled = draw.sampled
    rows = [
        (Fraction(draw.population[c.stratum], sampled[c.stratum]), c.assigned, annotations[i])
        for i, c in draw.key.items()
    ]
    total = sum(weight for weight, _, _ in rows)
    # Weighted shares of each label among the annotations and the assignments.
    labels = (*draw.topics, None)
    prevalence = dict.fromkeys(labels, Fraction(0))
    assigned = dict.fromkeys(labels, Fraction(0))
    for weight, given, label in rows:
        prevalence[label] += weight / total
        assigned[given] += weight / total
    topics = {}
    for topic in draw.topics:
        precision = [(w, label == topic) for w, given, label in rows if given == topic]
        recall = [(w, given == topic) for w, given, label in rows if label == topic]
        topics[topic] = TopicRates(
            _rate(precision),
            _rate(recall),
            float(prevalence[topic]),
            float(assigned[topic]),
        )
    majority = max(labels, key=lambda label: prevalence[label])
    return AuditReport(
        taxonomy_sha256=draw.taxonomy_sha256,
        mode=draw.mode,
        topics=MappingProxyType(topics),
        accuracy=_rate([(weight, given == label) for weight, given, label in rows]),
        majority_label=majority,
        majority_baseline=float(prevalence[majority]),
        random_baseline=float(sum(prevalence[label] * assigned[label] for label in labels)),
    )


def cohen_kappa(first, second):
    """Agreement beyond chance on the re-labelled items, paired by identifier.

    Returns None when chance agreement is certain.
    """
    if not isinstance(first, Mapping) or not isinstance(second, Mapping):
        raise ValueError("Labellings are mappings from item identifier to label")
    if not second or not set(second) <= set(first):
        raise ValueError("Re-labelled items must be a non-empty subset of the first labelling")
    pairs = [(first[item], second[item]) for item in second]
    n = len(pairs)
    observed = Fraction(sum(a == b for a, b in pairs), n)
    labels = {label for pair in pairs for label in pair}
    chance = sum(
        Fraction(
            sum(a == label for a, _ in pairs) * sum(b == label for _, b in pairs),
            n * n,
        )
        for label in labels
    )
    if chance == 1:
        return None
    return float((observed - chance) / (1 - chance))
