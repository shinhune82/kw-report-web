# -*- coding: utf-8 -*-
"""
translate_helper.py
---------------------
한국어로 작성한 초안을 영어로 번역하는 헬퍼.
deep-translator 라이브러리(구글 번역 엔진, API 키 불필요)를 사용합니다.

주의: 무료 번역기라 완벽하지 않습니다. Fiverr 제출용 리포트는 번역 결과를
반드시 검토하고 다듬은 뒤 사용하세요. 이 함수는 초안 작성 시간을 줄여주는
용도이지, 최종 문구를 대신 확정해주는 게 아닙니다.
"""


def translate_to_english(text):
    """
    한국어(또는 기타 언어) 텍스트를 영어로 번역합니다.
    여러 줄(문단)도 지원하며, 너무 긴 텍스트는 나눠서 번역합니다.
    """
    if not text or not text.strip():
        return text

    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        raise RuntimeError(
            "deep-translator 패키지가 설치되어 있지 않습니다. "
            "cmd에서 'pip install deep-translator' 실행 후 다시 시도해주세요."
        )

    translator = GoogleTranslator(source="auto", target="en")

    # 구글 번역 무료 엔드포인트는 한 번에 넣을 수 있는 글자 수 제한이 있어서,
    # 문단/줄 단위로 나눠서 번역한 뒤 다시 합칩니다.
    lines = text.splitlines()
    translated_lines = []
    try:
        for line in lines:
            if not line.strip():
                translated_lines.append("")
                continue
            translated_lines.append(translator.translate(line))
    except Exception as e:
        raise RuntimeError(
            "번역 중 오류가 발생했습니다. 인터넷 연결을 확인하시거나 잠시 후 다시 시도해주세요.\n"
            f"(상세: {e})"
        )

    return "\n".join(translated_lines)
