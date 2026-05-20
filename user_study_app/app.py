"""A/B 유저 스터디 Streamlit 앱 v2.

변경 사항:
  - 연구 참여 동의서 추가 (Step 0)
  - 모바일 최적화: 탭 + 카드형 식단 표시
  - Likert 5점 척도 레이블 (매우 아니다 ~ 매우 그렇다)
  - 전반적 선호도 제거 (4단계 A/B 선택과 통합)

로컬 실행:
  streamlit run user_study_app/app.py

배포:
  Streamlit Community Cloud — Secrets에 SUPABASE_URL, SUPABASE_KEY 등록
"""

from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path

import pandas as pd
import streamlit as st

# ── 경로 설정 ────────────────────────────────────────────────────────────────────
_APP_DIR  = Path(__file__).parent
_DATA_DIR = _APP_DIR.parent / "experiment" / "results" / "user_study"
CUISINES  = ["한식", "중식", "일식", "양식"]

LIKERT = ["매우 아니다", "아니다", "보통", "그렇다", "매우 그렇다"]  # 1~5 매핑

SCENARIOS = {
    "한식": "두 가지(식단 A / 식단 B) 7일치 식단을 보고 설문에 응답해주세요.",
    "중식": "두 가지(식단 A / 식단 B) 7일치 식단을 보고 설문에 응답해주세요.",
    "일식": "두 가지(식단 A / 식단 B) 7일치 식단을 보고 설문에 응답해주세요.",
    "양식": "두 가지(식단 A / 식단 B) 7일치 식단을 보고 설문에 응답해주세요.",
}


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
    cuisine_dir = _DATA_DIR / cuisine
    try:
        df_a = pd.read_csv(cuisine_dir / f"{set_id}_A.csv", encoding="utf-8-sig")
        df_b = pd.read_csv(cuisine_dir / f"{set_id}_B.csv", encoding="utf-8-sig")
        meta = json.loads((cuisine_dir / f"{set_id}_meta.json").read_text(encoding="utf-8"))
        return df_a, df_b, meta
    except FileNotFoundError:
        return None


def _available_sets(cuisine: str) -> list[str]:
    cuisine_dir = _DATA_DIR / cuisine
    if not cuisine_dir.exists():
        return []
    metas = sorted(cuisine_dir.glob("set_*_meta.json"))
    return [m.stem.replace("_meta", "") for m in metas]


# ── UI 컴포넌트 ──────────────────────────────────────────────────────────────────

def _render_diet_cards(df: pd.DataFrame) -> None:
    """7일치 식단을 날짜별 카드(expander)로 표시 — 모바일 최적화."""
    meal_labels = {"breakfast": "🌅 아침", "lunch": "☀️ 점심", "dinner": "🌙 저녁"}
    for _, row in df.iterrows():
        day   = int(row["day"])
        cal   = int(row.get("total_calories", 0))
        price = int(row.get("total_price", 0))
        with st.expander(f"**{day}일차**", expanded=(day == 1)):
            for col, label in meal_labels.items():
                menus = str(row.get(col, "")).strip()
                if menus:
                    st.markdown(f"{label}: {menus}")
            st.caption(f"🔥 {cal:,} kcal  |  💰 {price:,}원")


def _likert_radio(question: str, key: str) -> int:
    """Likert 5점 척도 라디오 버튼. 반환값: 1~5."""
    st.markdown(f"**{question}**")
    choice = st.radio(
        label=question,
        options=LIKERT,
        index=2,          # 기본값: "보통"
        horizontal=True,
        key=key,
        label_visibility="collapsed",
    )
    return LIKERT.index(choice) + 1  # 1~5


# ── 응답 저장 ────────────────────────────────────────────────────────────────────

def _save_response(
    cuisine: str,
    set_id: str,
    chosen_overall: str,
    diversity_winner: str,
    nutrition_winner: str,
    response_time_seconds: int | None = None,
    phone_number: str | None = None,
) -> bool:
    sb = _get_supabase()
    if sb is None:
        st.error("Supabase 연결 실패. SUPABASE_URL / SUPABASE_KEY를 확인하세요.")
        return False
    try:
        data: dict = {
            "cuisine":          cuisine,
            "set_id":           set_id,
            "chosen_overall":   chosen_overall,
            "diversity_winner": diversity_winner,
            "nutrition_winner": nutrition_winner,
        }
        if response_time_seconds is not None:
            data["response_time_seconds"] = response_time_seconds
        if phone_number:
            data["phone_number"] = phone_number.strip()
        sb.table("user_study_responses").insert(data).execute()
        return True
    except Exception as e:
        st.error(f"저장 오류: {e}")
        return False


# ── 메인 앱 ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="식단 선호도 조사",
        page_icon="🍱",
        layout="centered",   # 모바일 최적화
    )

    # ── Streamlit 배포자 배지 숨기기 ─────────────────────────────────────────────
    st.markdown("""
        <style>
        [data-testid="stAppViewerBadge"],
        div[class*="viewerBadge"],
        iframe[title="Streamlit App Badge"] { display: none !important; }
        [data-testid="stHeader"] { display: none !important; }
        footer { visibility: hidden !important; }
        </style>
    """, unsafe_allow_html=True)

    # ── 인앱 브라우저 경고 ───────────────────────────────────────────────────────
    st.warning(
        "📱 카카오톡·라인 등 **인앱 브라우저**에서 열린 경우, "
        "우측 상단 메뉴(···)를 눌러 **크롬 또는 사파리로 열기**를 선택해주세요.  \n"
        "인앱 브라우저에서는 응답이 저장되지 않을 수 있습니다."
    )

    # ── 세션 상태 초기화 ─────────────────────────────────────────────────────────
    for key, default in [
        ("consented", False), ("assigned", False),
        ("submitted", False), ("response_start", None),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # ── Step 0: 연구 참여 동의 ───────────────────────────────────────────────────
    st.title("🍱 식단 선호도 조사")
    st.markdown(
        "본 조사는 **식단 추천 알고리즘 연구(졸업논문)**를 위한 **A/B 테스트** 설문입니다.  \n"
        "서로 다른 알고리즘으로 생성된 두 가지 식단(식단 A / 식단 B)을 비교하고,  \n"
        "다양성·영양균형·선호도를 평가해주세요. **(약 3~5분 소요)**"
    )
    st.info(
        "⏰ **설문 기간:** 2026년 5월 20일(수) ~ 5월 24일(일) 23:59  \n"
        "☕ 참여해주신 분 중 **5명을 추첨하여 메가커피 아메리카노**를 드립니다!"
    )

    with st.expander("📋 연구 참여 동의서 확인 (필수)", expanded=not st.session_state.consented):
        st.markdown("""
**연구 제목:** 지식 그래프 기반 다목적 최적화를 활용한 개인화 식단 추천 시스템

**수집 정보:** 식단 평가 점수 및 선호 식문화 (익명, 개인 식별 정보 없음)

**활용 목적:** 본 졸업논문 연구에만 사용되며, 외부 공개 및 상업적 활용 없음

**참여 철회:** 제출 전 언제든 브라우저를 닫으면 참여가 취소됩니다.
        """)
        consent = st.checkbox("위 내용을 확인하였으며, 연구 참여에 동의합니다.", key="consent_check")
        if consent and not st.session_state.consented:
            st.session_state.consented = True
            st.rerun()

    if not st.session_state.consented:
        st.info("동의서에 동의하셔야 조사를 시작할 수 있습니다.")
        st.stop()

    # ── Step 1: 식문화 선택 ──────────────────────────────────────────────────────
    st.divider()
    st.subheader("1단계: 선호하는 식문화를 선택해주세요")
    cuisine = st.radio("식문화", CUISINES, horizontal=True, key="cuisine_radio",
                       disabled=st.session_state.assigned)

    if not st.session_state.assigned:
        st.info(SCENARIOS.get(cuisine, ""))
        if st.button("식단 배정받기", type="primary"):
            sets = _available_sets(cuisine)
            if not sets:
                st.error(f"'{cuisine}' 식단 데이터가 없습니다. 관리자에게 문의하세요.")
                st.stop()
            chosen_set = random.choice(sets)
            result = _load_set(cuisine, chosen_set)
            if result is None:
                st.error("식단 파일을 불러오지 못했습니다.")
                st.stop()
            st.session_state.df_a    = result[0]
            st.session_state.df_b    = result[1]
            st.session_state.meta    = result[2]
            st.session_state.set_id         = chosen_set
            st.session_state.cuisine        = cuisine
            st.session_state.assigned       = True
            st.session_state.response_start = time.time()
            st.rerun()
        st.stop()

    # 배정 완료 후 시나리오 표시
    cuisine = st.session_state.cuisine
    st.info(SCENARIOS.get(cuisine, ""))

    # ── Step 2: 식단 표시 (탭 — 모바일 최적화) ───────────────────────────────────
    st.divider()
    st.subheader("2단계: 아래 두 식단을 확인해주세요")
    st.caption("각 일차를 눌러 상세 메뉴를 확인하세요.")

    tab_a, tab_b = st.tabs(["🍽 식단 A", "🍽 식단 B"])
    with tab_a:
        _render_diet_cards(st.session_state.df_a)
    with tab_b:
        _render_diet_cards(st.session_state.df_b)

    # ── Step 3: 비교 평가 ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("3단계: 두 식단을 비교해주세요")

    st.markdown("**🔄 7일 동안 어느 식단의 메뉴가 더 다양했나요?**")
    div_choice = st.radio(
        "다양성 비교", ["식단 A", "식단 B"],
        horizontal=True, key="div_winner", label_visibility="collapsed",
    )

    st.markdown("**⚖️ 어느 식단이 더 균형 잡혀 보였나요?**")
    nutr_choice = st.radio(
        "균형 비교", ["식단 A", "식단 B"],
        horizontal=True, key="nutr_winner", label_visibility="collapsed",
    )

    st.markdown("**🙋 어느 식단이 자신의 선호도에 맞나요?**")
    chosen_overall = st.radio(
        "선호도 비교", ["식단 A", "식단 B"],
        horizontal=True, key="overall_choice", label_visibility="collapsed",
    )

    div_winner   = "A" if div_choice     == "식단 A" else "B"
    nutr_winner  = "A" if nutr_choice    == "식단 A" else "B"
    chosen_label = "A" if chosen_overall == "식단 A" else "B"

    # ── 전화번호 수집 (선택) ─────────────────────────────────────────────────────
    st.divider()
    with st.expander("📋 개인정보 수집·이용 안내 (이벤트 참여 시)", expanded=True):
        st.markdown(
            "- **수집 목적:** 졸업논문 유저 스터디 이벤트 상품(기프티콘) 추첨 및 발송  \n"
            "- **수집 항목:** 전화번호 (선택)  \n"
            "- **보유 기간:** 기프티콘 발송 완료 후 **즉시 파기**  \n"
            "- 미입력 시에도 설문 제출이 가능하며, 해당 응답은 이벤트 추첨 대상에서 제외됩니다."
        )

    phone_raw = st.text_input(
        "📞 추첨용 전화번호 (선택사항, 숫자만)",
        placeholder="01012345678",
        max_chars=11,
        key="phone_input",
    )
    phone_raw = phone_raw.strip()
    if phone_raw and not phone_raw.isdigit():
        st.warning("숫자만 입력해주세요.")
    phone = phone_raw if (phone_raw.isdigit() and len(phone_raw) >= 10) else ""

    # ── 제출 ─────────────────────────────────────────────────────────────────────
    st.divider()
    if not st.session_state.submitted:
        if st.button("제출하기 ✅", type="primary"):
            elapsed = (int(time.time() - st.session_state.response_start)
                       if st.session_state.response_start else None)
            ok = _save_response(
                cuisine                = cuisine,
                set_id                 = st.session_state.set_id,
                chosen_overall         = chosen_label,
                diversity_winner       = div_winner,
                nutrition_winner       = nutr_winner,
                response_time_seconds  = elapsed,
                phone_number           = phone or None,
            )
            if ok:
                st.session_state.submitted = True
                st.rerun()
    else:
        st.success("응답이 저장되었습니다. 참여해 주셔서 감사합니다! 🙏")
        st.balloons()


if __name__ == "__main__":
    main()
