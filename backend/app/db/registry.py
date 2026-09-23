"""
Model registry.

Importing this module registers every SQLAlchemy model from every feature
module on ``Base.metadata`` so that relationships resolve and Alembic sees the
complete schema. Each module owns its own ``models.py``.
"""
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.projects import models as projects_models  # noqa: F401
from app.modules.drawings import models as drawings_models  # noqa: F401
from app.modules.calibration import models as calibration_models  # noqa: F401
from app.modules.takeoff import models as takeoff_models  # noqa: F401
from app.modules.rates import models as rates_models  # noqa: F401
from app.modules.bbs import models as bbs_models  # noqa: F401
from app.modules.boq import models as boq_models  # noqa: F401
from app.modules.elements import models as elements_models  # noqa: F401
from app.modules.measurements import models as measurements_models  # noqa: F401
from app.modules.boq_items import models as boq_items_models  # noqa: F401
from app.modules.audit import models as audit_models  # noqa: F401
from app.modules.cost_library import models as cost_library_models  # noqa: F401
from app.modules.rate_matching import models as rate_matching_models  # noqa: F401
from app.modules.cad import models as cad_models  # noqa: F401
