"""diet_recommendation experiment package.

공통 상수:
  PROJECT_ROOT — 프로젝트 루트 절대경로 (loader/runner/CLI에서 sys.path 추가에 사용)
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

__all__ = ["PROJECT_ROOT"]
