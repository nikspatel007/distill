"""Backward-compat shim -- canonical locations: distill.intake.models + distill.intake.services."""

from distill.intake.models import (  # noqa: F401
    DailyIntakeEntry,
    IntakeMemory,
    IntakeThread,
)
from distill.intake.services import (  # noqa: F401
    MEMORY_FILENAME,
    load_intake_memory,
    save_intake_memory,
)
