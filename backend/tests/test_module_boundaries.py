"""Module boundary rule (CLAUDE.md §4, doc 07 §7, NFR-MOD-01).

A module under ``crowdcast/`` may import another module only through its ``interfaces.py``.
``common`` (config, enums, time helpers) is shared by everyone. CLI tools under ``tools/`` are
not modules and are not checked. This test stands in for import-linter (no extra dependency).
"""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "crowdcast"
SHARED = {"common"}


def _violations() -> list[str]:
    found: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        rel = path.relative_to(PACKAGE)
        if len(rel.parts) < 2 or "migrations" in rel.parts:
            continue
        own = rel.parts[0]
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Import | ast.ImportFrom):
                continue
            names: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            for name in names:
                parts = name.split(".")
                if parts[0] != "crowdcast" or len(parts) < 2:
                    continue
                target = parts[1]
                if target == own or target in SHARED:
                    continue
                if len(parts) != 3 or parts[2] != "interfaces":
                    found.append(f"{rel}:{node.lineno} imports {name}")
    return found


def test_modules_import_each_other_only_through_interfaces() -> None:
    assert _violations() == []


def test_every_module_has_an_interfaces_file() -> None:
    modules = [p for p in PACKAGE.iterdir() if p.is_dir() and (p / "__init__.py").exists()]
    missing = [
        p.name
        for p in modules
        if p.name not in SHARED | {"api"} and not (p / "interfaces.py").exists()
    ]
    assert missing == []
