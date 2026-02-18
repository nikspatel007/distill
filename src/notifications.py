"""Backward-compat shim — import from distill.shared.notifications instead."""
import sys as _sys

import distill.shared.notifications as _real_module

_sys.modules[__name__] = _real_module
