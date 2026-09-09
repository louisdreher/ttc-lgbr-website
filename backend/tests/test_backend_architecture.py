"""Keep infrastructure out of every component's application core."""

import ast
from importlib.util import resolve_name
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"


@pytest.mark.parametrize(
    "path",
    sorted((APP / "core").rglob("*.py")),
    ids=lambda path: str(path.relative_to(APP)),
)
def test_core_has_no_infrastructure_imports(path):
    forbidden = (
        "fastapi",
        "sqlmodel",
        "sqlalchemy",
        "pydantic",
        "httpx",
        "jwt",
        "pwdlib",
        "app.adapters",
        "app.bootstrap",
        "app.model_registry",
    )
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imports = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            package = ".".join(path.relative_to(APP.parent).parent.parts)
            imports = [resolve_name("." * node.level + (node.module or ""), package)]
        else:
            continue
        for name in imports:
            assert not any(
                name == prefix or name.startswith(prefix + ".") for prefix in forbidden
            ), (path, name)
            if "domain" in path.parts:
                assert ".application" not in name, (path, name)
