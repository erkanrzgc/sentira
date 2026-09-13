import ast
import socket
from pathlib import Path

import pytest


def test_only_storage_imports_database_driver():
    root = Path(__file__).resolve().parents[1] / "sentira"
    violations = []
    for path in root.rglob("*.py"):
        if "storage" in path.relative_to(root).parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            if any(name.split(".")[0] == "sqlite3" for name in names):
                violations.append(str(path))
    assert violations == []


def test_network_guard_rejects_connection_before_any_traffic():
    with pytest.raises(RuntimeError, match="Network access is disabled"):
        socket.create_connection(("example.invalid", 443))
    with pytest.raises(RuntimeError, match="Network access is disabled"):
        socket.getaddrinfo("example.invalid", 443)
