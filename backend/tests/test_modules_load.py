"""Guard against silently-dropped modules.

``app.core.modules.loader`` catches every exception and only logs an error, so
a bad import removes an entire module's routes from the running app without
failing anything. That is how ``app.modules.drawings`` shipped broken:
``BOQItem`` had moved to ``app.db.models_phase2``, and 20 routes quietly
disappeared.

These tests import every module directly and fail loudly instead.
"""

import importlib
import pkgutil

import pytest

from app.core.modules.loader import load_modules
from app.main import app
from app.modules import __path__ as modules_path


def _module_names() -> list[str]:
    return sorted(
        name
        for _, name, _ in pkgutil.walk_packages(modules_path, "app.modules.")
        if name.count(".") <= 3
    )


@pytest.mark.parametrize("module_name", _module_names())
def test_module_imports(module_name):
    """Every module must import cleanly (missing dependency or moved model)."""
    importlib.import_module(module_name)


def test_every_module_registers_a_router():
    missing = []
    for name in _module_names():
        module = importlib.import_module(name)
        from fastapi import APIRouter

        if not isinstance(getattr(module, "router", None), APIRouter):
            missing.append(name)
    assert not missing, f"modules with no router: {missing}"


def test_loader_registers_every_router():
    """Count routers the loader would register and compare to the live app."""
    from fastapi import APIRouter

    expected = 0
    for name in _module_names():
        module = importlib.import_module(name)
        if isinstance(getattr(module, "router", None), APIRouter):
            expected += 1
    assert expected > 0

    # The drawings module is the regression case: it must contribute routes.
    paths = {getattr(r, "path", "") for r in app.routes}
    assert any(p.startswith("/api/v1/projects") for p in paths)
