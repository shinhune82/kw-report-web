# -*- coding: utf-8 -*-
"""
app.py — 키워드 리서치 리포트 생성기 (웹 버전)
실행: streamlit run app.py
"""
import os
import tempfile
from datetime import datetime

import pandas as pd
import streamlit as st

import auto_draft
import data_sources
import report_engine
import translate_helper
import web_ops

st.set_page_config(page_title="키워드 리서치 리포트 생성기", layout="wide")

KW_COLUMNS = ["keyword", "volume", "competition", "trend", "intent", "opportunity"]
TREND_COLUMNS = ["name", "values_csv"]
SOURCE_COLUMNS = ["point", "source"]
CLUSTER_COLUMNS = ["title", "keywords", "note"]


# ============================================================
# 세션 상태 초기화
# ============================================================
def init_state():
    defaults = {
        "language": "EN",
        "tier": "Standard",
        "niche": "",
        "subtitle_extra": "",
        "report_date": "",
        "exec_summary": "",
        "footer_note": "",
        "trend_note": "",
        "trend_months": "Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec",
        "keyword_rows": [],
        "trend_series": [],
        "sources": [],
        "clusters": [],
        "recommendations_text": "",
        "seed_keywords_text": "",
        "output_filename": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()


def reset_all():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    init_state()


def auto_record_source(point, source):
    for i, (p, s) in enumerate(st.session_state.sources):
        if p == point:
            parts = [x.strip() for x in s.split(";")]
            if source.strip() not in parts:
                st.session_state.sources[i] = (p, s + "; " + source)
            return
    st.session_state.sources.append((point, source))


def kw_rows_to_df(rows):
    if not rows:
        return pd.DataFrame(columns=KW_COLUMNS)
    return pd.DataFrame(rows, columns=KW_COLUMNS)


def df_to_kw_rows(df):
    df = df.fillna("")
    return df.to_dict("records")


def trend_series_to_df(series):
    if not series:
        return pd.DataFrame(columns=TREND_COLUMNS)
    return pd.DataFrame(
        [{"name": s["name"], "values_csv": ",".join(str(v) for v in s["values"])} for s in series],
        columns=TREND_COLUMNS,
    )


def df_to_trend_series(df):
    series = []
    for _, row in df.fillna("").iterrows():
        name = str(row["name"]).strip()
        if not name:
            continue
        try:
            values = [float(x.strip()) for x in str(row["values_csv"]).split(",") if x.strip() != ""]
        except ValueError:
            values = []
        series.append({"name": name, "values": values})
    return series


def sources_to_df(sources):
    if not sources:
        return pd.DataFrame(columns=SOURCE_COLUMNS)
    return pd.DataFrame(sources, columns=SOURCE_COLUMNS)


def df_to_sources(df):
    df = df.fillna("")
    return [(r["point"], r["source"]) for r in df.to_dict("records") if r["point"]]


def clusters_to_df(clusters):
    if not clusters:
        return pd.DataFrame(columns=CLUSTER_COLUMNS)
    return pd.DataFrame(clusters, columns=CLUSTER_COLUMNS)


def df_to_clusters(df):
    df = df.fillna("")
    return [r for r in df.to_dict("records") if r["title"]]


def current_keyword_rows():
    return st.session_state.keyword_rows


def current_trend_series():
    return st.session_state.trend_series


# ============================================================
# 사이드바: 진행 흐름 안내 + 전체 초기화 + 실제 네비게이션
# ============================================================
PAGE_NAMES = ["1. 기본 정보", "2. 키워드 데이터", "3. 트렌드 그래프", "4. 데이터 출처", "5. 클러스터", "6. 제안 & 생성"]
if "current_page" not in st.session_state:
    st.session_state.current_page = PAGE_NAMES[0]

with st.sidebar:
    st.title("📊 키워드 리서치\n리포트 생성기")
    st.caption("Fiverr Gig용 PDF 리포트를 만드는 웹 버전입니다.")
    if st.button("🗑️ 새 리포트 시작 (전체 초기화)", use_container_width=True):
        reset_all()
        st.rerun()
    st.divider()
    st.markdown("**사용 순서** (클릭하면 이동)")
    st.session_state.current_page = st.radio(
        "이동", PAGE_NAMES, index=PAGE_NAMES.index(st.session_state.current_page),
        label_visibility="collapsed", key="nav_radio",
    )

current_page = st.session_state.current_page
st.markdown(f"### {current_page}")
st.divider()


# ============================================================
# TAB 1: 기본 정보
# ============================================================
if current_page == PAGE_NAMES[0]:
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.language = st.radio(
            "언어 / Language", ["EN", "KR"],
            format_func=lambda x: "영문 (Fiverr 제출용)" if x == "EN" else "한글 (본인 확인용)",
            index=0 if st.session_state.language == "EN" else 1,
            horizontal=True,
        )
    with col2:
        st.session_state.tier = st.radio(
            "패키지 티어", ["Basic", "Standard", "Premium"],
            format_func=lambda x: {"Basic": "Basic (5개, 표만)", "Standard": "Standard (20개, 전체)",
                                    "Premium": "Premium (최대 50개, 전체+교차검증)"}[x],
            index=["Basic", "Standard", "Premium"].index(st.session_state.tier),
            horizontal=True,
        )

    st.session_state.niche = st.text_input("니치 / 프로젝트명 (예: Home Coffee Brewing)", value=st.session_state.niche)

    st.markdown("**부제**")
    bcol1, bcol2, bcol3, bcol4 = st.columns([2, 1, 1, 1])
    with bcol1:
        st.session_state.subtitle_extra = st.text_input(
            "부제 (예: Prepared for [Client] / Prepared as a sample deliverable)",
            value=st.session_state.subtitle_extra, label_visibility="collapsed",
        )
    with bcol2:
        if st.button("샘플 포트폴리오용"):
            st.session_state.subtitle_extra = "Prepared as a sample deliverable"
            st.rerun()
    with bcol3:
        client_name = st.text_input("바이어명", key="client_name_input", label_visibility="collapsed",
                                     placeholder="바이어명 입력")
    with bcol4:
        if st.button("실제 납품용 적용") and client_name:
            st.session_state.subtitle_extra = f"Prepared for {client_name}"
            st.rerun()

    st.session_state.report_date = st.text_input("기준일 (예: July 2026)", value=st.session_state.report_date)

    st.markdown("**Executive Summary (요약 문단)**")
    ecol1, ecol2 = st.columns([1, 1])
    with ecol1:
        if st.button("✏️ 입력된 데이터로 초안 생성", key="draft_summary_btn"):
            draft = auto_draft.draft_executive_summary(
                st.session_state.niche, current_keyword_rows(), current_trend_series(),
                language=st.session_state.language,
            )
            st.session_state.exec_summary = draft
            st.rerun()
    with ecol2:
        if st.button("🌐 한국어→영어 번역", key="translate_summary_btn"):
            try:
                st.session_state.exec_summary = translate_helper.translate_to_english(st.session_state.exec_summary)
                st.success("번역되었습니다. 검토 후 다듬어주세요.")
            except Exception as e:
                st.error(str(e))
    st.session_state.exec_summary = st.text_area(
        "exec_summary", value=st.session_state.exec_summary, height=150, label_visibility="collapsed"
    )

    st.session_state.footer_note = st.text_area("하단 안내문구 (선택)", value=st.session_state.footer_note, height=70)


# ============================================================
# TAB 2: 키워드 데이터
# ============================================================
if current_page == PAGE_NAMES[1]:
    st.subheader("0단계 — 시드 키워드 아이디어")
    st.caption("아직 검색할 키워드가 없다면 여기서 시작하세요. 니치명 + 언어 설정에 맞춰 후보를 만들어줍니다.")
    if st.button("✏️ 니치명으로 시드 키워드 생성"):
        if not st.session_state.niche.strip():
            st.warning("먼저 니치/프로젝트명을 입력해주세요 (탭1).")
        else:
            seeds = auto_draft.generate_seed_keywords(st.session_state.niche, language=st.session_state.language)
            st.session_state.seed_keywords_text = ", ".join(seeds)
            st.rerun()
    if st.session_state.seed_keywords_text:
        st.code(st.session_state.seed_keywords_text, language=None)
        st.caption("이 문구를 복사해서 Google Keyword Planner의 'Discover new keywords'에 붙여넣으세요. "
                   "실제 검색어인지는 아니고, 확장을 위한 출발점일 뿐입니다.")

    st.divider()
    st.subheader("0.5단계 — 자동완성 확장 (실제 사람들이 검색하는 표현 찾기)")
    example_term = "유아 카시트" if st.session_state.language == "KR" else "baby car seat"
    engines_desc = "Google + Naver" if st.session_state.language == "KR" else "Google"
    st.caption(
        f"'{example_term}' 같은 기본어에 질문형 수식어를 붙여서, {engines_desc} 자동완성이 실제로 "
        "어떤 문장을 완성해주는지 찾아냅니다. 맘카페/포럼 글 뒤져서 진짜 고민 언어를 찾는 것과 "
        "비슷한 효과를 자동으로 냅니다. (현재 언어 설정에 따라 자동으로 한글/영어 수식어와 "
        f"검색엔진이 결정됩니다: {engines_desc})"
    )
    pain_base = st.text_input(f"기본 검색어 (예: {example_term})", key="pain_base_input")
    if st.button("🔎 질문형 조합으로 자동완성 조회"):
        if not pain_base.strip():
            st.warning("기본 검색어를 입력해주세요.")
        else:
            queries = web_ops.generate_pain_point_queries(pain_base, language=st.session_state.language)
            progress_bar = st.progress(0, text="자동완성 조회 준비 중...")

            def ac_progress_cb(i, total):
                progress_bar.progress(i / total, text=f"자동완성 조회 중... ({i}/{total})")

            suggestions, stats = web_ops.expand_via_autocomplete(
                queries, language=st.session_state.language, progress_cb=ac_progress_cb
            )
            progress_bar.empty()
            if suggestions:
                st.session_state["pain_point_suggestions"] = suggestions
                st.success(f"{stats['queries_tried']}개 조합 조회, {stats['found']}개 표현 발견 "
                           + (f"({stats['errors']}개 조회 실패)" if stats["errors"] else ""))
            else:
                st.warning("찾은 표현이 없습니다. 기본 검색어를 바꿔서 다시 시도해보세요.")

    if st.session_state.get("pain_point_suggestions"):
        st.multiselect(
            "발견된 표현 (원하는 것만 골라서 아래 버튼으로 키워드 표에 추가)",
            options=st.session_state["pain_point_suggestions"],
            default=st.session_state["pain_point_suggestions"],
            key="pain_point_selected",
        )
        if st.button("➕ 선택한 표현을 키워드 표에 추가"):
            selected = st.session_state.get("pain_point_selected", [])
            existing = {r["keyword"].strip().lower() for r in st.session_state.keyword_rows}
            added = 0
            for kw in selected:
                if kw.strip().lower() not in existing:
                    st.session_state.keyword_rows.append(
                        {"keyword": kw, "volume": "", "competition": "", "trend": "", "intent": "", "opportunity": ""}
                    )
                    existing.add(kw.strip().lower())
                    added += 1
            st.success(f"{added}개를 키워드 표에 추가했습니다 (검색량 등은 Keyword Planner에서 조회해서 채워주세요).")
            st.rerun()

    st.divider()
    st.subheader("1단계 — 검색량 조회 사이트 바로가기")
    lcol1, lcol2, lcol3 = st.columns(3)
    with lcol1:
        st.link_button("🔗 Google Keyword Planner", "https://ads.google.com/aw/keywordplanner/home")
    with lcol2:
        st.link_button("🔗 Keywords Everywhere", "https://keywordseverywhere.com/")
    with lcol3:
        st.link_button("🔗 Ubersuggest (무료 대안)", "https://neilpatel.com/ubersuggest/")

    st.divider()
    st.subheader("2단계 — 조회 결과 불러오기")

    SOURCE_OPTIONS = ["Google Keyword Planner", "Keywords Everywhere", "Ubersuggest", "Google Trends", "직접 입력..."]

    upload_col, paste_col = st.columns(2)

    with upload_col:
        st.markdown("**엑셀/CSV 파일 불러오기**")
        uploaded_file = st.file_uploader("파일 선택", type=["xlsx", "xls", "csv"], key="file_uploader")
        src_choice_file = st.selectbox("이 데이터는 어떤 툴에서 가져왔나요?", SOURCE_OPTIONS, key="src_file")
        custom_src_file = ""
        if src_choice_file == "직접 입력...":
            custom_src_file = st.text_input("출처 이름 직접 입력", key="custom_src_file")
        if st.button("📂 파일 불러오기 적용") and uploaded_file is not None:
            suffix = os.path.splitext(uploaded_file.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name
            try:
                rows = data_sources.import_keyword_table_from_excel(tmp_path)
            except Exception as e:
                st.error(str(e))
                rows = None
            finally:
                os.unlink(tmp_path)
            if rows:
                st.session_state.keyword_rows.extend([
                    {k: r.get(k, "") for k in KW_COLUMNS} for r in rows
                ])
                tool_name = custom_src_file.strip() or "Keyword research tool" if src_choice_file == "직접 입력..." else src_choice_file
                source_desc = f"{tool_name} (data exported {datetime.now().strftime('%Y-%m-%d')})"
                auto_record_source("Keyword list & volume (bulk import)", source_desc)
                auto_record_source("Monthly search volume", source_desc)
                if any(r.get("competition") for r in rows):
                    auto_record_source("Keyword-level competition", source_desc)
                st.success(f"{len(rows)}개 키워드를 불러왔습니다.")
                st.rerun()

    with paste_col:
        st.markdown("**클립보드에서 붙여넣기**")
        paste_text = st.text_area("표를 복사(Ctrl+C)한 뒤 여기 붙여넣으세요 (Ctrl+V)", key="paste_area", height=100)
        src_choice_paste = st.selectbox("이 데이터는 어떤 툴에서 가져왔나요?", SOURCE_OPTIONS, key="src_paste")
        custom_src_paste = ""
        if src_choice_paste == "직접 입력...":
            custom_src_paste = st.text_input("출처 이름 직접 입력", key="custom_src_paste")
        if st.button("📋 붙여넣기 적용") and paste_text.strip():
            try:
                rows = data_sources.parse_clipboard_table(paste_text)
            except Exception as e:
                st.error(str(e))
                rows = None
            if rows:
                st.session_state.keyword_rows.extend([
                    {k: r.get(k, "") for k in KW_COLUMNS} for r in rows
                ])
                tool_name = custom_src_paste.strip() or "Keyword research tool" if src_choice_paste == "직접 입력..." else src_choice_paste
                source_desc = f"{tool_name} (data as of {datetime.now().strftime('%Y-%m-%d')})"
                auto_record_source("Keyword list & volume (bulk import)", source_desc)
                auto_record_source("Monthly search volume", source_desc)
                if any(r.get("competition") for r in rows):
                    auto_record_source("Keyword-level competition", source_desc)
                st.success(f"{len(rows)}개 키워드를 불러왔습니다.")
                st.rerun()

    st.divider()
    st.subheader("키워드 기회 테이블")
    st.caption("표를 직접 편집하거나 행을 추가/삭제할 수 있습니다 (맨 아래 빈 행에 입력하면 새 행 추가).")

    edited_df = st.data_editor(
        kw_rows_to_df(st.session_state.keyword_rows),
        num_rows="dynamic", use_container_width=True, key="kw_editor",
        column_config={
            "keyword": "키워드", "volume": "검색량/월", "competition": "경쟁도",
            "trend": "트렌드", "intent": "의도", "opportunity": "기회도",
        },
    )
    st.session_state.keyword_rows = df_to_kw_rows(edited_df)

    st.markdown(f"※ 표의 검색량 컬럼에서 PDF 생성 시 검색량 그래프가 자동으로 만들어집니다 (상위 6개).")

    bcol1, bcol2, bcol3 = st.columns(3)
    with bcol1:
        if st.button("🧹 중복 키워드 병합 (교차검증)", use_container_width=True):
            merged, stats = web_ops.merge_duplicate_keywords(st.session_state.keyword_rows)
            st.session_state.keyword_rows = merged
            if stats["merged_count"] == 0:
                st.info("중복된 키워드가 없습니다.")
            else:
                msg = f"{stats['merged_count']}개의 중복 키워드를 병합했습니다 (검색량은 평균값)."
                if stats["mismatch_notes"]:
                    msg += "\n\n⚠️ 값이 달라서 두 값을 모두 남긴 항목:\n" + "\n".join(stats["mismatch_notes"][:6])
                st.success(msg)
            st.rerun()

    with bcol2:
        if st.button("🤖 자동 처리 (트렌드+정규화+의도+기회도)", use_container_width=True):
            rows = st.session_state.keyword_rows
            if not rows:
                st.warning("먼저 키워드를 입력해주세요.")
            else:
                progress_bar = st.progress(0, text="트렌드 조회 준비 중...")

                def progress_cb(i, total):
                    progress_bar.progress(i / total, text=f"트렌드 조회 중... ({i}/{total} 배치)")

                new_series, trend_stats = web_ops.bulk_fetch_trends(
                    rows, st.session_state.trend_series, max_keywords=30, progress_cb=progress_cb
                )
                st.session_state.trend_series = new_series
                progress_bar.empty()

                if trend_stats["success_count"]:
                    auto_record_source(
                        "Search interest & seasonality trend",
                        f"Google Trends (last 12 months, as of {datetime.now().strftime('%Y-%m-%d')})"
                    )

                normalized, norm_stats = web_ops.normalize_enums(rows)
                classified, intent_stats = web_ops.classify_missing_intent(normalized)
                judged, judge_stats = web_ops.judge_trend_opportunity(
                    classified, st.session_state.trend_series, st.session_state.language
                )
                st.session_state.keyword_rows = judged

                msg_parts = []
                if trend_stats["ran"]:
                    fstats = trend_stats.get("filter_stats", {})
                    msg_parts.append(
                        f"트렌드 조회: 신규 {trend_stats['success_count']}개 성공"
                        + (f", {trend_stats['fail_count']}개 실패" if trend_stats["fail_count"] else "")
                        + f" (기존 {trend_stats['skipped_existing']}개는 재조회 생략)."
                    )
                    if fstats:
                        msg_parts.append(
                            f"↳ 조회 전 필터링: 전체 {fstats['total_candidates_before_filter']}개 중 "
                            f"경쟁도 미상(데이터 없음) {fstats['excluded_no_competition']}개를 제외하고, "
                            f"검색량 상위 {fstats['selected_count']}개를 조회 대상으로 선정했습니다."
                        )
                    if trend_stats.get("rate_limited"):
                        msg_parts.append("⚠️ Google Trends 요청 제한으로 중단됨. 잠시 후 다시 시도하세요.")
                else:
                    msg_parts.append("트렌드 조회: 모든 키워드에 이미 데이터가 있어 생략했습니다.")
                msg_parts.append(f"한글 값 정규화: {norm_stats['changed_count']}개 값을 영어로 바꿨습니다.")
                msg_parts.append(f"의도 분류: 비어있던 {intent_stats['classified_count']}개를 자동 분류했습니다.")
                msg_parts.append(f"기회도: {judge_stats['opportunity_count']}개 모두 계산했습니다.")
                if norm_stats["korean_keywords"]:
                    msg_parts.append(
                        f"⚠️ 키워드 자체가 한글인 {len(norm_stats['korean_keywords'])}개는 정규화 대상에서 "
                        f"제외했습니다: {', '.join(norm_stats['korean_keywords'][:5])}"
                    )
                st.success("\n\n".join(msg_parts))
                st.rerun()

    with bcol3:
        if st.button("⌨️ 표에서 여러 행 선택해 일괄수정은 상단 표에서", use_container_width=True, disabled=True):
            pass
        st.caption("표에서 여러 셀을 드래그해서 직접 편집하거나, 값을 복사해서 붙여넣을 수 있습니다 (data editor 기본 기능).")


# ============================================================
# TAB 3: 트렌드 그래프
# ============================================================
if current_page == PAGE_NAMES[2]:
    st.subheader("Google Trends 자동 조회 (수동)")
    existing_keywords = [r["keyword"] for r in st.session_state.keyword_rows if r.get("keyword")]
    seed_for_trend = ", ".join(existing_keywords[:5])
    trend_kw_input = st.text_input(
        "키워드 (쉼표로 구분, 최대 5개) — 탭2 키워드가 자동으로 채워집니다",
        value=seed_for_trend,
    )
    tcol1, tcol2 = st.columns(2)
    with tcol1:
        timeframe = st.selectbox("조회 기간", ["today 3-m", "today 12-m", "today 5-y"], index=1)
    with tcol2:
        geo = st.text_input("지역 (비워두면 전세계, 예: US, KR)", value="")

    if st.button("🔍 Google Trends에서 조회"):
        keywords = [k.strip() for k in trend_kw_input.split(",") if k.strip()][:5]
        if not keywords:
            st.warning("키워드를 입력해주세요.")
        else:
            try:
                months, series = data_sources.fetch_google_trends(keywords, timeframe=timeframe, geo=geo)
            except Exception as e:
                st.error(str(e))
                series = None
            if series:
                st.session_state.trend_months = ",".join(months)
                existing_by_name = {s["name"]: i for i, s in enumerate(st.session_state.trend_series)}
                for s in series:
                    if s["name"] in existing_by_name:
                        st.session_state.trend_series[existing_by_name[s["name"]]] = s
                    else:
                        st.session_state.trend_series.append(s)
                auto_record_source(
                    "Search interest & seasonality trend",
                    f"Google Trends (last 12 months, as of {datetime.now().strftime('%Y-%m-%d')})"
                )
                st.success(f"{len(series)}개 키워드의 트렌드를 가져왔습니다.")
                st.rerun()

    st.divider()
    st.session_state.trend_months = st.text_input("X축 라벨 (쉼표 구분)", value=st.session_state.trend_months)

    st.markdown("**트렌드 데이터 (직접 편집 가능, values_csv는 쉼표로 구분된 숫자)**")
    trend_df = st.data_editor(
        trend_series_to_df(st.session_state.trend_series),
        num_rows="dynamic", use_container_width=True, key="trend_editor",
        column_config={"name": "키워드명", "values_csv": "월별 수치 (쉼표 구분)"},
    )
    st.session_state.trend_series = df_to_trend_series(trend_df)

    if st.session_state.trend_series:
        chart_data = {}
        months_list = [m.strip() for m in st.session_state.trend_months.split(",") if m.strip()]
        for s in st.session_state.trend_series:
            if len(s["values"]) == len(months_list):
                chart_data[s["name"]] = s["values"]
        if chart_data:
            chart_df = pd.DataFrame(chart_data, index=months_list)
            st.line_chart(chart_df)

    st.session_state.trend_note = st.text_area("그래프 위 설명 문단 (선택)", value=st.session_state.trend_note)


# ============================================================
# TAB 4: 데이터 출처
# ============================================================
if current_page == PAGE_NAMES[3]:
    st.caption("자동조회/불러오기 시 자동 기록됩니다. 수동 입력분은 직접 추가해주세요.")
    src_df = st.data_editor(
        sources_to_df(st.session_state.sources),
        num_rows="dynamic", use_container_width=True, key="source_editor",
        column_config={"point": "데이터 항목", "source": "출처"},
    )
    st.session_state.sources = df_to_sources(src_df)


# ============================================================
# TAB 5: 클러스터
# ============================================================
if current_page == PAGE_NAMES[4]:
    if st.button("🪄 키워드 표에서 자동 클러스터 생성"):
        clusters, stats = web_ops.auto_build_clusters(
            st.session_state.keyword_rows, st.session_state.clusters, language=st.session_state.language
        )
        st.session_state.clusters = clusters
        if stats["created"] == 0:
            st.warning("키워드 표에 '의도' 값이 입력된 키워드가 없습니다. 탭2에서 먼저 채워주세요.")
        else:
            msg = f"{stats['created']}개 클러스터를 생성/갱신했습니다."
            if stats["uncategorized"]:
                msg += f"\n의도가 비어있어 제외된 키워드: {', '.join(stats['uncategorized'][:5])}"
            st.success(msg)
        st.rerun()

    st.caption("'의도' 컬럼값(Informational/Commercial 등) 기준으로 자동 그룹화합니다.")

    cluster_df = st.data_editor(
        clusters_to_df(st.session_state.clusters),
        num_rows="dynamic", use_container_width=True, key="cluster_editor",
        column_config={"title": "클러스터명", "keywords": "키워드 목록", "note": "콘텐츠 전략"},
    )
    st.session_state.clusters = df_to_clusters(cluster_df)


# ============================================================
# TAB 6: 제안 & 생성
# ============================================================
if current_page == PAGE_NAMES[5]:
    st.markdown("**실행 제안 (한 줄에 하나씩)**")
    rcol1, rcol2 = st.columns(2)
    with rcol1:
        if st.button("✏️ 입력된 데이터로 초안 생성", key="draft_recs_btn"):
            recs = auto_draft.draft_recommendations(
                st.session_state.keyword_rows, st.session_state.trend_series, language=st.session_state.language
            )
            st.session_state.recommendations_text = "\n".join(recs)
            st.rerun()
    with rcol2:
        if st.button("🌐 한국어→영어 번역", key="translate_recs_btn"):
            try:
                st.session_state.recommendations_text = translate_helper.translate_to_english(
                    st.session_state.recommendations_text
                )
                st.success("번역되었습니다.")
            except Exception as e:
                st.error(str(e))
    st.session_state.recommendations_text = st.text_area(
        "recs", value=st.session_state.recommendations_text, height=150, label_visibility="collapsed"
    )

    st.divider()

    suggested_name = web_ops.build_suggested_filename(
        st.session_state.niche, st.session_state.tier, st.session_state.report_date, st.session_state.subtitle_extra
    )
    fcol1, fcol2 = st.columns([3, 1])
    with fcol1:
        output_filename = st.text_input("저장 파일명", value=st.session_state.output_filename or suggested_name)
    with fcol2:
        if st.button("✏️ 자동 생성"):
            st.session_state.output_filename = suggested_name
            st.rerun()

    if st.button("📄 PDF 생성하기", type="primary", use_container_width=True):
        if not st.session_state.niche.strip():
            st.error("니치 / 프로젝트명을 입력해주세요 (탭1).")
        else:
            data = {
                "language": st.session_state.language,
                "tier": st.session_state.tier,
                "niche": st.session_state.niche,
                "subtitle_extra": st.session_state.subtitle_extra,
                "report_date": st.session_state.report_date,
                "exec_summary": st.session_state.exec_summary,
                "footer_note": st.session_state.footer_note,
                "sources": st.session_state.sources,
                "trend_months": [m.strip() for m in st.session_state.trend_months.split(",") if m.strip()],
                "trend_series": st.session_state.trend_series,
                "trend_note": st.session_state.trend_note,
                "volume_labels": [], "volume_values": [],
                "keyword_rows": st.session_state.keyword_rows,
                "clusters": st.session_state.clusters,
                "recommendations": [l for l in st.session_state.recommendations_text.splitlines() if l.strip()],
            }
            # 검색량 그래프: 키워드 표에서 상위 6개 자동 추출
            parsed_vol = []
            for r in data["keyword_rows"]:
                try:
                    parsed_vol.append((r["keyword"], float(str(r.get("volume", "")).replace(",", ""))))
                except (ValueError, KeyError):
                    continue
            parsed_vol.sort(key=lambda x: x[1], reverse=True)
            data["volume_labels"] = [k for k, _ in parsed_vol[:6]]
            data["volume_values"] = [v for _, v in parsed_vol[:6]]

            proceed = True
            if data["language"] == "EN":
                korean_keywords, narrative_fields = web_ops.korean_check_details(data)
                if korean_keywords:
                    st.error(
                        f"'키워드' 컬럼에 한글이 섞여 있습니다 ({len(korean_keywords)}개): "
                        + ", ".join(korean_keywords[:8])
                        + "\n\n번역이 아니라 영어로 재검색해서 교체해야 합니다 (탭2)."
                    )
                    proceed = False
                elif narrative_fields:
                    st.warning(
                        "요약/제안/클러스터 설명에 한글이 섞여 있습니다. "
                        "번역 버튼으로 바꾼 뒤 다시 생성하는 걸 권장합니다. 이대로 생성하려면 버튼을 다시 눌러주세요."
                    )

            if proceed:
                out_path = os.path.join(tempfile.gettempdir(), output_filename)
                try:
                    report_engine.build_report(data, out_path)
                    with open(out_path, "rb") as f:
                        pdf_bytes = f.read()
                    st.success("PDF가 생성되었습니다!")
                    st.download_button(
                        "⬇️ PDF 다운로드", data=pdf_bytes, file_name=output_filename, mime="application/pdf",
                        type="primary", use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"리포트 생성 중 오류: {e}")
