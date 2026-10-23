"""Load the repo root as a package, the way Hermes loads an installed plugin directory."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent
PACKAGE = "plainspoken_plugin"


def load_plugin():
    if PACKAGE in sys.modules:
        return sys.modules[PACKAGE]
    spec = importlib.util.spec_from_file_location(
        PACKAGE, PLUGIN_DIR / "__init__.py", submodule_search_locations=[str(PLUGIN_DIR)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE] = module
    spec.loader.exec_module(module)
    return module


def load_module(name: str):
    """Import a submodule (detector, rules, surfaces, rewrite, ...) of the plugin package."""
    load_plugin()
    return importlib.import_module(f"{PACKAGE}.{name}")


def load_detector():
    return load_module("detector")
