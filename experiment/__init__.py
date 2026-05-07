"""experiment package — internal use only."""

from __future__ import annotations

from pathlib import Path

# Internal constant: project root path for sys.path setup in core modules.
# NOT intended for external use. Only accessed by loader/runner/simulate_kg.
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

__all__ = []  # No public API
