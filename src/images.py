"""Backward-compat shim — import from distill.shared.images instead."""

import sys as _sys

import distill.shared.images as _real_module

_sys.modules[__name__] = _real_module
