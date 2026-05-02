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


def make_menu_id(item: dict) -> str:
    """food_master 아이템 dict에서 유니크 메뉴 ID를 생성한다.

    우선순위:
      1) item['id']   — Supabase UUID (가장 유니크)
      2) "product_name|brand_name"  — DB 유니크 키 복합
      3) product_name / menu_name   — fallback

    모든 호출 지점(add_menu, get_score, record_eating)에서 이 함수를 사용하면
    KG 노드 ID가 항상 동일하게 유지된다.
    """
    raw_id = item.get("id")
    if raw_id not in (None, ""):
        return str(raw_id)
    name = str(item.get("product_name") or item.get("menu_name") or "")
    brand = str(item.get("brand_name") or "")
    if name and brand:
        return f"{name}|{brand}"
    return name


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
        timezone-aware datetime은 로컬 시간대로 변환한 뒤 naive로 정규화
        (get_score의 now=datetime.now()와 통일).
        """
        # tz-aware → 로컬 시간대로 변환 후 tz-naive 정규화
        # (오프셋을 보존한 채 now와 비교 가능하게 만듦)
        if timestamp.tzinfo is not None:
            timestamp = timestamp.astimezone().replace(tzinfo=None)
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
        # 음수 weight 방어: preference가 음수여도 score는 0 이상 보장
        score = preference * (1.0 - decay)
        return max(0.0, score)

    def max_possible_score(self, user_id: str) -> float:
        """이론상 최대 추천 점수 = 최대 PREFERS 가중치 (감쇠 없음 기준).

        기본 선호도 1.0을 포함하여 계산 — 모든 weight < 1.0이어도
        기본값 메뉴의 score가 max_s를 초과해 f4가 음수가 되는 것을 방지.
        PREFERS 엣지가 없으면 기본값 1.0 반환.
        """
        weights: list[float] = [1.0]  # 기본 선호도 항상 포함
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

        alias_to_menu_ids: dict[str, set[str]] = {}

        # 전체 음식 메뉴 노드 등록 — make_menu_id() 모듈 함수로 통일
        for item in all_foods:
            mid = make_menu_id(item)
            cat = item.get("category", "UNKNOWN")
            if mid:
                kg.add_menu(mid, cat)

                for alias in (
                    item.get("id"),
                    item.get("product_name"),
                    item.get("menu_name"),
                ):
                    alias_str = str(alias or "")
                    if alias_str:
                        alias_to_menu_ids.setdefault(alias_str, set()).add(mid)

        def _normalize_target_id(raw_target_id: str) -> str:
            target_id = str(raw_target_id)
            mapped_ids = alias_to_menu_ids.get(target_id)
            if mapped_ids and len(mapped_ids) == 1:
                return next(iter(mapped_ids))
            return target_id

        # 선호도 설정
        for target_id, weight in (kg_cfg.get("preferences") or {}).items():
            kg.set_preference(user_id, _normalize_target_id(str(target_id)), float(weight))

        # 섭취 이력 등록
        for record in (kg_cfg.get("user_history") or []):
            mid = _normalize_target_id(str(record.get("menu_id", "")))
            ts_str = str(record.get("timestamp", ""))
            if mid and ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str)
                    # timezone-aware → naive 변환 (datetime.now()와 비교 위해)
                    if ts.tzinfo is not None:
                        ts = ts.replace(tzinfo=None)
                    kg.record_eating(user_id, mid, ts)
                except ValueError:
                    pass

        return kg
