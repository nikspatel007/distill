"""Backward-compat shim — import from distill.shared.narrative instead."""
import sys as _sys

import distill.shared.narrative as _real_module

_sys.modules[__name__] = _real_module
