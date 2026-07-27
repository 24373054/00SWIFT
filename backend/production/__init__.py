"""Production-oriented cross-border payment domain.

The package is deliberately isolated from ``nextgen``. Alembic may select the
frozen pre-0004 model snapshot while bootstrapping an empty database; normal
application imports always expose the current production models.
"""

from __future__ import annotations

import os

if os.getenv("_00SWIFT_ALEMBIC_BASELINE") == "1":
    from . import baseline_0002_models as models
else:
    from . import models

for _name in dir(models):
    if _name.startswith("Production"):
        globals()[_name] = getattr(models, _name)

__all__ = [name for name in globals() if name.startswith("Production")]
