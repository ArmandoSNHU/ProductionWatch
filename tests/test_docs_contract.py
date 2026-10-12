"""The endpoint table in docs/ARCHITECTURE.md must match the real API surface."""
from pathlib import Path

from fastapi.routing import APIRoute

from app.main import create_app

DOC = Path(__file__).resolve().parents[1] / "docs" / "ARCHITECTURE.md"


def test_every_route_is_documented(settings):
    text = DOC.read_text(encoding="utf-8")
    app = create_app(settings)
    paths = {r.path for r in app.routes if isinstance(r, APIRoute)}
    missing = sorted(p for p in paths if f"`{p}`" not in text)
    assert not missing, f"Routes missing from ARCHITECTURE.md: {missing}"
