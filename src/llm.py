"""Backward-compat shim — import from distill.shared.llm instead."""

import sys as _sys

import distill.shared.llm as _real_module

_sys.modules[__name__] = _real_module
