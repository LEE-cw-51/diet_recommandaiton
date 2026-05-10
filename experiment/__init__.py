"""experiment package — internal use only.

This package provides the multi-objective optimization experiment framework
for diet recommendation. It is NOT intended for external use.

Internal Structure:
  core/           — Problem definitions, data loaders, metrics, KG manager
  algorithms/     — NSGA-II and R-NSGA-II algorithm factories
  config/         — YAML experiment configurations
  results/        — Output directory for experiment runs
  tools/          — Utility scripts (e.g., simulate_kg for KG validation)

Internal Constants:
  _PROJECT_ROOT  — Project root path. Used by core modules (loader/runner/simulate_kg)
                   to setup sys.path for importing db.client. NOT for external use.

Public API: None (__all__ = [])
"""

from __future__ import annotations

from pathlib import Path

# Internal constant: project root path for sys.path setup in core modules.
# NOT intended for external use. Only accessed by loader/runner/simulate_kg.
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

__all__ = []  # No public API
