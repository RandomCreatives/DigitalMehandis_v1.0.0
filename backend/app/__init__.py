"""
Digital Mehandis — backend package.

Standalone, open-source quantity surveying platform for the Ethiopian
construction community.

Package layout:
- app.core     configuration, security, auth dependencies, module loader, files, logging
- app.db       SQLAlchemy Base, shared column types, session, model registry, migrations
- app.modules  one self-contained package per feature; each may contain
               models.py, schemas.py, service/logic files and router.py

License: GNU GPL v3
"""

__version__ = "1.1.0"
