"""Backward-compat shim — import from distill.shared.config instead."""
import sys as _sys

import distill.shared.config as _real_module

_sys.modules[__name__] = _real_module
