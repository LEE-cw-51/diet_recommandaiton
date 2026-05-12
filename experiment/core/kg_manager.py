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

선호도(P_i):
  별점(1~5) 기반: P_i = rating / 3.0
    1★ → 0.33, 3★ → 1.0(중립), 5★ → 1.67
  카테고리 PREFERS가 없으면 기본값 1.0 (3★ 중립과 동등)
  set_rating()으로 별점 입력 → set_preference()로 내부 저장

추천 점수 공식:
  Score_KG(i) = P_i × (1 - D_i)
  D_i = e^{-λ·Δt}  (직접 ATE일 때만, Δt = 경과 일수)
  슬롯이 카테고리별로 고정(MAIN/SIDE_SOUP/DRINK)되므로 형제 메뉴 유사도 불필요.

f4 오차율:
  f4 = (max_score - avg_score) / max_score  ∈ [0, 1]
  max_score = 최대 PREFERS 가중치 (감쇠 없음 기준, 기본 1.0 포함)

성능 최적화:
  - _menu_to_category : 메뉴 ID → 카테고리 O(1) 조회
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
    if raw_id:
        raw_id_str = str(raw_id).strip()
        if raw_id_str:  # 빈 string / whitespace 제외
            return raw_id_str
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

    def set_rating(self, user_id: str, target_id: str, rating: int) -> None:
        """별점(1~5)을 선호도 가중치로 변환하여 PREFERS 엣지 추가/갱신.

        P_i = rating / 3.0  →  1★=0.33, 3★=1.0(중립), 5★=1.67
        """
        if not (1 <= rating <= 5):
            raise ValueError(f"rating must be 1~5, got {rating}")
        self.set_preference(user_id, target_id, rating / 3.0)

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

        Args:
            timestamp: 메뉴 섭취 시각. tz-aware 또는 naive 모두 가능.
                       tz-aware인 경우 UTC offset을 제거하고 naive로 정규화.
                       (get_score()의 now와 Δt 계산 일관성 보장)

        Note:
            PREFERS 엣지와 충돌 없음 (MultiDiGraph + key 분리).
            timezone 정규화:
              tz-aware "2026-04-25 12:00:00+09:00"
                → remove tzinfo → naive "2026-04-25 12:00:00"
                → get_score(now=datetime.now())과 일관된 Δt 계산
        """
        # tz-aware → naive 정규화 (tzinfo 제거, UTC offset은 무시)
        # 이 방식은 offset 보존이 필요 없고, get_score()의 datetime.now()와
        # 비교 가능한 naive datetime만 필요한 경우에 적합함.
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
            now: 시뮬레이션 기준 시각 (반드시 naive datetime, tzinfo=None).
                 None이면 datetime.now() 사용 (로컬 시간, naive).
                 record_eating()의 timestamp도 naive로 정규화되므로
                 Δt = (now - ts)의 계산이 일관성 있게 수행됨.
                 tz-aware datetime을 넘기면 TypeError 발생.

        Returns:
            Score ∈ [0, max_preference]. 항상 음수가 아님.
        """
        if now is None:
            now = datetime.now()  # naive datetime (로컬 시간)
        elif now.tzinfo is not None:
            raise TypeError(
                f"get_score(now=...) expects naive datetime, but got tzinfo={now.tzinfo}. "
                "Use datetime.now() or datetime.fromisoformat(ts_str) without timezone."
            )

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

        # ── 2) 시간 감쇠(D_i) — D_i = e^{-λΔt} (직접 ATE일 때만) ─────────
        # 슬롯이 카테고리별로 고정(MAIN/SIDE_SOUP/DRINK)되므로 형제 유사도 불필요.
        decay = 0.0
        if self.G.has_edge(user_id, menu_id, key="ATE"):
            ts = self.G[user_id][menu_id]["ATE"].get("timestamp")
            if ts:
                delta_days = max(0.0, (now - ts).total_seconds() / 86400.0)
                decay = math.exp(-lambda_decay * delta_days)
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
                    alias_str = str(alias or "").strip()
                    if alias_str:
                        alias_to_menu_ids.setdefault(alias_str, set()).add(mid)

        def _normalize_target_id(raw_target_id: str) -> str:
            target_id = str(raw_target_id).strip()
            mapped_ids = alias_to_menu_ids.get(target_id)
            if mapped_ids and len(mapped_ids) == 1:
                return next(iter(mapped_ids))
            # 매핑 실패 시 원본 ID 반환 (명시적 주석)
            if mapped_ids and len(mapped_ids) > 1:
                # 하나의 alias가 여러 메뉴에 매핑됨 (보통 발생하지 않음)
                pass
            return target_id

        # 선호도 설정 — 정수(1~5)면 별점으로 해석, float이면 raw weight로 저장
        n_prefs_set = 0
        for target_id, value in (kg_cfg.get("preferences") or {}).items():
            tid = _normalize_target_id(str(target_id))
            if isinstance(value, int) and 1 <= value <= 5:
                kg.set_rating(user_id, tid, value)
            else:
                kg.set_preference(user_id, tid, float(value))
            n_prefs_set += 1

        # 섭취 이력 등록 — timestamp를 UTC 기준 naive datetime으로 정규화
        n_history_added = 0
        n_history_failed = 0
        for record in (kg_cfg.get("user_history") or []):
            mid = _normalize_target_id(str(record.get("menu_id", "")))
            ts_str = str(record.get("timestamp", ""))
            if mid and ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str)
                    # record_eating()이 tz-aware → naive로 정규화하므로
                    # record.get("timestamp")의 timezone 정보는 무시됨.
                    # (시뮬레이션/테스트 시 sim_now의 timezone과 일치하도록 UTC 기준 해석)
                    kg.record_eating(user_id, mid, ts)
                    n_history_added += 1
                except ValueError:
                    n_history_failed += 1

        if n_history_failed > 0:
            import warnings
            warnings.warn(
                f"KGManager.from_config: {n_history_failed} user_history record(s) "
                f"failed to parse (invalid timestamp format or menu_id not found)",
                UserWarning,
                stacklevel=2,
            )

        return kg
