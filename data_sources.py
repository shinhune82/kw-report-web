# -*- coding: utf-8 -*-
"""
data_sources.py
-----------------
GUI에서 사용하는 외부 데이터 연동 기능:
1) Google Trends 자동 조회 (pytrends)
2) 엑셀(Keyword Planner export 등) 불러오기

두 기능 모두 실패해도 프로그램이 죽지 않고, 명확한 한글 에러 메시지를
raise 해서 GUI가 messagebox로 보여줄 수 있게 합니다.
"""

import os


# ------------------------------------------------------------------
# 1) Google Trends 자동 조회
# ------------------------------------------------------------------
def fetch_naver_autocomplete_suggestions(query):
    """
    네이버 자동완성 제안을 가져옵니다 (네이버 검색창이 쓰는 공개 엔드포인트,
    Google Suggest와 비슷한 성격 — 로그인/카페 글 같은 폐쇄 공간이 아니라
    누구나 브라우저에서 그냥 검색창에 타이핑하면 보이는 공개 기능입니다).
    """
    try:
        import requests
    except ImportError:
        raise RuntimeError(
            "requests 패키지가 설치되어 있지 않습니다. cmd에서 'pip install requests' 실행 후 다시 시도해주세요."
        )

    query = (query or "").strip()
    if not query:
        raise ValueError("검색어를 입력해주세요.")

    url = "https://ac.search.naver.com/nx/ac"
    params = {
        "q": query, "con": "0", "frm": "nv", "ans": "2",
        "r_format": "json", "r_enc": "UTF-8", "r_unicode": "0",
        "t_koreng": "1", "run": "2", "rev": "4", "q_enc": "UTF-8", "st": "100",
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise RuntimeError(f"네이버 자동완성 조회에 실패했습니다: {e}")

    suggestions = []
    try:
        groups = data.get("items", [])
        if groups:
            for entry in groups[0]:
                if entry and entry[0]:
                    suggestions.append(str(entry[0]).strip())
    except Exception:
        pass  # 응답 구조가 예상과 다르면 빈 리스트로 처리 (에러로 전체를 막지 않음)

    return [s for s in suggestions if s]


def fetch_autocomplete_suggestions(query, hl="ko"):
    """
    Google 자동완성 제안을 가져옵니다 (비공식 엔드포인트 — pytrends와 비슷한 성격의 접근 방식).
    실제 사람들이 검색창에 이어서 치는 표현을 찾는 용도 (예: '유아 카시트 언제' -> '유아 카시트 언제까지').
    """
    try:
        import requests
    except ImportError:
        raise RuntimeError(
            "requests 패키지가 설치되어 있지 않습니다. cmd에서 'pip install requests' 실행 후 다시 시도해주세요."
        )

    query = (query or "").strip()
    if not query:
        raise ValueError("검색어를 입력해주세요.")

    url = "https://suggestqueries.google.com/complete/search"
    params = {"client": "firefox", "q": query, "hl": hl}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        suggestions = data[1] if len(data) > 1 else []
        return [s for s in suggestions if s and s.strip()]
    except Exception as e:
        raise RuntimeError(f"자동완성 조회에 실패했습니다: {e}")


def fetch_google_trends(keywords, timeframe="today 12-m", geo=""):
    """
    keywords: list[str], 최대 5개 (Google Trends 제한)
    timeframe: pytrends 형식 (예: 'today 12-m', 'today 5-y')
    geo: '' (전세계) 또는 'US', 'KR' 등 국가코드

    반환: (months, series)
        months: list[str]  (x축 라벨, 보통 12~13개 정도의 주/월 단위)
        series: list[{"name":.., "values":[float,...]}]
    """
    try:
        from pytrends.request import TrendReq
    except ImportError:
        raise RuntimeError(
            "pytrends 패키지가 설치되어 있지 않습니다. "
            "cmd에서 'pip install pytrends' 를 실행한 뒤 다시 시도해주세요."
        )

    if not keywords:
        raise ValueError("조회할 키워드를 1개 이상 입력해주세요.")
    if len(keywords) > 5:
        raise ValueError("Google Trends는 한 번에 최대 5개 키워드까지만 비교할 수 있습니다.")

    try:
        pytrends = TrendReq(hl="en-US", tz=360)
        pytrends.build_payload(keywords, cat=0, timeframe=timeframe, geo=geo)
        df = pytrends.interest_over_time()
    except Exception as e:
        if "429" in str(e):
            raise RuntimeError(
                "Google Trends가 요청을 너무 자주 보낸다고 판단해서 일시적으로 차단했습니다 "
                "(인터넷 문제가 아닙니다). 몇 분에서 1시간 정도 기다렸다가 다시 시도해주세요.\n"
                f"(상세: {e})"
            )
        raise RuntimeError(
            "Google Trends 조회에 실패했습니다. 인터넷 연결을 확인하시거나, "
            f"잠시 후 다시 시도해주세요.\n(상세: {e})"
        )

    if df is None or df.empty:
        raise RuntimeError("조회 결과가 없습니다. 키워드 철자를 확인해주세요.")

    if "isPartial" in df.columns:
        df = df.drop(columns=["isPartial"])

    months = [d.strftime("%Y-%m-%d") for d in df.index]
    series = []
    for kw in keywords:
        if kw in df.columns:
            series.append({"name": kw, "values": [float(v) for v in df[kw].tolist()]})

    return months, series


# ------------------------------------------------------------------
# 2) 엑셀 불러오기 (Keyword Planner export 등)
# ------------------------------------------------------------------
# 사람마다 엑셀 컬럼명이 다를 수 있어서, 자주 쓰이는 이름들을 폭넓게 매칭합니다.
_COLUMN_ALIASES = {
    "keyword": ["keyword", "keywords", "키워드", "search term", "query"],
    "volume": ["volume", "avg. monthly searches", "monthly searches", "search volume",
               "검색량", "월간검색량", "월간 검색량"],
    "competition": ["competition", "competition (indexed value)", "경쟁도", "keyword difficulty", "kd"],
    "trend": ["trend", "trend direction", "트렌드"],
    "intent": ["intent", "search intent", "의도", "검색의도"],
    "opportunity": ["opportunity", "opportunity score", "기회도"],
}


def _normalize(colname):
    return str(colname).strip().lower()


def _match_columns(df_columns):
    """실제 엑셀 컬럼명 -> 표준 키 매핑 딕셔너리 반환"""
    mapping = {}
    normalized = {_normalize(c): c for c in df_columns}
    for standard_key, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                mapping[standard_key] = normalized[alias]
                break
    return mapping


def parse_clipboard_table(text):
    """
    엑셀/Google Sheets/Keyword Planner 웹페이지에서 표를 복사(Ctrl+C)하면
    보통 탭(\t)으로 구분된 텍스트가 클립보드에 들어갑니다. 이를 파싱합니다.
    반환 형식은 import_keyword_table_from_excel()과 동일합니다.
    """
    try:
        import pandas as pd
        import io
    except ImportError:
        raise RuntimeError(
            "pandas 패키지가 설치되어 있지 않습니다. "
            "cmd에서 'pip install pandas' 실행 후 다시 시도해주세요."
        )

    text = text.strip()
    if not text:
        raise ValueError("붙여넣은 내용이 비어있습니다.")

    # Keyword Planner 화면에서 복사하면 표 위 안내문/메타데이터 줄이 섞여올 수 있으므로
    # CSV 파일과 동일하게 실제 헤더 줄을 먼저 찾아서 그 위는 건너뜁니다.
    lines = text.splitlines(keepends=True)
    header_idx = _find_header_line_index(lines)
    body = "".join(lines[header_idx:])
    header_line = lines[header_idx]
    first_sep = "\t" if header_line.count("\t") >= header_line.count(",") else ","

    df = None
    last_error = None
    for sep in (first_sep, "\t" if first_sep == "," else ","):
        try:
            candidate = pd.read_csv(io.StringIO(body), sep=sep, engine="python", on_bad_lines="skip")
        except TypeError:
            try:
                candidate = pd.read_csv(io.StringIO(body), sep=sep, engine="python", error_bad_lines=False)
            except Exception as e:
                last_error = e
                continue
        except Exception as e:
            last_error = e
            continue
        if candidate.shape[1] >= 2:
            df = candidate
            break
        if df is None:
            df = candidate  # 컬럼 1개짜리라도 일단 보관 (아래에서 keyword 컬럼 검증으로 걸러짐)

    if df is None:
        raise RuntimeError(f"붙여넣은 표를 해석하지 못했습니다: {last_error}")

    mapping = _match_columns(df.columns)
    if "keyword" not in mapping:
        raise ValueError(
            "붙여넣은 표에서 '키워드' 컬럼을 찾지 못했습니다. "
            "첫 줄에 헤더(Keyword, Avg. Monthly Searches 등)가 포함되어야 합니다.\n"
            f"인식된 컬럼: {list(df.columns)}"
        )

    rows = []
    for _, r in df.iterrows():
        row = {}
        for key in ["keyword", "volume", "competition", "trend", "intent", "opportunity"]:
            col = mapping.get(key)
            if col is not None and col in df.columns:
                val = r[col]
                row[key] = "" if pd.isna(val) else str(val)
            else:
                row[key] = ""
        if row["keyword"]:
            rows.append(row)

    if not rows:
        raise ValueError("붙여넣은 표에서 읽어들인 키워드 행이 없습니다.")

    return rows


def _find_header_line_index(lines, max_scan=25):
    """
    Google Keyword Planner CSV는 실제 표 위에 안내문/날짜범위 같은 메타데이터 줄이
    몇 줄 섞여있는 경우가 많습니다 (예: 'Keyword Planner: Historical metrics'라는 제목 줄에도
    'keyword'라는 단어가 들어있어서 단순 포함여부로는 오탐지가 생김).
    그래서 쉼표/탭으로 나눈 뒤, 한 '필드'가 정확히 'keyword' 또는 '키워드'인 줄만 헤더로 인정합니다.
    못 찾으면 0을 반환합니다.
    """
    keyword_terms = {"keyword", "keywords", "키워드"}
    for i, line in enumerate(lines[:max_scan]):
        for sep in ("\t", ","):
            fields = [f.strip().strip('"').lower() for f in line.split(sep)]
            if any(f in keyword_terms for f in fields):
                return i
    return 0


def _read_csv_any_encoding(path):
    """
    CSV 인코딩/구분자/헤더 위치가 도구마다 달라서 (Google Keyword Planner는 보통 UTF-16 + 탭 구분이고,
    실제 표 앞에 메타데이터 줄이 섞여있음; 국내 엑셀은 CP949/EUC-KR인 경우가 흔함) 아래 순서로 시도합니다.
    또한 특정 셀 안에 쉼표가 많은 값(따옴표 누락 등) 때문에 깨지는 행은 건너뛰고 나머지를 읽습니다.
    """
    import pandas as pd

    encodings = ["utf-8-sig", "utf-16", "cp949", "euc-kr", "latin1"]
    last_error = None

    for enc in encodings:
        try:
            with open(path, "r", encoding=enc, errors="strict") as fh:
                raw_lines = fh.readlines()
        except (UnicodeDecodeError, UnicodeError, LookupError):
            continue
        except Exception as e:
            last_error = e
            continue

        if not raw_lines:
            continue

        header_idx = _find_header_line_index(raw_lines)
        header_line = raw_lines[header_idx]
        sep = "\t" if header_line.count("\t") >= header_line.count(",") else ","

        try:
            df = pd.read_csv(
                path, encoding=enc, sep=sep, skiprows=header_idx,
                engine="python", on_bad_lines="skip",
            )
        except TypeError:
            # 구버전 pandas는 on_bad_lines 대신 error_bad_lines를 씁니다.
            try:
                df = pd.read_csv(
                    path, encoding=enc, sep=sep, skiprows=header_idx,
                    engine="python", error_bad_lines=False,
                )
            except Exception as e:
                last_error = e
                continue
        except Exception as e:
            last_error = e
            continue

        if df.shape[1] >= 2 and df.shape[0] >= 1:
            return df

    raise RuntimeError(
        "CSV 파일 구조를 인식하지 못했습니다. 엑셀에서 파일을 열어 "
        "'다른 이름으로 저장 → CSV UTF-8' 로 다시 저장한 뒤 시도하시거나, "
        "엑셀(.xlsx) 형식으로 저장해서 불러와주세요.\n"
        f"(마지막 오류: {last_error})"
    )


def import_keyword_table_from_excel(path):
    """
    엑셀/CSV 파일을 읽어서 키워드 표(탭5)에 넣을 수 있는 리스트[dict] 형태로 반환.
    최소한 'keyword' 컬럼은 있어야 하고, 나머지는 있으면 채우고 없으면 빈 값으로 둡니다.
    """
    try:
        import pandas as pd
    except ImportError:
        raise RuntimeError(
            "pandas 패키지가 설치되어 있지 않습니다. "
            "cmd에서 'pip install pandas openpyxl' 실행 후 다시 시도해주세요."
        )

    if not os.path.exists(path):
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

    try:
        if path.lower().endswith(".csv"):
            df = _read_csv_any_encoding(path)
        else:
            df = pd.read_excel(path)
    except Exception as e:
        raise RuntimeError(f"파일을 읽는 중 오류가 발생했습니다: {e}")

    mapping = _match_columns(df.columns)
    if "keyword" not in mapping:
        raise ValueError(
            "엑셀에서 '키워드' 컬럼을 찾지 못했습니다. "
            "컬럼명이 'Keyword', 'Keywords', '키워드' 중 하나인지 확인해주세요.\n"
            f"현재 컬럼: {list(df.columns)}"
        )

    rows = []
    for _, r in df.iterrows():
        row = {}
        for key in ["keyword", "volume", "competition", "trend", "intent", "opportunity"]:
            col = mapping.get(key)
            if col is not None and col in df.columns:
                val = r[col]
                row[key] = "" if pd.isna(val) else str(val)
            else:
                row[key] = ""
        if row["keyword"]:
            rows.append(row)

    if not rows:
        raise ValueError("엑셀에서 읽어들인 키워드 행이 없습니다.")

    return rows



