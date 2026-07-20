# -*- coding: utf-8 -*-
"""
web_ops.py
-----------
Streamlit 앱에서 쓰는 데이터 처리 로직. Tkinter 데스크톱 버전의 '조용한 내부 메서드'들을
GUI와 무관한 순수 함수로 옮긴 것입니다. auto_draft.py / data_sources.py / report_engine.py의
로직을 그대로 재사용하고, list[dict] 형태의 키워드 행을 입출력으로 다룹니다.
"""

import os
import re
from datetime import datetime

import auto_draft
import data_sources
import report_engine


KW_KEYS = ["keyword", "volume", "competition", "trend", "intent", "opportunity"]

PAIN_POINT_MODIFIERS_KR = [
    "언제", "왜", "어떻게", "방법", "추천", "후기", "증상", "원인", "괜찮나요", "안전한가요",
]

PAIN_POINT_MODIFIERS_EN = [
    "when", "why", "how to", "safe", "reviews", "recommendations", "vs", "not working", "alternative", "problems",
]


def generate_pain_point_queries(base_term, language=None, modifiers=None):
    """
    기본 검색어에 질문형 수식어를 붙여서, 자동완성 조회에 넣을 조합을 만든다.
    language="KR"이면 한글 수식어(언제/왜/방법 등), "EN"이면 영어 수식어(when/why/how to 등).
    language를 안 주면 base_term에 한글이 섞였는지로 자동 판단한다.
    """
    base = (base_term or "").strip()
    if not base:
        return []

    if modifiers is not None:
        mods = modifiers
    elif language == "KR":
        mods = PAIN_POINT_MODIFIERS_KR
    elif language == "EN":
        mods = PAIN_POINT_MODIFIERS_EN
    else:
        mods = PAIN_POINT_MODIFIERS_KR if auto_draft.contains_korean(base) else PAIN_POINT_MODIFIERS_EN

    return [f"{base} {m}" for m in mods]


def expand_via_autocomplete(queries, language="KR", progress_cb=None):
    """
    질문형 조합 목록을 자동완성에 넣어서 실제 검색 표현들을 모은다.
    language="KR"이면 Google + Naver 둘 다 조회해서 합친다 (한국은 네이버 검색 비중이 커서).
    그 외(예: "EN")에는 Google만 조회한다.
    """
    all_suggestions = []
    seen = set()
    errors = 0
    hl = "ko" if language == "KR" else "en"

    for i, q in enumerate(queries, start=1):
        if progress_cb:
            progress_cb(i, len(queries))

        try:
            suggestions = data_sources.fetch_autocomplete_suggestions(q, hl=hl)
        except Exception:
            suggestions = []
            errors += 1

        if language == "KR":
            try:
                naver_suggestions = data_sources.fetch_naver_autocomplete_suggestions(q)
            except Exception:
                naver_suggestions = []
                errors += 1
            suggestions = suggestions + naver_suggestions

        for s in suggestions:
            norm = s.strip()
            if norm and norm.lower() not in seen:
                seen.add(norm.lower())
                all_suggestions.append(norm)

    return all_suggestions, {"queries_tried": len(queries), "errors": errors, "found": len(all_suggestions)}


def normalize_enums(rows):
    """경쟁도/트렌드/의도/기회도 값의 한글 표기를 영어로 정규화. (키워드 자체는 건드리지 않음)"""
    normalized, changed_count = auto_draft.normalize_keyword_rows_enums(rows)
    korean_keywords = [r["keyword"] for r in normalized if auto_draft.contains_korean(r.get("keyword", ""))]
    return normalized, {"changed_count": changed_count, "korean_keywords": korean_keywords}


def classify_missing_intent(rows):
    """의도가 비어있는 행만 규칙 기반으로 자동 분류. 이미 값 있는 행은 그대로 유지."""
    result = []
    classified_count = 0
    for row in rows:
        new_row = dict(row)
        if not str(new_row.get("intent", "")).strip():
            new_row["intent"] = auto_draft.classify_intent(new_row.get("keyword", ""))
            classified_count += 1
        result.append(new_row)
    return result, {"classified_count": classified_count}


def judge_trend_opportunity(rows, trend_series, language="EN"):
    """탭3 트렌드 데이터를 기준으로 트렌드 방향/기회도를 계산해서 채운다."""
    trend_by_kw = {}
    for s in trend_series:
        direction = auto_draft.classify_trend_direction(s.get("values", []))
        if direction:
            trend_by_kw[s["name"].strip().lower()] = direction

    all_volumes = []
    for r in rows:
        vol_raw = str(r.get("volume", "")).replace(",", "").strip()
        if vol_raw:
            try:
                all_volumes.append(float(vol_raw))
            except ValueError:
                pass

    result = []
    matched_trend_count = 0
    for row in rows:
        new_row = dict(row)
        norm_name = str(new_row.get("keyword", "")).strip().lower()
        direction = trend_by_kw.get(norm_name)
        if direction:
            new_row["trend"] = auto_draft.trend_label(direction, language=language)
            matched_trend_count += 1

        vol_raw = str(new_row.get("volume", "")).replace(",", "").strip()
        try:
            vol = float(vol_raw) if vol_raw else None
        except ValueError:
            vol = None

        new_row["opportunity"] = auto_draft.compute_opportunity(
            vol, new_row.get("competition", ""), direction, all_volumes
        )
        result.append(new_row)

    return result, {"matched_trend_count": matched_trend_count, "opportunity_count": len(result)}


def select_trend_candidates(rows, existing_trend_series, max_keywords=30):
    """
    Google Trends 조회 대상을 검색량 기준으로 고릅니다.
    경쟁도 값이 아예 없는(데이터 품질 문제) 키워드만 제외하고, 그 외에는
    경쟁도가 Low든 High든 상관없이 검색량이 큰 순서대로 상위 max_keywords개를 선정합니다.

    (참고: 예전 버전은 '검색량+경쟁도로 계산한 1차 기회도가 Low면 제외'하는 규칙이었는데,
    Keyword Planner의 '경쟁도'는 광고 입찰 경쟁이지 SEO 난이도가 아니라서, 경쟁도가 High여도
    검색량이 크면 여전히 확인해볼 가치가 있는 키워드일 수 있습니다. 그래서 경쟁도를 기준으로
    미리 배제하지 않도록 단순화했습니다.)
    """
    existing_names = {s["name"].strip().lower() for s in existing_trend_series}

    candidates_pool = [r for r in rows if r["keyword"].strip().lower() not in existing_names]

    filtered = []
    excluded_no_competition = 0

    for r in candidates_pool:
        competition = str(r.get("competition", "")).strip()
        if not competition:
            excluded_no_competition += 1
            continue

        vol_raw = str(r.get("volume", "")).replace(",", "").strip()
        try:
            vol = float(vol_raw) if vol_raw else -1
        except ValueError:
            vol = -1

        filtered.append((r["keyword"], vol))

    filtered.sort(key=lambda x: x[1], reverse=True)
    selected = [kw for kw, _ in filtered[:max_keywords]]

    return selected, {
        "excluded_no_competition": excluded_no_competition,
        "excluded_low_opportunity": 0,  # 더 이상 이 기준으로 제외하지 않음 (하위 호환을 위해 필드는 유지)
        "total_candidates_before_filter": len(candidates_pool),
        "selected_count": len(selected),
    }


def bulk_fetch_trends(rows, existing_trend_series, max_keywords=30, progress_cb=None):
    """
    트렌드 데이터가 없는 키워드 중, select_trend_candidates()로 미리 거른 후보만
    Google Trends에서 5개씩 조회. progress_cb(i, total)를 넘기면 배치마다 호출해서
    진행상황을 알려줄 수 있음 (Streamlit 진행바용).
    """
    candidates, filter_stats = select_trend_candidates(rows, existing_trend_series, max_keywords)

    if not candidates:
        return existing_trend_series, {
            "success_count": 0, "fail_count": 0, "skipped_existing": len(rows), "ran": False,
            "rate_limited": False, "filter_stats": filter_stats,
        }

    import time
    batches = [candidates[i:i + 5] for i in range(0, len(candidates), 5)]
    new_series = list(existing_trend_series)
    success_count = 0
    fail_count = 0
    rate_limited = False
    last_months = None

    for i, batch in enumerate(batches, start=1):
        if progress_cb:
            progress_cb(i, len(batches))
        if i > 1:
            time.sleep(3)
        try:
            months, series = data_sources.fetch_google_trends(batch, timeframe="today 12-m")
        except Exception as e:
            if "429" in str(e):
                rate_limited = True
                fail_count += len(batch) * (len(batches) - i + 1)
                break
            fail_count += len(batch)
            continue

        last_months = months
        existing_by_name = {s["name"]: idx for idx, s in enumerate(new_series)}
        for s in series:
            if s["name"] in existing_by_name:
                new_series[existing_by_name[s["name"]]] = s
            else:
                new_series.append(s)
            success_count += 1

    return new_series, {
        "success_count": success_count, "fail_count": fail_count,
        "skipped_existing": len(rows) - len(candidates), "ran": True,
        "rate_limited": rate_limited, "months": last_months, "filter_stats": filter_stats,
    }


def merge_duplicate_keywords(rows):
    """
    같은 키워드가 여러 소스에서 겹치면 병합: 검색량은 평균, 값이 다른 라벨 필드는
    '값1/값2' 형태로 모두 남겨서 검토할 수 있게 한다.
    """
    field_labels = {"competition": "경쟁도", "trend": "트렌드", "intent": "의도", "opportunity": "기회도"}
    groups = {}
    order = []
    for row in rows:
        norm = row["keyword"].strip().lower()
        groups.setdefault(norm, []).append(row)
        if norm not in order:
            order.append(norm)

    merged_rows = []
    merged_count = 0
    mismatch_notes = []

    for norm in order:
        group = groups[norm]
        if len(group) == 1:
            merged_rows.append(group[0])
            continue

        keyword_display = group[0]["keyword"]
        vols = []
        for r in group:
            try:
                vols.append(float(str(r.get("volume", "")).replace(",", "").strip()))
            except ValueError:
                pass
        avg_vol = round(sum(vols) / len(vols)) if vols else group[0].get("volume", "")

        merged = {"keyword": keyword_display, "volume": avg_vol}
        for key in ["competition", "trend", "intent", "opportunity"]:
            distinct = []
            for r in group:
                v = str(r.get(key, "")).strip()
                if v and v not in distinct:
                    distinct.append(v)
            if len(distinct) <= 1:
                merged[key] = distinct[0] if distinct else ""
            else:
                merged[key] = "/".join(distinct)
                mismatch_notes.append(f"{keyword_display} — {field_labels[key]}: {' vs '.join(distinct)}")

        merged_rows.append(merged)
        merged_count += 1

    return merged_rows, {"merged_count": merged_count, "mismatch_notes": mismatch_notes}


def auto_build_clusters(rows, existing_clusters, language="EN"):
    """키워드의 '의도' 값을 기준으로 클러스터를 자동 생성/갱신."""
    groups = {}
    uncategorized = []
    for r in rows:
        intent = str(r.get("intent", "")).strip()
        kw = r.get("keyword", "")
        if not kw:
            continue
        if not intent:
            uncategorized.append(kw)
            continue
        groups.setdefault(intent, []).append(kw)

    if not groups:
        return existing_clusters, {"created": 0, "uncategorized": uncategorized}

    existing_by_title = {c["title"]: i for i, c in enumerate(existing_clusters)}
    result = list(existing_clusters)

    for title, kws in groups.items():
        kw_str = ", ".join(kws)
        note = auto_draft.draft_cluster_note(title, kw_str, language=language)
        if title in existing_by_title:
            result[existing_by_title[title]] = {"title": title, "keywords": kw_str, "note": note}
        else:
            result.append({"title": title, "keywords": kw_str, "note": note})

    return result, {"created": len(groups), "uncategorized": uncategorized}


def korean_check_details(data):
    """키워드 컬럼(재검색 필요)과 서술형 텍스트(번역 가능)에 한글이 섞였는지 각각 확인."""
    korean_keywords = [
        r.get("keyword", "") for r in (data.get("keyword_rows") or [])
        if auto_draft.contains_korean(r.get("keyword", ""))
    ]
    narrative_fields = []
    for k in ("niche", "subtitle_extra", "exec_summary", "footer_note", "trend_note"):
        if data.get(k) and auto_draft.contains_korean(data[k]):
            narrative_fields.append(k)
    for r in (data.get("recommendations") or []):
        if auto_draft.contains_korean(r):
            narrative_fields.append("recommendations")
            break
    for c in (data.get("clusters") or []):
        if auto_draft.contains_korean(c.get("note", "")):
            narrative_fields.append("clusters")
            break
    return korean_keywords, narrative_fields


def sanitize_filename_part(text):
    text = (text or "").strip()
    if not text:
        return ""
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^0-9A-Za-z_\-가-힣]", "", text)
    return text


def build_suggested_filename(niche, tier, report_date, subtitle_extra):
    niche_part = sanitize_filename_part(niche) or "Report"
    date_part = sanitize_filename_part(report_date) or datetime.now().strftime("%Y%m%d")

    client_match = re.match(r"^Prepared for (.+)$", (subtitle_extra or "").strip(), re.IGNORECASE)
    if client_match:
        client_part = sanitize_filename_part(client_match.group(1))
    elif "sample" in (subtitle_extra or "").lower():
        client_part = "Sample"
    else:
        client_part = "Client_Request"

    parts = [p for p in [niche_part, tier, date_part, client_part] if p]
    return "_".join(parts) + ".pdf"
