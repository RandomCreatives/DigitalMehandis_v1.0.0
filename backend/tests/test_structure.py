"""Guards for the module layout (see docs/ARCHITECTURE.md)."""
import importlib
import pathlib

from app.core.module_loader import discover_modules
from app.db.base import Base
from app.main import app

MODULES_DIR = pathlib.Path(__file__).resolve().parents[1] / "app" / "modules"

EXPECTED_MODULES = {
    "audit", "auth", "bbs", "boq", "boq_items", "cad", "calibration", "cost_library",
    "drawings", "elements", "measurements", "projects", "rate_matching", "rates", "takeoff",
}


def test_all_modules_discovered():
    assert set(discover_modules()) == EXPECTED_MODULES


def test_every_table_is_owned_by_a_module():
    owners = {}
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        parts = cls.__module__.split(".")
        assert parts[:2] == ["app", "modules"] and parts[-1] == "models", (
            f"{cls.__name__} must live in app/modules/<name>/models.py, found {cls.__module__}"
        )
        owners[cls.__tablename__] = parts[2]
    assert len(owners) == len(Base.metadata.tables)


def test_no_legacy_packages():
    app_dir = MODULES_DIR.parent
    for legacy in ("schemas", "services", "utils", "api", "dependencies"):
        assert not (app_dir / legacy).exists(), f"app/{legacy} was retired — put code in a module"


def test_all_routers_import_cleanly():
    # A module whose router fails to import must fail loudly, not disappear.
    for name in discover_modules():
        if (MODULES_DIR / name / "router.py").exists():
            importlib.import_module(f"app.modules.{name}.router")


def test_core_api_routes_registered():
    paths = {r.path for r in app.routes}
    for p in (
        "/api/v1/auth/login",
        "/api/v1/projects",
        "/api/v1/projects/{project_id}/drawings/upload",
        "/api/v1/projects/{project_id}/boq-items",
        "/api/v1/projects/{project_id}/bbs",
        "/api/v1/templates",
        "/health",
    ):
        assert p in paths, p
