"""A/B 유저 스터디 Streamlit 앱.

사용자 흐름:
  1. 선호 식문화 선택
  2. 해당 식문화의 세트 중 하나 랜덤 배정
  3. A / B 식단 7일치 나란히 표시
  4. 3가지 기준 평가 (1~5점): 다양성, 영양균형 체감, 전반적 선호도
  5. 제출 → Supabase user_study_responses 저장

로컬 실행:
  streamlit run user_study_app/app.py

배포:
  Streamlit Community Cloud — GitHub 연결 후 Secrets에 SUPABASE_URL, SUPABASE_KEY 등록
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

import pandas as pd
import streamlit as st

# ── 경로 설정 ────────────────────────────────────────────────────────────────────
# app.py 위치 기준 상위 디렉토리의 experiment/results/user_study
_APP_DIR    = Path(__file__).parent
_DATA_DIR   = _APP_DIR.parent / "experiment" / "results" / "user_study"
CUISINES    = ["한식", "중식", "일식", "양식"]

# ── Supabase 클라이언트 ──────────────────────────────────────────────────────────

@st.cache_resource
def _get_supabase():
    try:
        from supabase import create_client
        url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY", "")
        if not url or not key:
            return None
        return create_client(url, key)
    except Exception:
        return None


# ── 데이터 로딩 ──────────────────────────────────────────────────────────────────

def _load_set(cuisine: str, set_id: str) -> tuple[pd.DataFrame, pd.DataFrame, dict] | None:
    """A/B CSV + meta.json 로드. 파일 없으면 None."""
    cuisine_dir = _DATA_DIR / cuisine
    try:
        df_a  = pd.read_csv(cuisine_dir / f"{set_id}_A.csv", encoding="utf-8-sig")
        df_b  = pd.read_csv(cuisine_dir / f"{set_id}_B.csv", encoding="utf-8-sig")
        meta  = json.loads((cuisine_dir / f"{set_id}_meta.json").read_text(encoding="utf-8"))
        return df_a, df_b, meta
    except FileNotFoundError:
        return None


def _available_sets(cuisine: str) -> list[str]:
    """해당 식문화 디렉토리에서 사용 가능한 set ID 목록 반환."""
    cuisine_dir = _DATA_DIR / cuisine
    if not cuisine_dir.exists():
        return []
    metas = sorted(cuisine_dir.glob("set_*_meta.json"))
    return [m.stem.replace("_meta", "") for m in metas]


# ── UI 컴포넌트 ──────────────────────────────────────────────────────────────────

def _render_diet_table(df: pd.DataFrame, label: str) -> None:
    """7일치 식단 테이블 렌더링."""
    st.markdown(f"### 식단 {label}")
    display = df[["day", "date", "breakfast", "lunch", "dinner",
                  "total_calories", "total_price"]].copy()
    display.columns = ["일차", "날짜", "아침", "점심", "저녁", "총칼로리(kcal)", "총가격(원)"]
    st.dataframe(display, use_container_width=True, hide_index=True)


def _rating_row(label: str, key_a: str, key_b: str) -> tuple[int, int]:
    """한 평가 기준에 대해 A/B 점수를 나란히 입력받는다."""
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown(f"**{label}**")
    with col2:
        score_a = st.selectbox("식단 A", [1, 2, 3, 4, 5], key=key_a, label_visibility="collapsed")
    with col3:
        score_b = st.selectbox("식단 B", [1, 2, 3, 4, 5], key=key_b, label_visibility="collapsed")
    return score_a, score_b


# ── 응답 저장 ────────────────────────────────────────────────────────────────────

def _save_response(
    cuisine: str,
    set_id: str,
    chosen_overall: str,
    diversity_a: int, diversity_b: int,
    nutrition_a: int, nutrition_b: int,
    overall_a: int,   overall_b: int,
) -> bool:
    sb = _get_supabase()
    if sb is None:
        st.error("Supabase 연결 실패. SUPABASE_URL / SUPABASE_KEY를 확인하세요.")
        return False
    try:
        sb.table("user_study_responses").insert({
            "cuisine":        cuisine,
            "set_id":         set_id,
            "chosen_overall": chosen_overall,
            "diversity_a":    diversity_a,
            "diversity_b":    diversity_b,
            "nutrition_a":    nutrition_a,
            "nutrition_b":    nutrition_b,
            "overall_a":      overall_a,
            "overall_b":      overall_b,
        }).execute()
        return True
    except Exception as e:
        st.error(f"저장 오류: {e}")
        return False


# ── 메인 앱 ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="식단 선호도 조사",
        page_icon="🍱",
        layout="wide",
    )

    st.title("식단 선호도 조사")
    st.markdown(
        "두 가지 7일치 식단을 비교하고, 각 항목을 **1~5점**으로 평가해주세요.  \n"
        "어느 쪽이 더 나은지 이유가 없어도 됩니다. 직관적으로 평가해 주세요."
    )

    # ── 세션 상태 초기화 ─────────────────────────────────────────────────────────
    if "assigned" not in st.session_state:
        st.session_state.assigned  = False
        st.session_state.submitted = False

    # ── Step 1: 식문화 선택 ──────────────────────────────────────────────────────
    st.divider()
    st.subheader("1단계: 선호하는 식문화를 선택해주세요")
    cuisine = st.radio("식문화", CUISINES, horizontal=True, key="cuisine_radio")

    if st.button("식단 배정받기", type="primary", disabled=st.session_state.assigned):
        sets = _available_sets(cuisine)
        if not sets:
            st.error(f"'{cuisine}' 식단 데이터가 없습니다. 관리자에게 문의하세요.")
            st.stop()
        chosen_set = random.choice(sets)
        result = _load_set(cuisine, chosen_set)
        if result is None:
            st.error("식단 파일을 불러오지 못했습니다.")
            st.stop()
        st.session_state.df_a      = result[0]
        st.session_state.df_b      = result[1]
        st.session_state.meta      = result[2]
        st.session_state.set_id    = chosen_set
        st.session_state.assigned  = True
        st.rerun()

    if not st.session_state.assigned:
        st.stop()

    # ── Step 2: 식단 표시 ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("2단계: 아래 두 식단을 확인해주세요")

    col_a, col_b = st.columns(2)
    with col_a:
        _render_diet_table(st.session_state.df_a, "A")
    with col_b:
        _render_diet_table(st.session_state.df_b, "B")

    # ── Step 3: 평가 ─────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("3단계: 각 항목을 평가해주세요 (1점: 매우 낮음 / 5점: 매우 높음)")

    header_cols = st.columns([2, 1, 1])
    with header_cols[1]:
        st.markdown("**식단 A**")
    with header_cols[2]:
        st.markdown("**식단 B**")

    div_a, div_b   = _rating_row("🔄 다양성 — 7일 동안 메뉴가 얼마나 다양했나요?",
                                  "div_a", "div_b")
    nutr_a, nutr_b = _rating_row("⚖️ 영양균형 체감 — 균형 잡힌 식단처럼 느껴졌나요?",
                                  "nutr_a", "nutr_b")
    ovr_a, ovr_b   = _rating_row("❤️ 전반적 선호도 — 실제로 먹고 싶은 식단은?",
                                  "ovr_a", "ovr_b")

    st.divider()
    st.subheader("4단계: 전반적으로 어느 식단이 더 마음에 드나요?")
    chosen_overall = st.radio("최종 선택", ["A", "B"], horizontal=True, key="overall_choice")

    # ── Step 4: 제출 ─────────────────────────────────────────────────────────────
    st.divider()
    if st.button("제출하기", type="primary", disabled=st.session_state.submitted):
        ok = _save_response(
            cuisine       = cuisine,
            set_id        = st.session_state.set_id,
            chosen_overall= chosen_overall,
            diversity_a   = div_a,   diversity_b = div_b,
            nutrition_a   = nutr_a,  nutrition_b = nutr_b,
            overall_a     = ovr_a,   overall_b   = ovr_b,
        )
        if ok:
            st.session_state.submitted = True
            st.rerun()

    if st.session_state.submitted:
        st.success("응답이 저장되었습니다. 참여해 주셔서 감사합니다! 🙏")
        st.balloons()


if __name__ == "__main__":
    main()
