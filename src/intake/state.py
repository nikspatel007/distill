"""Backward-compat shim -- canonical locations: distill.intake.models + distill.intake.services."""

from distill.intake.models import (  # noqa: F401
    IntakeRecord,
    IntakeState,
)
from distill.intake.services import (  # noqa: F401
    STATE_FILENAME,
    load_intake_state,
    save_intake_state,
)
