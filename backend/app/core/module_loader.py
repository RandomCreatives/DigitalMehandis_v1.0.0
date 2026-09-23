"""
Module loader.

Every feature lives in ``app/modules/<name>/``. A module exposes its HTTP API
through ``router.py`` (an ``APIRouter`` named ``router``). Extra routers can be
declared in the module's ``__init__.py`` via ``EXTRA_ROUTERS = ["other_router"]``.

Module import failures are fatal: a silently missing module hides real bugs.
"""
import importlib
import pkgutil

from fastapi import APIRouter, FastAPI
from loguru import logger


def discover_modules(modules_package: str = "app.modules") -> list[str]:
    package = importlib.import_module(modules_package)
    return sorted(name for _, name, is_pkg in pkgutil.iter_modules(package.__path__) if is_pkg)


def load_modules(app: FastAPI, modules_package: str = "app.modules", prefix: str = "/api/v1") -> list[str]:
    # Register all models first so cross-module relationships resolve.
    importlib.import_module("app.db.registry")

    loaded: list[str] = []
    for name in discover_modules(modules_package):
        pkg = importlib.import_module(f"{modules_package}.{name}")
        router_files = ["router", *getattr(pkg, "EXTRA_ROUTERS", [])]
        for rf in router_files:
            try:
                mod = importlib.import_module(f"{modules_package}.{name}.{rf}")
            except ModuleNotFoundError as e:
                if e.name == f"{modules_package}.{name}.{rf}":
                    continue  # module has no router (e.g. library-only module)
                raise
            router = getattr(mod, "router", None)
            if isinstance(router, APIRouter):
                app.include_router(router, prefix=prefix)
                loaded.append(f"{name}.{rf}")
    logger.info(f"Loaded {len(loaded)} routers: {', '.join(loaded)}")
    return loaded
