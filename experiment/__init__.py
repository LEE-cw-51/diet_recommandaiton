"""experiment package — internal use only.

Internal constants:
  _PROJECT_ROOT — 프로젝트 루트 절대경로 (loader/runner/CLI에서 sys.path 추가에만 사용)
                  외부에서는 직접 참조하지 말 것.
"""

from __future__ import annotations

from pathlib import Path

# Internal constant — do NOT use outside of experiment package
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# Re-export for backward compatibility (internal modules only)
PROJECT_ROOT = _PROJECT_ROOT

__all__ = []  # No public API
