# -*- coding: utf-8 -*-
"""
report_engine.py
-----------------
키워드 리서치 리포트 PDF 생성 엔진.
GUI(report_gui.py)에서 이 모듈을 불러와 사용합니다.
단독으로도 아래처럼 테스트 가능:
    python report_engine.py
"""

import os
import sys
import platform
import tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, HRFlowable, PageBreak
)
from reportlab.lib.enums import TA_LEFT

# ------------------------------------------------------------------
# Color theme (coffee / brand theme - feel free to tweak)
# ------------------------------------------------------------------
BROWN_DARK = colors.HexColor("#3B2314")
BROWN_MED = colors.HexColor("#6F4E37")
BROWN_LIGHT = colors.HexColor("#C89F80")
CREAM = colors.HexColor("#F5EBDD")
ACCENT = colors.HexColor("#B5651D")
GREY_TEXT = colors.HexColor("#4A4A4A")

MPL_BROWN_DARK = "#3B2314"
MPL_BROWN_MED = "#6F4E37"
MPL_BROWN_LIGHT = "#C89F80"
MPL_ACCENT = "#B5651D"
MPL_PALETTE = ["#3B2314", "#B5651D", "#C89F80", "#8B5E3C", "#A9744F", "#5C3A21"]


# ------------------------------------------------------------------
# Korean font auto-detection
# ------------------------------------------------------------------
def find_korean_font():
    """
    Returns (regular_path, bold_path) for a usable Korean TrueType font,
    or (None, None) if nothing found (falls back to Helvetica; Korean text
    will not render correctly in that case).
    Priority: Malgun Gothic (Windows default) -> Nanum Gothic (Linux/Mac, common) 
    """
    candidates = []
    system = platform.system()

    if system == "Windows":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        candidates.append((
            os.path.join(windir, "Fonts", "malgun.ttf"),
            os.path.join(windir, "Fonts", "malgunbd.ttf"),
        ))

    # Common Linux (Ubuntu/Debian with fonts-nanum installed) locations
    candidates.append((
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    ))
    # Common macOS location if user installs Nanum via homebrew-cask-fonts
    candidates.append((
        os.path.expanduser("~/Library/Fonts/NanumGothic.ttf"),
        os.path.expanduser("~/Library/Fonts/NanumGothicBold.ttf"),
    ))

    for reg, bold in candidates:
        if os.path.exists(reg) and os.path.exists(bold):
            return reg, bold

    return None, None


def register_fonts(language="EN"):
    """
    Registers fonts for reportlab + matplotlib depending on language.
    Returns a dict with keys: 'regular', 'bold' (reportlab font names to use).
    """
    if language == "KR":
        reg_path, bold_path = find_korean_font()
        if reg_path is None:
            raise RuntimeError(
                "한글 폰트를 찾을 수 없습니다. Windows는 맑은 고딕(malgun.ttf)이 기본 내장되어 "
                "있어야 하고, 리눅스/맥이라면 'Nanum Gothic' 폰트를 설치해주세요."
            )
        # Register with reportlab (idempotent-safe: catch already-registered)
        try:
            pdfmetrics.registerFont(TTFont("KRRegular", reg_path))
            pdfmetrics.registerFont(TTFont("KRBold", bold_path))
        except Exception:
            pass

        # Register with matplotlib
        fm.fontManager.addfont(reg_path)
        plt.rcParams["font.family"] = fm.FontProperties(fname=reg_path).get_name()
        plt.rcParams["axes.unicode_minus"] = False

        return {"regular": "KRRegular", "bold": "KRBold"}
    else:
        plt.rcParams["font.family"] = "DejaVu Sans"
        plt.rcParams["axes.unicode_minus"] = False
        return {"regular": "Helvetica", "bold": "Helvetica-Bold"}


# ------------------------------------------------------------------
# Chart generation
# ------------------------------------------------------------------
def make_trend_chart(series, months, out_path, title, ylabel):
    """
    series: list of dicts [{"name": "pour over coffee", "values": [12 numbers]}, ...]
    months: list of 12 axis labels
    """
    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=200)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    for i, s in enumerate(series):
        color = MPL_PALETTE[i % len(MPL_PALETTE)]
        ax.plot(months, s["values"], marker="o", linewidth=2.5, color=color, label=s["name"])

    ax.set_ylabel(ylabel, fontsize=10, color=MPL_BROWN_DARK)
    ax.set_title(title, fontsize=13, color=MPL_BROWN_DARK, fontweight="bold", pad=12)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#ccc")
    ax.spines["bottom"].set_color("#ccc")
    ax.tick_params(colors=MPL_BROWN_DARK, labelsize=9)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    ax.grid(axis="y", linestyle="--", alpha=0.3)

    plt.tight_layout()
    plt.savefig(out_path, facecolor="white")
    plt.close(fig)


def make_volume_chart(labels, values, out_path, title, ylabel):
    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=200)
    fig.patch.set_facecolor("white")
    colors_ = [MPL_PALETTE[i % len(MPL_PALETTE)] for i in range(len(labels))]
    bars = ax.bar(labels, values, color=colors_, width=0.55)

    for bar, v in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, v + max(values) * 0.02,
                 f"{v:,.0f}", ha="center", fontsize=9, color=MPL_BROWN_DARK, fontweight="bold")

    ax.set_ylabel(ylabel, fontsize=10, color=MPL_BROWN_DARK)
    ax.set_title(title, fontsize=13, color=MPL_BROWN_DARK, fontweight="bold", pad=12)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(colors=MPL_BROWN_DARK, labelsize=9)
    ax.set_yticks([])

    plt.tight_layout()
    plt.savefig(out_path, facecolor="white")
    plt.close(fig)


# ------------------------------------------------------------------
# PDF generation
# ------------------------------------------------------------------
def _sort_keyword_rows(rows):
    """
    키워드 표를 기회도(High>Medium>Low) → 검색량(높은순) → 경쟁도(Low>Medium>High) 순으로 정렬합니다.
    값이 없거나 인식 못하는 값은 가장 뒤로 보냅니다.
    """
    opp_rank = {"high": 0, "medium": 1, "low": 2}
    comp_rank = {"low": 0, "medium": 1, "high": 2}

    def sort_key(row):
        opp = opp_rank.get(str(row.get("opportunity", "")).strip().lower(), 3)
        vol_raw = str(row.get("volume", "")).replace(",", "").strip()
        try:
            vol = float(vol_raw) if vol_raw else -1
        except ValueError:
            vol = -1
        comp = comp_rank.get(str(row.get("competition", "")).strip().lower(), 3)
        return (opp, -vol, comp)

    return sorted(rows, key=sort_key)


# ------------------------------------------------------------------
# 패키지 티어 설정 (Basic / Standard / Premium)
# ------------------------------------------------------------------
TIER_CONFIG = {
    "Basic": {
        "keyword_limit": 5,
        "show_summary": False,
        "show_methodology": False,
        "show_trend_chart": False,
        "show_volume_chart": True,
        "show_clusters": False,
        "show_recommendations": False,
        "label": {"EN": "Basic Package", "KR": "베이직 패키지"},
    },
    "Standard": {
        "keyword_limit": 20,
        "show_summary": True,
        "show_methodology": True,
        "show_trend_chart": True,
        "show_volume_chart": True,
        "show_clusters": True,
        "show_recommendations": True,
        "label": {"EN": "Standard Package", "KR": "스탠다드 패키지"},
    },
    "Premium": {
        "keyword_limit": 50,
        "show_summary": True,
        "show_methodology": True,
        "show_trend_chart": True,
        "show_volume_chart": True,
        "show_clusters": True,
        "show_recommendations": True,
        "label": {"EN": "Premium Package", "KR": "프리미엄 패키지"},
    },
}


def build_report(data, out_pdf_path):
    """
    data: dict with the following keys (see report_gui.py for how it's populated):
        language: "EN" or "KR"
        niche: str
        subtitle_extra: str (e.g. "Prepared as a sample deliverable")
        report_date: str
        exec_summary: str
        sources: list of (data_point, source) tuples
        trend_months: list[12] of axis labels
        trend_series: list of {"name":.., "values":[12 floats]}
        volume_labels: list[str]
        volume_values: list[float]
        keyword_rows: list of dicts with keys
            keyword, volume, competition, trend, intent, opportunity
        clusters: list of {"title":.., "keywords":.., "note":..}
        recommendations: list[str]
        footer_note: str
    out_pdf_path: where to save the PDF
    """
    from xml.sax.saxutils import escape as _xml_escape

    def _esc(text):
        """사용자 입력 텍스트를 reportlab Paragraph(XML)에서 안전하게 쓰도록 이스케이프."""
        return _xml_escape(str(text)) if text else ""

    # 사용자 입력이 들어가는 필드들을 미리 이스케이프 (GUI에서는 평범한 &, < 등을 그대로 입력해도 됨)
    data = dict(data)
    for key in ("niche", "subtitle_extra", "report_date", "exec_summary", "footer_note", "trend_note"):
        if data.get(key):
            data[key] = _esc(data[key])
    if data.get("sources"):
        data["sources"] = [(_esc(p), _esc(s)) for p, s in data["sources"]]
    if data.get("keyword_rows"):
        data["keyword_rows"] = [{k: _esc(v) for k, v in row.items()} for row in data["keyword_rows"]]
    if data.get("clusters"):
        data["clusters"] = [{k: _esc(v) for k, v in c.items()} for c in data["clusters"]]
    if data.get("recommendations"):
        data["recommendations"] = [_esc(r) for r in data["recommendations"]]

    language = data.get("language", "EN")

    # ---- 한글(또는 기타 비-라틴 문자)이 섞여 있으면 언어 설정과 무관하게
    #      한글 지원 폰트를 강제로 사용 (안 그러면 Helvetica엔 한글 글꼴이 없어서 깨짐) ----
    _text_fragments = []
    for _k in ("niche", "subtitle_extra", "report_date", "exec_summary", "footer_note", "trend_note"):
        if data.get(_k):
            _text_fragments.append(str(data[_k]))
    for _pt, _src in (data.get("sources") or []):
        _text_fragments += [str(_pt), str(_src)]
    for _row in (data.get("keyword_rows") or []):
        _text_fragments += [str(_v) for _v in _row.values()]
    for _c in (data.get("clusters") or []):
        _text_fragments += [str(_c.get("title", "")), str(_c.get("keywords", "")), str(_c.get("note", ""))]
    _text_fragments += [str(_r) for _r in (data.get("recommendations") or [])]
    for _s in (data.get("trend_series") or []):
        _text_fragments.append(str(_s.get("name", "")))
    _text_fragments += [str(_l) for _l in (data.get("volume_labels") or [])]

    try:
        " ".join(_text_fragments).encode("latin-1")
        needs_unicode_font = False
    except UnicodeEncodeError:
        needs_unicode_font = True

    font_language = "KR" if needs_unicode_font else language
    fonts = register_fonts(font_language)
    F_REG = fonts["regular"]
    F_BOLD = fonts["bold"]

    # ---- styles ----
    title_style = ParagraphStyle("Title", fontName=F_BOLD, fontSize=22, textColor=BROWN_DARK,
                                  spaceAfter=4, leading=28)
    subtitle_style = ParagraphStyle("Subtitle", fontName=F_REG, fontSize=11, textColor=BROWN_MED,
                                     spaceAfter=18, leading=16)
    h2_style = ParagraphStyle("H2", fontName=F_BOLD, fontSize=14, textColor=BROWN_DARK,
                               spaceBefore=16, spaceAfter=8, leading=19)
    h3_style = ParagraphStyle("H3", fontName=F_BOLD, fontSize=11, textColor=ACCENT,
                               spaceBefore=10, spaceAfter=6, leading=15)
    body_style = ParagraphStyle("Body", fontName=F_REG, fontSize=9.5, textColor=GREY_TEXT,
                                 leading=15.5, spaceAfter=8)
    small_style = ParagraphStyle("Small", fontName=F_REG, fontSize=8,
                                  textColor=colors.HexColor("#8A8A8A"), leading=11)
    table_header_style = ParagraphStyle("TH", fontName=F_BOLD, fontSize=9, textColor=colors.white)
    table_cell_style = ParagraphStyle("TC", fontName=F_REG, fontSize=9, textColor=GREY_TEXT, leading=13)
    table_cell_bold = ParagraphStyle("TCB", fontName=F_BOLD, fontSize=9, textColor=BROWN_DARK, leading=13)

    tmp_dir = tempfile.mkdtemp(prefix="kw_report_")
    trend_chart_path = os.path.join(tmp_dir, "trend_chart.png")
    volume_chart_path = os.path.join(tmp_dir, "volume_chart.png")

    trend_title = "12-Month Search Interest Trend" if language == "EN" else "12개월 검색 관심도 추이"
    trend_ylabel = "Relative Search Interest" if language == "EN" else "상대 검색 관심도"
    volume_title = "Core Keyword Search Volume Comparison" if language == "EN" else "핵심 키워드 검색량 비교"
    volume_ylabel = "Monthly Search Volume" if language == "EN" else "월간 검색량"

    if data.get("trend_series"):
        make_trend_chart(data["trend_series"], data["trend_months"], trend_chart_path,
                          trend_title, trend_ylabel)
    if data.get("volume_labels"):
        make_volume_chart(data["volume_labels"], data["volume_values"], volume_chart_path,
                           volume_title, volume_ylabel)

    doc = SimpleDocTemplate(
        out_pdf_path, pagesize=letter,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        leftMargin=0.65 * inch, rightMargin=0.65 * inch,
        title=f"Keyword Research Report - {data.get('niche','')}"
    )

    story = []

    # ---- Header ----
    L = {
        "EN": {
            "report_title": "Keyword Research &amp; Trend Report",
            "methodology": "Methodology &amp; Data Sources",
            "data_point": "Data Point", "source": "Source",
            "trend_section": "Search Interest Trend",
            "volume_section": "Core Keyword Volume Comparison",
            "kw_table": "Keyword Opportunity Table",
            "kw_cols": ["Keyword", "Volume/mo", "Competition", "Trend", "Intent", "Opportunity"],
            "clusters_section": "Keyword Clusters &amp; Content Angles",
            "keywords_label": "Keywords",
            "angle_label": "Content angle",
            "recs_section": "Recommendations",
        },
        "KR": {
            "report_title": "키워드 리서치 &amp; 트렌드 리포트",
            "methodology": "방법론 &amp; 데이터 출처",
            "data_point": "데이터 항목", "source": "출처",
            "trend_section": "검색 관심도 트렌드",
            "volume_section": "핵심 키워드 검색량 비교",
            "kw_table": "키워드 기회 테이블",
            "kw_cols": ["키워드", "검색량/월", "경쟁도", "트렌드", "의도", "기회도"],
            "clusters_section": "키워드 클러스터 &amp; 콘텐츠 전략",
            "keywords_label": "키워드",
            "angle_label": "콘텐츠 전략",
            "recs_section": "실행 제안",
        },
    }[language]

    tier = data.get("tier", "Standard")
    tier_conf = TIER_CONFIG.get(tier, TIER_CONFIG["Standard"])

    story.append(Paragraph(L["report_title"], title_style))
    subtitle_bits = [data.get("niche", "")]
    subtitle_bits.append(tier_conf["label"][language])
    if data.get("subtitle_extra"):
        subtitle_bits.append(data["subtitle_extra"])
    if data.get("report_date"):
        date_label = "Data as of" if language == "EN" else "기준일"
        subtitle_bits.append(f"{date_label} {data['report_date']}")
    story.append(Paragraph("  |  ".join(subtitle_bits), subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.3, color=ACCENT, spaceAfter=14))

    # ---- Executive Summary ----
    if tier_conf["show_summary"] and data.get("exec_summary"):
        summary_title = "Executive Summary" if language == "EN" else "Executive Summary (요약)"
        story.append(Paragraph(summary_title, h2_style))
        story.append(Paragraph(data["exec_summary"], body_style))

    # ---- Methodology / Sources ----
    if tier_conf["show_methodology"] and data.get("sources"):
        story.append(Paragraph(L["methodology"], h2_style))
        src_data = [[Paragraph(L["data_point"], table_header_style), Paragraph(L["source"], table_header_style)]]
        for point, src in data["sources"]:
            src_data.append([Paragraph(point, table_cell_style), Paragraph(src, table_cell_bold)])
        src_tbl = Table(src_data, colWidths=[2.6 * inch, 3.4 * inch])
        src_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BROWN_MED),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CREAM]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("LINEBELOW", (0, 0), (-1, 0), 1, ACCENT),
            ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#E5DCCB")),
        ]))
        story.append(Spacer(1, 4))
        story.append(src_tbl)
        story.append(Spacer(1, 10))

    # ---- Trend chart ----
    if tier_conf["show_trend_chart"] and data.get("trend_series"):
        story.append(Paragraph(L["trend_section"], h2_style))
        if data.get("trend_note"):
            story.append(Paragraph(data["trend_note"], body_style))
        story.append(Image(trend_chart_path, width=6.6 * inch, height=3.08 * inch))
        story.append(Spacer(1, 10))

    # ---- Volume chart ----
    if tier_conf["show_volume_chart"] and data.get("volume_labels"):
        story.append(Paragraph(L["volume_section"], h2_style))
        story.append(Image(volume_chart_path, width=6.6 * inch, height=3.08 * inch))
        story.append(Spacer(1, 4))

    if data.get("keyword_rows"):
        story.append(PageBreak())

    # ---- Keyword table ----
    if data.get("keyword_rows"):
        story.append(Paragraph(L["kw_table"], h2_style))
        sorted_rows = _sort_keyword_rows(data["keyword_rows"])
        limit = tier_conf.get("keyword_limit")
        truncated_count = 0
        if limit and len(sorted_rows) > limit:
            truncated_count = len(sorted_rows) - limit
            sorted_rows = sorted_rows[:limit]
        kw_data = [[Paragraph(c, table_header_style) for c in L["kw_cols"]]]
        for r in sorted_rows:
            row = [
                Paragraph(str(r.get("keyword", "")), table_cell_bold),
                Paragraph(str(r.get("volume", "")), table_cell_style),
                Paragraph(str(r.get("competition", "")), table_cell_style),
                Paragraph(str(r.get("trend", "")), table_cell_style),
                Paragraph(str(r.get("intent", "")), table_cell_style),
                Paragraph(str(r.get("opportunity", "")), table_cell_style),
            ]
            kw_data.append(row)
        col_widths = [1.85 * inch, 0.75 * inch, 0.85 * inch, 0.75 * inch, 1.0 * inch, 0.9 * inch]
        kw_tbl = Table(kw_data, colWidths=col_widths, repeatRows=1)
        kw_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BROWN_DARK),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CREAM]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("LINEBELOW", (0, 0), (-1, 0), 1, ACCENT),
            ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#E5DCCB")),
        ]))
        story.append(kw_tbl)
        if truncated_count > 0:
            note = (
                f"+ {truncated_count} more keywords available in a higher-tier package."
                if language == "EN" else
                f"+ 상위 패키지에서는 {truncated_count}개 키워드를 추가로 제공합니다."
            )
            story.append(Paragraph(note, small_style))
        story.append(Spacer(1, 14))

    # ---- Clusters ----
    if tier_conf["show_clusters"] and data.get("clusters"):
        story.append(Paragraph(L["clusters_section"], h2_style))
        for c in data["clusters"]:
            story.append(Paragraph(c.get("title", ""), h3_style))
            if c.get("keywords"):
                story.append(Paragraph(f"<b>{L['keywords_label']}:</b> {c['keywords']}", body_style))
            if c.get("note"):
                story.append(Paragraph(f"<b>{L['angle_label']}:</b> {c['note']}", body_style))

    # ---- Recommendations ----
    if tier_conf["show_recommendations"] and data.get("recommendations"):
        story.append(Paragraph(L["recs_section"], h2_style))
        for rec in data["recommendations"]:
            story.append(Paragraph(f"&bull;&nbsp;&nbsp;{rec}", body_style))

    # ---- Footer note ----
    if data.get("footer_note"):
        story.append(Spacer(1, 20))
        story.append(HRFlowable(width="100%", thickness=0.7, color=BROWN_LIGHT, spaceAfter=8))
        story.append(Paragraph(data["footer_note"], small_style))

    doc.build(story)
    return out_pdf_path


# ------------------------------------------------------------------
# Standalone test (uses the coffee sample) — run: python report_engine.py
# ------------------------------------------------------------------
if __name__ == "__main__":
    sample_data = {
        "language": "EN",
        "niche": "Niche: Home Coffee Brewing",
        "subtitle_extra": "Prepared as a sample deliverable",
        "report_date": "July 2026",
        "exec_summary": (
            "This report identifies high-opportunity keywords for a home coffee brewing "
            "blog, product page, or content channel. Figures shown are illustrative mock data."
        ),
        "sources": [
            ("Search interest & seasonality trend", "Google Trends"),
            ("Monthly search volume", "Google Keyword Planner"),
            ("Keyword-level competition", "Google Keyword Planner"),
        ],
        "trend_months": ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],
        "trend_series": [
            {"name": "pour over coffee", "values": [42,45,48,52,55,58,54,50,60,68,82,95]},
            {"name": "french press", "values": [55,58,60,62,60,58,56,54,58,62,70,78]},
        ],
        "volume_labels": ["pour over coffee", "french press", "espresso machine"],
        "volume_values": [40500, 33100, 60500],
        "keyword_rows": [
            {"keyword": "pour over coffee", "volume": "40,500", "competition": "Medium",
             "trend": "Rising", "intent": "Informational", "opportunity": "High"},
        ],
        "clusters": [
            {"title": "Informational", "keywords": "pour over coffee",
             "note": "Good for blog posts and tutorials."},
        ],
        "recommendations": ["Prioritize pour over coffee.", "Publish seasonal content by August."],
        "footer_note": "This is a sample report. Figures are illustrative.",
    }
    out = build_report(sample_data, os.path.join(tempfile.gettempdir(), "test_report.pdf"))
    print("Saved:", out)
