"""experiment package — internal use only.

This package provides the multi-objective optimization experiment framework
for diet recommendation. It is NOT intended for external use.

Internal Structure:
  core/           — Problem definitions, data loaders, metrics, KG manager
  algorithms/     — NSGA-II / R-NSGA-II factory + builders
  models/         — Model variants (G1/G2/G3) + reproducibility constants
  config/         — YAML experiment configurations
  simulation/     — Compute layer: runs optimization, saves artifacts (no plotting)
  visualization/  — Plot layer: loads artifacts/CSV only, never re-runs the optimizer
  evaluation/     — User-study (A/B test) tooling
  results/        — Output directory for experiment runs (CSV / PNG / artifacts.npz)

Internal Constants:
  _PROJECT_ROOT  — Project root path. Used by submodules to setup sys.path for
                   importing db.client. NOT for external use.

Public API: None (__all__ = [])
"""

from __future__ import annotations

from pathlib import Path

# Internal constant: project root path for sys.path setup in core modules.
# NOT intended for external use. Only accessed by loader/runner/simulate_kg.
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

__all__ = []  # No public API
