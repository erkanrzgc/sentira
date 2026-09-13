import sqlite3
from dataclasses import fields

import pytest

from sentira.core.document import Document, FieldClass
from sentira.storage.repository import Repository
from sentira.storage.schema import COLUMN_CLASSES


def test_schema_has_no_raw_identifier_or_document_counter_columns(tmp_path, clock):
    path = tmp_path / "synthetic.sqlite3"
    with Repository(path, clock=clock):
        with sqlite3.connect(path) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(documents)")}
            assert columns == {f.name for f in fields(Document)} | {"observed_at"}
            assert set(COLUMN_CLASSES["documents"]) == columns
            for table in COLUMN_CLASSES:
                actual = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
                assert set(COLUMN_CLASSES[table]) == actual
                assert all(isinstance(v, FieldClass) for v in COLUMN_CLASSES[table].values())
            for item in fields(Document):
                assert COLUMN_CLASSES["documents"][item.name] == item.metadata["class"]


def test_sql_constraints_reject_raw_hash_and_wrong_kind(tmp_path, clock):
    path = tmp_path / "synthetic.sqlite3"
    with Repository(path, clock=clock):
        with sqlite3.connect(path) as connection:
            for value in ("raw-author-marker", "x" * 64):
                with pytest.raises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            "a" * 64,
                            "utterance",
                            "synthetic",
                            "2026-01-01T10:00:00.000000+00:00",
                            "2026-01-01T10:00:00.000000+00:00",
                            "Synthetic text",
                            value,
                            None,
                            "synthetic",
                            "2026-01-01T12:00:00.000000+00:00",
                        ),
                    )


def test_snapshot_foreign_key_and_nonnegative_constraint(tmp_path, clock):
    path = tmp_path / "synthetic.sqlite3"
    with Repository(path, clock=clock):
        with sqlite3.connect(path) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            for count in (-1, 1):
                with pytest.raises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO snapshots VALUES (?, ?, ?, ?)",
                        ("a" * 64, "2026-01-01T12:00:00.000000+00:00", "likes", count),
                    )
