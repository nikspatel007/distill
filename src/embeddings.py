"""Backward-compat shim — import from distill.shared.embeddings instead."""
import sys as _sys

import distill.shared.embeddings as _real_module

_sys.modules[__name__] = _real_module
