# -*- coding: utf-8 -*-
"""
auto_draft.py
--------------
GUI에 입력된 데이터(니치, 키워드 표, 트렌드)를 바탕으로
Executive Summary / Recommendations 초안 문장을 규칙 기반으로 생성합니다.

주의: 이건 AI가 아니라 "입력된 숫자를 문장 템플릿에 끼워넣는" 방식입니다.
      즉 완전히 새로운 통찰을 만들어내는 게 아니라, 이미 입력한 표/그래프 데이터를
      요약 문장 형태로 바꿔주는 역할만 합니다. 최종 문장은 반드시 검토 후 사용하세요.
"""


def classify_trend_direction(values):
    """
    12개월(또는 여러 구간) 수치 리스트를 받아서 상승/보합/하락을 판정합니다.
    앞쪽 절반 평균 대비 뒤쪽 절반 평균이 15% 이상 높으면 상승, 15% 이상 낮으면 하락, 그 사이면 보합.
    """
    if not values or len(values) < 2:
        return None
    first_half_avg = sum(values[: len(values) // 2]) / max(1, len(values) // 2)
    second_half_avg = sum(values[len(values) // 2:]) / max(1, len(values) - len(values) // 2)
    if first_half_avg == 0:
        return None
    ratio = second_half_avg / first_half_avg
    if ratio > 1.15:
        return "rising"
    elif ratio < 0.85:
        return "declining"
    else:
        return "stable"


_TREND_LABELS = {
    "rising": {"EN": "▲ Rising", "KR": "▲ 상승"},
    "stable": {"EN": "— Stable", "KR": "— 보합"},
    "declining": {"EN": "▼ Declining", "KR": "▼ 하락"},
}


def trend_label(direction, language="EN"):
    if direction not in _TREND_LABELS:
        return ""
    return _TREND_LABELS[direction][language]


def compute_opportunity(volume, competition, trend_direction, all_volumes):
    """
    검색량(상대 순위) + 경쟁도 + 트렌드 방향을 조합해서 기회도(High/Medium/Low)를 계산합니다.
    이건 '정답'이 아니라 참고용 1차 판단이며, 최종 판단은 사람이 검토해서 조정해야 합니다.

    volume: 이 키워드의 검색량 (숫자)
    competition: "Low"/"Medium"/"High" (대소문자 무관, 한글도 일부 인식)
    trend_direction: "rising"/"stable"/"declining"/None
    all_volumes: 전체 키워드들의 검색량 리스트 (상대 순위 계산용)
    """
    score = 0

    # 검색량 점수: 전체 중 상위/중위/하위 구간으로 판단
    if all_volumes and volume is not None:
        sorted_vols = sorted(all_volumes, reverse=True)
        n = len(sorted_vols)
        rank = sorted_vols.index(volume) if volume in sorted_vols else n // 2
        percentile = rank / max(1, n - 1) if n > 1 else 0
        if percentile <= 0.33:
            score += 2
        elif percentile <= 0.66:
            score += 1

    # 경쟁도 점수: 낮을수록 유리
    comp = (competition or "").strip().lower()
    if comp in ("low", "낮음"):
        score += 2
    elif comp in ("medium", "중간", "보통"):
        score += 1
    # high/높음이면 0점

    # 트렌드 점수: 상승할수록 유리
    if trend_direction == "rising":
        score += 2
    elif trend_direction == "stable":
        score += 1
    # declining/None이면 0점

    if score >= 5:
        return "High"
    elif score >= 3:
        return "Medium"
    else:
        return "Low"


_ENUM_KR_TO_EN = {
    # 경쟁도
    "낮음": "Low", "매우낮음": "Low", "매우 낮음": "Low",
    "보통": "Medium", "중간": "Medium",
    "높음": "High", "매우높음": "High", "매우 높음": "High",
    # 트렌드
    "상승": "Rising", "▲상승": "Rising", "▲ 상승": "Rising",
    "보합": "Stable", "—보합": "Stable", "— 보합": "Stable",
    "하락": "Declining", "▼하락": "Declining", "▼ 하락": "Declining",
    # 의도
    "정보성": "Informational", "정보": "Informational",
    "구매성": "Commercial", "구매": "Commercial", "상업성": "Commercial",
    "탐색성": "Navigational", "탐색": "Navigational",
    # 기회도
    "높은기회": "High", "낮은기회": "Low",
}


def normalize_enum_value(value):
    """
    경쟁도/트렌드/의도/기회도처럼 '자유 검색어가 아닌 라벨' 값에 한글이 섞여 있으면
    사전 매핑으로 안전하게 영어로 바꿉니다. 매핑에 없는 값은 그대로 둡니다.
    (키워드 자체는 이 함수로 처리하면 안 됨 — 검색어 번역은 실제 검색 행태를 보장 못 함)
    """
    if not value:
        return value
    stripped = str(value).strip()
    return _ENUM_KR_TO_EN.get(stripped, value)


def normalize_keyword_rows_enums(keyword_rows):
    """keyword_rows 리스트에서 competition/trend/intent/opportunity 값만 정규화하고,
    keyword/volume은 건드리지 않은 새 리스트를 반환합니다."""
    result = []
    changed_count = 0
    for row in keyword_rows:
        new_row = dict(row)
        for key in ("competition", "trend", "intent", "opportunity"):
            old_val = new_row.get(key, "")
            new_val = normalize_enum_value(old_val)
            if new_val != old_val:
                changed_count += 1
            new_row[key] = new_val
        result.append(new_row)
    return result, changed_count


_INTENT_PATTERNS = {
    "Commercial": [
        # English
        "best", "buy", "price", "cheap", "discount", "coupon", "review", "reviews",
        "top", "for sale", "deal", "shop", "store", "vs", "comparison", "worth it",
        # Korean
        "추천", "후기", "순위", "가격", "할인", "구매", "베스트", "최고", "리뷰",
    ],
    "Navigational": [
        # English
        "login", "official", "website", "sign in", "download",
        # Korean
        "로그인", "공식", "다운로드", "홈페이지",
    ],
    "Informational": [
        # English
        "how to", "what is", "guide", "tips", "why", "when", "meaning", "definition",
        "recipe", "diy", "checklist", "signs", "causes", "symptoms", "ideas", "for beginners",
        # Korean
        "방법", "하는법", "이유", "원인", "증상", "시기", "언제", "왜", "정리", "차이", "팁",
        "초보", "종류", "가이드",
    ],
}

_INTENT_PRIORITY = ["Commercial", "Navigational", "Informational"]


def classify_intent(keyword):
    """
    키워드 문자열의 패턴을 보고 검색 의도를 규칙 기반으로 추정합니다.
    (Commercial/Navigational 패턴이 하나라도 있으면 그걸 우선, 없으면 Informational 패턴 확인,
    아무 패턴도 안 걸리면 기본값 Informational — 롱테일 콘텐츠 키워드는 대부분 정보성이라서.)

    주의: 이건 규칙 기반 추정이라 완벽하지 않습니다. 특히 애매한 키워드는 직접 검토해서 수정하세요.
    """
    kw_lower = str(keyword).lower()
    for intent in _INTENT_PRIORITY:
        for pattern in _INTENT_PATTERNS[intent]:
            if pattern in kw_lower:
                return intent
    return "Informational"


def contains_korean(text):
    return any("\uac00" <= ch <= "\ud7a3" for ch in str(text))


_SEED_TEMPLATES_EN = [
    "{niche}",
    "best {niche}",
    "how to {niche}",
    "{niche} for beginners",
    "{niche} tips",
    "{niche} guide",
    "{niche} reviews",
    "{niche} at home",
    "{niche} ideas",
    "top {niche}",
]

_SEED_TEMPLATES_KR = [
    "{niche}",
    "{niche} 추천",
    "{niche} 방법",
    "{niche} 후기",
    "{niche} 순위",
    "{niche} 정리",
    "{niche} 초보",
    "{niche} 팁",
    "{niche} 하는법",
    "{niche} 종류",
]


def generate_seed_keywords(niche, language=None):
    """
    니치명(예: 'home coffee brewing' 또는 '육아 블로그')을 받아서, Google Keyword Planner의
    'Discover new keywords'에 그대로 붙여넣을 수 있는 시드 키워드 후보를 생성합니다.
    Keyword Planner는 한 번에 최대 10개까지만 받으므로, 정확히 10개까지만 생성합니다.

    language: "EN" 또는 "KR"을 명시하면 그 언어의 템플릿을 사용합니다 (탭1의 언어 설정을 그대로 따름).
              지정하지 않으면 니치명에 한글이 섞여있는지로 자동 판단합니다.

    한글 니치명이면 한글 자연어 수식어(추천/방법/후기 등)를, 영문 니치명이면 영어 템플릿을
    사용합니다 — 언어를 섞으면(예: 'best 육아 블로그') 부자연스러운 조합이 되어 Keyword Planner가
    검색 확장을 못 하고 입력값을 그대로 돌려주는 문제가 생기기 때문입니다.

    주의: 이건 실제 검색 데이터가 아니라 흔한 패턴으로 조합한 '출발점'입니다.
    여기서 나온 문구를 그대로 리포트에 쓰면 안 되고, Keyword Planner에 넣어서
    실제 검색량이 있는지 확인하는 용도로만 쓰세요.
    """
    niche = (niche or "").strip()
    if not niche:
        return []

    if language == "EN":
        use_korean = False
    elif language == "KR":
        use_korean = True
    else:
        use_korean = contains_korean(niche)

    templates = _SEED_TEMPLATES_KR if use_korean else _SEED_TEMPLATES_EN
    niche_for_template = niche if use_korean else niche.lower()

    seeds = []
    seen = set()
    for template in templates:
        phrase = template.format(niche=niche_for_template)
        if phrase not in seen:
            seen.add(phrase)
            seeds.append(phrase)
    return seeds[:10]


def _top_opportunity_keywords(keyword_rows, n=3):
    """opportunity가 High인 키워드를 우선으로, 최대 n개 추출"""
    high = [r for r in keyword_rows if str(r.get("opportunity", "")).strip().lower() == "high"]
    others = [r for r in keyword_rows if r not in high]
    ordered = high + others
    return [r.get("keyword", "") for r in ordered[:n] if r.get("keyword")]


def _trend_direction_summary(trend_series):
    """트렌드 계열들의 시작값 대비 끝값을 비교해서 상승/하락/보합 판단"""
    notes = []
    for s in trend_series:
        values = s.get("values", [])
        if len(values) < 2:
            continue
        first_half_avg = sum(values[: len(values) // 2]) / max(1, len(values) // 2)
        second_half_avg = sum(values[len(values) // 2:]) / max(1, len(values) - len(values) // 2)
        if second_half_avg > first_half_avg * 1.15:
            direction = "rising"
        elif second_half_avg < first_half_avg * 0.85:
            direction = "declining"
        else:
            direction = "stable"
        notes.append((s.get("name", ""), direction))
    return notes


def draft_executive_summary(niche, keyword_rows, trend_series, language="EN"):
    """Executive Summary 초안 생성"""
    top_kws = _top_opportunity_keywords(keyword_rows, n=3)
    trend_notes = _trend_direction_summary(trend_series)
    rising = [name for name, d in trend_notes if d == "rising"]

    if language == "KR":
        parts = []
        if niche:
            parts.append(f"이 리포트는 '{niche}' 관련 콘텐츠/상품을 위한 키워드 기회를 정리합니다.")
        if top_kws:
            parts.append(f"현재까지 조사된 키워드 중 '{', '.join(top_kws)}'가 상대적으로 높은 기회도를 보입니다.")
        if rising:
            parts.append(f"특히 '{', '.join(rising)}'는 최근 검색 관심도가 상승 추세입니다.")
        if not parts:
            parts.append(f"'{niche or '이 니치'}'에 대한 키워드 기회를 정리한 리포트입니다.")
        parts.append("아래 방법론 및 데이터 섹션에서 구체적인 산출 방식을 확인할 수 있습니다.")
        return " ".join(parts)
    else:
        parts = []
        if niche:
            parts.append(f"This report identifies keyword opportunities for {niche}.")
        if top_kws:
            parts.append(
                f"Among the keywords researched so far, {', '.join(top_kws)} show the strongest "
                f"combination of demand and opportunity."
            )
        if rising:
            parts.append(f"Notably, {', '.join(rising)} show a rising search interest trend.")
        if not parts:
            parts.append(f"This report summarizes keyword opportunities for {niche or 'this niche'}.")
        parts.append("See the methodology section below for how each figure was sourced.")
        return " ".join(parts)


def draft_recommendations(keyword_rows, trend_series, language="EN"):
    """Recommendations 초안 (여러 줄) 생성"""
    top_kws = _top_opportunity_keywords(keyword_rows, n=2)
    trend_notes = _trend_direction_summary(trend_series)
    rising = [name for name, d in trend_notes if d == "rising"]

    recs = []
    if language == "KR":
        if top_kws:
            recs.append(f"{', '.join(top_kws)} 키워드를 우선순위로 콘텐츠/페이지를 준비하세요.")
        if rising:
            recs.append(f"{', '.join(rising)}의 상승 추세를 고려해 관련 콘텐츠를 미리 준비하는 것을 추천합니다.")
        recs.append("정보성 키워드로 트래픽을 모으고, 구매성 키워드 페이지로 내부 링크하는 구조를 고려하세요.")
        recs.append("검색 트렌드는 계절/시장 변화에 따라 바뀌므로, 분기별로 재검토하는 것을 권장합니다.")
    else:
        if top_kws:
            recs.append(f"Prioritize {', '.join(top_kws)} — these show the strongest opportunity based on current data.")
        if rising:
            recs.append(f"Prepare content around {', '.join(rising)} ahead of their rising search trend.")
        recs.append("Use informational keywords to build traffic, then link internally to commercial pages to guide conversions.")
        recs.append("Revisit this research quarterly, as search trends shift with seasonality and market changes.")
    return recs


def draft_cluster_note(cluster_title, keywords, language="EN"):
    """클러스터의 '콘텐츠 전략' 문구 초안 (클러스터명에 따라 다른 템플릿)"""
    title_lower = (cluster_title or "").strip().lower()
    if language == "KR":
        if "정보" in cluster_title or "informational" in title_lower:
            return "블로그 글, 튜토리얼, 가이드 콘텐츠에 적합합니다. 트래픽을 모으고 채널의 전문성을 쌓는 역할을 합니다."
        if "구매" in cluster_title or "commercial" in title_lower:
            return "제품 리뷰, 비교 페이지, 제휴 콘텐츠에 적합합니다. 실제 구매 전환을 유도하는 역할을 합니다."
        return "이 클러스터에 맞는 콘텐츠 형태와 활용 방안을 정리해주세요."
    else:
        if "informational" in title_lower:
            return "Best suited for blog posts, tutorials, or beginner guides — builds traffic and topical authority."
        if "commercial" in title_lower:
            return "Best suited for product reviews, comparison pages, or affiliate content — drives purchase intent."
        return "Describe the content format and strategy that fits this cluster."
