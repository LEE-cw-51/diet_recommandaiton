"""KGManager — NetworkX 기반 지식 그래프 (선호도 + 시간 감쇠).

노드:
  user     : 사용자
  menu     : 후보 메뉴 (product_name / menu_name)
  category : 식품군 (MAIN, SIDE_SOUP, DRINK, SNACK, ...)

엣지 (MultiDiGraph, key로 종류 구분):
  IS_IN   (Menu → Category)         : 정적 분류 관계
  PREFERS (User → Category/Menu)    : 선호도 가중치 (weight: float)
  ATE     (User → Menu)             : 마지막 섭취 타임스탬프 (timestamp: datetime)

  ※ MultiDiGraph로 같은 (user→menu) 쌍에 PREFERS·ATE 동시 저장 가능.

추천 점수 공식:
  Score_KG(i) = P_i × (1 - D_i)
  D_i = max_j( Sim(i,j) × e^{-λ·Δt_j} )
    Sim = 1.0 (직접 ATE), 0.5 (동일 카테고리 형제 메뉴)

f4 오차율:
  f4 = (max_score - avg_score) / max_score  ∈ [0, 1]
  max_score = 최대 PREFERS 가중치 (감쇠 없음 기준)

성능 최적화:
  - _menu_to_category : 메뉴 ID → 카테고리 O(1) 조회
  - _ate_by_category  : 카테고리 → {menu_id: timestamp} 빠른 형제 탐색
"""

from __future__ import annotations

import math
from datetime import datetime

try:
    import networkx as nx
except ImportError as exc:
    raise ImportError(
        "KGManager requires the optional dependency 'networkx'. "
        "Install it with `pip install networkx` and try again."
    ) from exc


class KGManager:
    """NetworkX MultiDiGraph 기반 지식 그래프."""

    def __init__(self) -> None:
        self.G: nx.MultiDiGraph = nx.MultiDiGraph()
        # 성능 인덱스
        self._menu_to_category: dict[str, str] = {}
        # (user_id → category → {menu_id: timestamp}) — 형제 탐색 가속
        self._ate_by_category: dict[str, dict[str, dict[str, datetime]]] = {}

    # ------------------------------------------------------------------
    # 그래프 구성
    # ------------------------------------------------------------------

    def add_menu(self, menu_id: str, category: str) -> None:
        """메뉴 노드 + IS_IN 엣지 추가."""
        self.G.add_node(menu_id, type="menu")
        self.G.add_node(category, type="category")
        if not self.G.has_edge(menu_id, category, key="IS_IN"):
            self.G.add_edge(menu_id, category, key="IS_IN")
        self._menu_to_category[menu_id] = category

    def set_preference(self, user_id: str, target_id: str, weight: float) -> None:
        """PREFERS 엣지 추가/갱신. target은 메뉴 ID 또는 카테고리명."""
        self.G.add_node(user_id, type="user")
        # MultiDiGraph: 동일 key="PREFERS" 엣지가 있으면 weight만 갱신
        if self.G.has_edge(user_id, target_id, key="PREFERS"):
            self.G[user_id][target_id]["PREFERS"]["weight"] = float(weight)
        else:
            self.G.add_edge(user_id, target_id, key="PREFERS", weight=float(weight))

    def record_eating(self, user_id: str, menu_id: str, timestamp: datetime) -> None:
        """ATE 엣지 추가/갱신 — 더 최근 타임스탬프로 갱신.

        PREFERS 엣지와 충돌 없음 (MultiDiGraph + 다른 key 사용).
        """
        self.G.add_node(user_id, type="user")
        self.G.add_node(menu_id, type="menu")

        if self.G.has_edge(user_id, menu_id, key="ATE"):
            existing = self.G[user_id][menu_id]["ATE"]["timestamp"]
            new_ts = max(existing, timestamp)
            self.G[user_id][menu_id]["ATE"]["timestamp"] = new_ts
        else:
            self.G.add_edge(user_id, menu_id, key="ATE", timestamp=timestamp)
            new_ts = timestamp

        # 인덱스 갱신
        cat = self._menu_to_category.get(menu_id)
        if cat:
            user_idx = self._ate_by_category.setdefault(user_id, {})
            cat_idx  = user_idx.setdefault(cat, {})
            cat_idx[menu_id] = new_ts

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

        반환값은 [0, max_preference] 범위로 클리핑되어 음수가 나오지 않음.
        """
        if now is None:
            now = datetime.now()

        # ── 1) 선호도(P_i) ───────────────────────────────────────
        preference = 1.0
        # 1-a) 메뉴 직접 PREFERS
        if self.G.has_edge(user_id, menu_id, key="PREFERS"):
            preference = float(self.G[user_id][menu_id]["PREFERS"].get("weight", 1.0))
        else:
            # 1-b) 카테고리 PREFERS (IS_IN 전파)
            cat = self._menu_to_category.get(menu_id)
            if cat and self.G.has_edge(user_id, cat, key="PREFERS"):
                preference = float(self.G[user_id][cat]["PREFERS"].get("weight", 1.0))

        # ── 2) 시간 감쇠(D_i) — D_i = max_j(Sim·e^{-λΔt}), Δt ≥ 0 ────
        decay = 0.0

        # 2-a) 직접 ATE (Sim = 1.0)
        if self.G.has_edge(user_id, menu_id, key="ATE"):
            ts = self.G[user_id][menu_id]["ATE"].get("timestamp")
            if ts:
                delta_days = max(0.0, (now - ts).total_seconds() / 86400.0)
                decay = max(decay, math.exp(-lambda_decay * delta_days))

        # 2-b) 동일 카테고리 형제 메뉴 ATE (Sim = 0.5)
        cat = self._menu_to_category.get(menu_id)
        if cat:
            sibling_ate = (self._ate_by_category.get(user_id, {}).get(cat, {}))
            for sib_id, sib_ts in sibling_ate.items():
                if sib_id == menu_id:
                    continue
                delta_days = max(0.0, (now - sib_ts).total_seconds() / 86400.0)
                decay = max(decay, 0.5 * math.exp(-lambda_decay * delta_days))

        # decay ∈ [0, 1] 보장 (Δt 음수 방지로 이미 보장되지만 안전)
        decay = min(1.0, max(0.0, decay))
        return preference * (1.0 - decay)

    def max_possible_score(self, user_id: str) -> float:
        """이론상 최대 추천 점수 = 최대 PREFERS 가중치 (감쇠 없음 기준).

        PREFERS 엣지가 없으면 기본값 1.0 반환.
        """
        weights: list[float] = []
        if not self.G.has_node(user_id):
            return 1.0
        for _, _, key, edata in self.G.out_edges(user_id, keys=True, data=True):
            if key == "PREFERS":
                weights.append(float(edata.get("weight", 1.0)))
        return max(weights) if weights else 1.0

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
          user_id: user_0
          lambda_decay: 0.5
          preferences:
            MAIN: 1.2
            DRINK: 0.8
          user_history:
            - menu_id: "비빔밥"
              timestamp: "2026-04-25T12:00:00"
        """
        kg = cls()

        # 전체 음식 메뉴 노드 등록
        for item in all_foods:
            mid = str(item.get("product_name") or item.get("menu_name") or "")
            cat = item.get("category", "UNKNOWN")
            if mid:
                kg.add_menu(mid, cat)

        # 선호도 설정
        for target_id, weight in (kg_cfg.get("preferences") or {}).items():
            kg.set_preference(user_id, str(target_id), float(weight))

        # 섭취 이력 등록
        for record in (kg_cfg.get("user_history") or []):
            mid = str(record.get("menu_id", ""))
            ts_str = str(record.get("timestamp", ""))
            if mid and ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str)
                    kg.record_eating(user_id, mid, ts)
                except ValueError:
                    pass

        return kg
