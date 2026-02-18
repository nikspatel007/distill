"""Backward-compat shim — import from distill.shared.errors instead."""

import sys as _sys

import distill.shared.errors as _real_module

_sys.modules[__name__] = _real_module
