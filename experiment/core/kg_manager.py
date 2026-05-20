"""KGManager — NetworkX 기반 지식 그래프 (사용자-메뉴 관계만).

노드:
  user : 사용자
  menu : 후보 메뉴 (product_name / menu_name)

엣지 (DiGraph):
  User → Menu : { 'pref': float }
    - pref : 선호도 가중치 (별점 기반, weight = rating / 3.0). 없으면 1.0.

섭취 이력 (_intake_log):
  선호도 엣지와 독립적으로 관리되는 별도 리스트.
  list[tuple[user_id, menu_id, datetime]]
  record_eating() 호출 시에만 기록되며, 엣지 생성과 무관하다.

선호도(P_i):
  P_i = rating / 3.0  →  1★=0.33, 3★=1.0(중립), 5★=1.67
  엣지에 pref가 없으면 기본값 1.0 (3★ 중립과 동등)

시간 감쇠(D_time):
  D_time = e^{-λ·Δt}  (_intake_log의 last_ate 있을 때만, Δt = 경과 일수)
  섭취 이력 없으면 D_time = 0 → 선호도 점수 그대로 반영

당일 중복 페널티(D_dup) — get_batch_diet_score 한정:
  D_dup = 1.0 if 같은 식단 리스트 안에서 이미 등장한 메뉴, 아니면 0

추천 점수:
  D_i = max(D_time, D_dup)
  Score_KG(i) = P_i × (1 - D_i)  ∈ [0, max_preference]

f4 오차율:
  f4 = (max_score - avg_score) / max_score  ∈ [0, 1]
  max_score = max([1.0] + 모든 pref 값) → 항상 ≥ 1.0
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
    """NetworkX DiGraph 기반 지식 그래프 (User ↔ Menu, 단일 엣지)."""

    def __init__(self) -> None:
        self.G: nx.DiGraph = nx.DiGraph()
        self._intake_log: list[tuple[str, str, datetime]] = []

    # ------------------------------------------------------------------
    # 그래프 구성
    # ------------------------------------------------------------------

    def add_menu(self, menu_id: str, category: str = "UNKNOWN", cuisine: str | None = None) -> None:
        """메뉴 노드 등록. category(5-class)와 cuisine(식문화) 정보 저장."""
        self.G.add_node(menu_id, type="menu", category=category, cuisine=cuisine)

    def set_rating(self, user_id: str, menu_id: str, rating: int) -> None:
        """별점(1~5)을 선호도 가중치로 변환하여 엣지 pref 속성 추가/갱신.

        P_i = rating / 3.0  →  1★=0.33, 3★=1.0(중립), 5★=1.67
        """
        if not (1 <= rating <= 5):
            raise ValueError(f"rating must be 1~5, got {rating}")
        self.set_preference(user_id, menu_id, rating / 3.0)

    def set_preference(self, user_id: str, menu_id: str, weight: float) -> None:
        """엣지 pref 속성 추가/갱신 (기존 last_ate는 보존)."""
        self.G.add_node(user_id, type="user")
        self.G.add_node(menu_id, type="menu")
        if self.G.has_edge(user_id, menu_id):
            self.G[user_id][menu_id]["pref"] = float(weight)
        else:
            self.G.add_edge(user_id, menu_id, pref=float(weight))

    def record_eating(self, user_id: str, menu_id: str, timestamp: datetime) -> None:
        """섭취 이력을 _intake_log에 추가 (선호도 엣지와 독립).

        Args:
            timestamp: tz-aware인 경우 tzinfo를 제거하고 naive로 정규화.
        """
        if timestamp.tzinfo is not None:
            timestamp = timestamp.replace(tzinfo=None)
        self._intake_log.append((user_id, menu_id, timestamp))

    def _get_last_ate(self, user_id: str, menu_id: str) -> datetime | None:
        """_intake_log에서 해당 (user, menu) 쌍의 가장 최근 섭취 시각 반환."""
        times = [t for u, m, t in self._intake_log if u == user_id and m == menu_id]
        return max(times) if times else None

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
        """단일 메뉴 추천 점수 Score_KG(i) = P_i × (1 - D_time).

        Args:
            now: 시뮬레이션 기준 시각 (naive datetime). None이면 datetime.now().

        Returns:
            Score ∈ [0, max_preference].
        """
        if now is None:
            now = datetime.now()
        elif now.tzinfo is not None:
            raise TypeError("get_score(now=...) expects naive datetime.")

        edata = self.G.get_edge_data(user_id, menu_id, default={})
        pref = float(edata.get("pref", 1.0))
        last_ate = self._get_last_ate(user_id, menu_id)

        decay = 0.0
        if last_ate is not None:
            delta_days = max(0.0, (now - last_ate).total_seconds() / 86400.0)
            decay = math.exp(-lambda_decay * delta_days)
        decay = min(1.0, max(0.0, decay))

        return max(0.0, pref * (1.0 - decay))

    def get_batch_diet_score(
        self,
        user_id: str,
        menu_ids: list[str],
        lambda_decay: float = 0.5,
        now: datetime | None = None,
    ) -> float:
        """하루 식단 리스트의 평균 조정 점수 mean(S_i).

        중복 메뉴는 두 번째 등장부터 D_dup=1.0 강제 → S_i=0 (당일 다양성 페널티).
        f4 = (max_score - avg) / max_score 변환은 호출 측 책임.

        Args:
            menu_ids: 식단 메뉴 ID 리스트 (순서대로 평가).
            now: 시뮬레이션 기준 시각 (naive). None이면 datetime.now().

        Returns:
            avg_score ∈ [0, max_preference].
        """
        if not menu_ids:
            return 0.0
        if now is None:
            now = datetime.now()
        elif now.tzinfo is not None:
            raise TypeError("get_batch_diet_score(now=...) expects naive datetime.")

        seen: set[str] = set()
        total = 0.0
        for mid in menu_ids:
            edata = self.G.get_edge_data(user_id, mid, default={})
            pref = float(edata.get("pref", 1.0))

            if mid in seen:
                decay = 1.0
            else:
                last_ate = self._get_last_ate(user_id, mid)
                if last_ate is not None:
                    delta_days = max(0.0, (now - last_ate).total_seconds() / 86400.0)
                    decay = min(1.0, math.exp(-lambda_decay * delta_days))
                else:
                    decay = 0.0

            seen.add(mid)
            total += max(0.0, pref * (1.0 - decay))

        return total / len(menu_ids)

    def max_possible_score(self, user_id: str) -> float:
        """이론상 최대 추천 점수 = max([1.0] + 모든 pref 값). 항상 ≥ 1.0."""
        if not self.G.has_node(user_id):
            return 1.0
        weights: list[float] = [1.0]
        for _, _, data in self.G.out_edges(user_id, data=True):
            if "pref" in data:
                weights.append(float(data["pref"]))
        return max(weights)

    def set_category_preference(
        self,
        user_id: str,
        category: str,
        weight: float,
        all_menus: list[str] | None = None,
    ) -> int:
        """카테고리(5-class)에 속한 모든 메뉴에 선호도 엣지 생성.

        Returns:
            선호도 엣지를 생성한 메뉴 개수.
        """
        if all_menus is None:
            all_menus = [
                node for node, attr in self.G.nodes(data=True)
                if attr.get("type") == "menu" and attr.get("category") == category
            ]
        for menu_id in all_menus:
            self.set_preference(user_id, menu_id, weight)
        return len(all_menus)

    def set_cuisine_preference(
        self,
        user_id: str,
        cuisine: str,
        weight: float,
        all_menus: list[str] | None = None,
    ) -> int:
        """식문화(한식/일식/중식/양식/분식 등)에 속한 모든 메뉴에 선호도 엣지 생성.

        Returns:
            선호도 엣지를 생성한 메뉴 개수.
        """
        if all_menus is None:
            all_menus = [
                node for node, attr in self.G.nodes(data=True)
                if attr.get("type") == "menu" and attr.get("cuisine") == cuisine
            ]
        for menu_id in all_menus:
            self.set_preference(user_id, menu_id, weight)
        return len(all_menus)

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
