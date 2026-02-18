"""Backward-compat shim — import from distill.shared.store instead."""
import sys as _sys

import distill.shared.store as _real_module

_sys.modules[__name__] = _real_module
