from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


ScreeningCategory = Literal["allowed", "safety", "privacy", "not_ml"]


@dataclass(frozen=True)
class ScreeningResult:
    """Decision returned before a hypothesis enters the design graph."""

    allowed: bool
    category: ScreeningCategory
    reason: str


_SAFETY_PATTERNS = (
    re.compile(r"\b(ignore|override|bypass)\b.{0,40}\b(instructions?|prompt|policy)\b", re.I),
    re.compile(r"\b(system prompt|developer message|jailbreak)\b", re.I),
    re.compile(
        r"\brm\s+-rf\b|\b(drop|delete)\s+(?:all\s+)?(database|table|files?)\b",
        re.I,
    ),
    re.compile(r"(이전|기존).{0,20}(지시|규칙).{0,20}(무시|우회)"),
    re.compile(r"(시스템 프롬프트|개발자 메시지).{0,20}(출력|공개|유출)"),
    re.compile(r"(파일|데이터베이스|테이블).{0,15}(전부|모두)?.{0,10}(삭제|파괴)"),
    re.compile(r"\b(malware|ransomware|credential theft|steal passwords?)\b", re.I),
)

_DIRECT_PRIVACY_PATTERNS = (
    re.compile(r"\b\d{6}-?[1-4]\d{6}\b"),
    re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    re.compile(r"(?<![A-Z0-9._%+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I),
    re.compile(r"\b01[016789]-?\d{3,4}-?\d{4}\b"),
    re.compile(r"\b(?:sk|pk|api)[-_][A-Za-z0-9_-]{16,}\b"),
)

_SENSITIVE_DATA_TERMS = re.compile(
    r"주민등록번호|주민번호|여권번호|계좌번호|신용카드번호|비밀번호|"
    r"생체정보|지문|얼굴인식정보|의료기록|진료기록|"
    r"social security number|passport number|bank account|credit card number|"
    r"password|biometric|medical record",
    re.I,
)

_ML_OR_RESEARCH_SIGNALS = re.compile(
    r"가설|데이터|피처|특성|변수|모델|학습|검증|점수|예측|분류|회귀|클러스터|"
    r"전처리|왜도|정규화|결측|하이퍼파라미터|정확도|정밀도|재현율|r2|rmse|auc|"
    r"영향|관계|상관|효과|증가|감소|높아|낮아|개선|차이|"
    r"hypothesis|dataset|data|feature|variable|model|train|validation|score|predict|"
    r"classification|regression|clustering|preprocess|skew|normalize|missing|"
    r"accuracy|precision|recall|correlation|effect|increase|decrease|higher|lower|improve",
    re.I,
)

_GENERAL_CONVERSATION_SIGNALS = re.compile(
    r"안녕|반가워|고마워|오늘 날씨|점심|저녁 메뉴|농담|심심|잡담|"
    r"번역해|요약해|이메일 써|자기소개|소설|시를 써|"
    r"hello|how are you|weather|tell me a joke|translate|summarize|write an email|"
    r"write a poem|small talk",
    re.I,
)


def screen_hypothesis(content: str) -> ScreeningResult:
    """Apply deterministic safety, privacy, and ML-relevance gates."""
    normalized = " ".join((content or "").split())
    if not normalized:
        return ScreeningResult(False, "not_ml", "가설 내용이 비어 있습니다.")

    if any(pattern.search(normalized) for pattern in _SAFETY_PATTERNS):
        return ScreeningResult(
            False,
            "safety",
            "시스템 지시 우회, 정보 유출 또는 파괴적 작업 요청이 감지되었습니다.",
        )

    if any(pattern.search(normalized) for pattern in _DIRECT_PRIVACY_PATTERNS):
        return ScreeningResult(
            False,
            "privacy",
            "가설 내용에 직접 식별자 또는 자격 증명으로 보이는 값이 포함되어 있습니다.",
        )

    if _SENSITIVE_DATA_TERMS.search(normalized):
        return ScreeningResult(
            False,
            "privacy",
            "민감 개인정보를 실험 입력이나 예측 기준으로 사용하는 요청은 처리할 수 없습니다.",
        )

    has_ml_signal = bool(_ML_OR_RESEARCH_SIGNALS.search(normalized))
    if not has_ml_signal:
        detail = (
            "일반 대화로 판단되었습니다."
            if _GENERAL_CONVERSATION_SIGNALS.search(normalized)
            else "검증 가능한 데이터/ML 가설로 판단하기 어렵습니다."
        )
        return ScreeningResult(
            False,
            "not_ml",
            f"{detail} 변수, 예상 관계, 목표 지표를 포함해 가설 형태로 작성해 주세요.",
        )

    return ScreeningResult(True, "allowed", "사전 필터를 통과했습니다.")
