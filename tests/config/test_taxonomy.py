"""Frozen topic taxonomy: registered order, counter-free, digest-bound."""

from dataclasses import replace
from pathlib import Path

import pytest

from sentira.config.taxonomy import load_taxonomy

TAXONOMY = Path(__file__).resolve().parents[2] / "examples/synthetic-taxonomy.toml"
TOPICS = [
    "economy",
    "health",
    "education",
    "justice",
    "security",
    "foreign-policy",
    "environment-and-disasters",
    "local-services",
    "energy",
    "social-security",
    "elections",
]


def test_shipped_taxonomy_validates_in_registered_order():
    taxonomy = load_taxonomy(TAXONOMY)
    assert [topic.id for topic in taxonomy.topics] == TOPICS
    assert len(taxonomy.sha256) == 64
    assert taxonomy.normalise("KASTOR Valtor") == "qastor valtor"


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('keywords = ["sentavo", "kirumel*"]', 'keywords = ["sentavo", "prensek"]'),
        ('keywords = ["sentavo", "kirumel*"]', 'keywords = ["sentavo", "kir*"]'),
        ('keywords = ["sentavo", "kirumel*"]', 'keywords = ["Sentavo", "kirumel*"]'),
        ('keywords = ["sentavo", "kirumel*"]', 'keywords = ["sentavo2", "kirumel*"]'),
        ('keywords = ["sentavo", "kirumel*"]', 'keywords = ["sen tavo", "kirumel*"]'),
        ('keywords = ["sentavo", "kirumel*"]', "keywords = []"),
        ('id = "health"', 'id = "economy"'),
        ('id = "health"\n', 'id = "health"\nmin_views = 100\n'),
        ('case_map = [["K", "q"]]', 'case_map = [["KK", "q"]]'),
        ('mode = "synthetic"', 'mode = "live"'),
        ('case_map = [["K", "q"]]', 'case_map = [["K", "q"], ["K", "r"]]'),
        ('keywords = ["sentavo", "kirumel*"]', 'keywords = ["sentavo", "sentavo"]'),
        ('keywords = ["sentavo", "kirumel*"]', 'keywords = ["sentavo", 5]'),
    ],
)
def test_invalid_taxonomies_are_refused(tmp_path, old, new):
    text = TAXONOMY.read_text(encoding="utf-8")
    assert old in text
    path = tmp_path / "taxonomy.toml"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(ValueError):
        load_taxonomy(path)


def test_direct_construction_is_validated():
    taxonomy = load_taxonomy(TAXONOMY)
    with pytest.raises(ValueError):
        replace(taxonomy, topics=taxonomy.topics[:1])
    with pytest.raises(ValueError):
        replace(taxonomy, topics=(*taxonomy.topics[:2], "economy"))
