"""KGManager — NetworkX 기반 지식 그래프 (사용자-메뉴 관계만).

노드:
  user : 사용자
  menu : 후보 메뉴 (product_name / menu_name)

엣지 (MultiDiGraph, key로 종류 구분):
  PREFERS (User → Menu) : 별점 기반 선호도 (weight = rating / 3.0)
  ATE     (User → Menu) : 마지막 섭취 타임스탬프 (timestamp: datetime)

선호도(P_i):
  P_i = rating / 3.0  →  1★=0.33, 3★=1.0(중립), 5★=1.67
  PREFERS 없으면 기본값 1.0 (3★ 중립과 동등)

시간 감쇠(D_i):
  D_i = e^{-λ·Δt}  (직접 ATE일 때만, Δt = 경과 일수)
  ATE 없으면 D_i = 0

추천 점수:
  Score_KG(i) = P_i × (1 - D_i)  ∈ [0, max_preference]

f4 오차율:
  f4 = (max_score - avg_score) / max_score  ∈ [0, 1]
  max_score = 최대 PREFERS 가중치 (기본 1.0 포함)
"""

from __future__ import annotations

import math
from datetime import datetime

try:
    import networkx as nx
except ImportError as exc:
    raise ImportError(
        "KGManager requires 'networkx'. Install with `pip install networkx`."
    ) from exc


def make_menu_id(item: dict) -> str:
    """food_master 아이템 dict에서 유니크 메뉴 ID를 생성한다.

    우선순위:
      1) item['id']   — Supabase UUID
      2) "product_name|brand_name"
      3) product_name / menu_name
    """
    raw_id = item.get("id")
    if raw_id:
        raw_id_str = str(raw_id).strip()
        if raw_id_str:
            return raw_id_str
    name = str(item.get("product_name") or item.get("menu_name") or "")
    brand = str(item.get("brand_name") or "")
    if name and brand:
        return f"{name}|{brand}"
    return name


class KGManager:
    """NetworkX MultiDiGraph 기반 지식 그래프 (User ↔ Menu 관계만)."""

    def __init__(self) -> None:
        self.G: nx.MultiDiGraph = nx.MultiDiGraph()

    # ------------------------------------------------------------------
    # 그래프 구성
    # ------------------------------------------------------------------

    def add_menu(self, menu_id: str) -> None:
        """메뉴 노드 등록."""
        self.G.add_node(menu_id, type="menu")

    def set_rating(self, user_id: str, menu_id: str, rating: int) -> None:
        """별점(1~5)을 선호도 가중치로 변환하여 PREFERS 엣지 추가/갱신.

        P_i = rating / 3.0  →  1★=0.33, 3★=1.0(중립), 5★=1.67
        """
        if not (1 <= rating <= 5):
            raise ValueError(f"rating must be 1~5, got {rating}")
        self.set_preference(user_id, menu_id, rating / 3.0)

    def set_preference(self, user_id: str, menu_id: str, weight: float) -> None:
        """PREFERS 엣지 추가/갱신."""
        self.G.add_node(user_id, type="user")
        if self.G.has_edge(user_id, menu_id, key="PREFERS"):
            self.G[user_id][menu_id]["PREFERS"]["weight"] = float(weight)
        else:
            self.G.add_edge(user_id, menu_id, key="PREFERS", weight=float(weight))

    def record_eating(self, user_id: str, menu_id: str, timestamp: datetime) -> None:
        """ATE 엣지 추가/갱신 — 더 최근 타임스탬프로 갱신.

        Args:
            timestamp: tz-aware인 경우 tzinfo를 제거하고 naive로 정규화.
        """
        if timestamp.tzinfo is not None:
            timestamp = timestamp.replace(tzinfo=None)
        self.G.add_node(user_id, type="user")
        self.G.add_node(menu_id, type="menu")

        if self.G.has_edge(user_id, menu_id, key="ATE"):
            existing = self.G[user_id][menu_id]["ATE"]["timestamp"]
            self.G[user_id][menu_id]["ATE"]["timestamp"] = max(existing, timestamp)
        else:
            self.G.add_edge(user_id, menu_id, key="ATE", timestamp=timestamp)

    # ------------------------------------------------------------------
    # 점수 계산
    # ------------------------------------------------------------------

    def get_score(
        self,
        user_id: str,
        menu_id: str,
        lambda_decay: float = 0.5,
        now: datetime | None = None,
    ) -> float:
        """추천 점수 Score_KG(i) = P_i × (1 - D_i).

        Args:
            now: 시뮬레이션 기준 시각 (naive datetime). None이면 datetime.now().

        Returns:
            Score ∈ [0, max_preference].
        """
        if now is None:
            now = datetime.now()
        elif now.tzinfo is not None:
            raise TypeError("get_score(now=...) expects naive datetime.")

        # ── P_i: 메뉴 직접 PREFERS, 없으면 1.0 ─────────────────────────
        preference = 1.0
        if self.G.has_edge(user_id, menu_id, key="PREFERS"):
            preference = float(self.G[user_id][menu_id]["PREFERS"].get("weight", 1.0))

        # ── D_i: 직접 ATE일 때만 e^{-λΔt} ──────────────────────────────
        decay = 0.0
        if self.G.has_edge(user_id, menu_id, key="ATE"):
            ts = self.G[user_id][menu_id]["ATE"].get("timestamp")
            if ts:
                delta_days = max(0.0, (now - ts).total_seconds() / 86400.0)
                decay = math.exp(-lambda_decay * delta_days)
        decay = min(1.0, max(0.0, decay))

        return max(0.0, preference * (1.0 - decay))

    def max_possible_score(self, user_id: str) -> float:
        """이론상 최대 추천 점수 = 최대 PREFERS 가중치 (기본 1.0 포함)."""
        weights: list[float] = [1.0]
        if not self.G.has_node(user_id):
            return 1.0
        for _, _, key, edata in self.G.out_edges(user_id, keys=True, data=True):
            if key == "PREFERS":
                weights.append(float(edata.get("weight", 1.0)))
        return max(weights)

    # ------------------------------------------------------------------
    # 팩토리
    # ------------------------------------------------------------------

    @classmethod
    def from_config(
        cls,
        all_foods: list[dict],
        kg_cfg: dict,
        user_id: str = "user_0",
    ) -> "KGManager":
        """YAML kg 섹션으로 KGManager 구성.

        kg_cfg 예시:
          preferences:
            <menu_id>: 4        # 별점 1~5 → set_rating()
            <menu_id>: 1.33     # raw weight → set_preference()
          user_history:
            - menu_id: "비빔밥"
              timestamp: "2026-04-25T12:00:00"
        """
        kg = cls()

        alias_to_menu_ids: dict[str, set[str]] = {}

        for item in all_foods:
            mid = make_menu_id(item)
            if mid:
                kg.add_menu(mid)
                for alias in (
                    item.get("id"),
                    item.get("product_name"),
                    item.get("menu_name"),
                ):
                    alias_str = str(alias or "").strip()
                    if alias_str:
                        alias_to_menu_ids.setdefault(alias_str, set()).add(mid)

        def _resolve(raw: str) -> str:
            mapped = alias_to_menu_ids.get(str(raw).strip())
            if mapped and len(mapped) == 1:
                return next(iter(mapped))
            return str(raw).strip()

        # 선호도 설정 — int(1~5)면 별점, float이면 raw weight
        for target_id, value in (kg_cfg.get("preferences") or {}).items():
            mid = _resolve(str(target_id))
            if isinstance(value, int) and 1 <= value <= 5:
                kg.set_rating(user_id, mid, value)
            else:
                kg.set_preference(user_id, mid, float(value))

        # 섭취 이력 등록
        n_failed = 0
        for record in (kg_cfg.get("user_history") or []):
            mid = _resolve(str(record.get("menu_id", "")))
            ts_str = str(record.get("timestamp", ""))
            if mid and ts_str:
                try:
                    kg.record_eating(user_id, mid, datetime.fromisoformat(ts_str))
                except ValueError:
                    n_failed += 1

        if n_failed > 0:
            import warnings
            warnings.warn(
                f"KGManager.from_config: {n_failed} user_history record(s) failed.",
                UserWarning, stacklevel=2,
            )

        return kg
