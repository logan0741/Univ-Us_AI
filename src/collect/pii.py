"""개인정보 마스킹 (수집 계획서 §6.1, AI 계획서 §8).

수집한 원문은 본인 데이터이므로 '저장'은 그대로 한다(원문 보존 §5.1).
다만 이 데이터를 LLM 프롬프트나 로그·이슈로 '내보낼' 때는 반드시 마스킹한다.
'식별 정보는 프롬프트에 포함하지 않는다'(AI 계획서 §8).
"""
from __future__ import annotations

import re

# 학번(7~10자리 숫자), 휴대폰, 주민번호 앞자리 등
_PATTERNS = [
    (re.compile(r"\b01[016789]-?\d{3,4}-?\d{4}\b"), "[전화]"),
    (re.compile(r"\b\d{6}-?[1-4]\d{6}\b"), "[주민번호]"),
    (re.compile(r"\b\d{7,10}\b"), "[학번]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[이메일]"),
]


def mask(text: str) -> str:
    """프롬프트·로그·이슈로 내보내기 전 개인정보를 가린다."""
    out = text
    for pat, repl in _PATTERNS:
        out = pat.sub(repl, out)
    return out


def mask_name(name: str) -> str:
    """이름 가운데 글자를 가린다. 홍길동 -> 홍*동."""
    if len(name) <= 1:
        return name
    if len(name) == 2:
        return name[0] + "*"
    return name[0] + "*" * (len(name) - 2) + name[-1]
