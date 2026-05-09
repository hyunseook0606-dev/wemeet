"""
llm_reporter.py — 해상 리스크 자동 보고서 생성기
우선순위:
  1. Google Gemini 1.5 Flash (무료, GEMINI_API_KEY)
  2. Claude Haiku 4.5 (유료 $5/월, ANTHROPIC_API_KEY)
환경변수에 따라 자동 선택.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Iterator

import pandas as pd

# 시스템 프롬프트 — 캐싱 대상 (매 호출마다 동일)
_SYSTEM_PROMPT = """당신은 위밋모빌리티의 해상 리스크 분석 전문가입니다.
MRI(Maritime Risk Index) 데이터와 해사 뉴스를 분석해 중소 수출기업 화주를 위한
간결하고 실용적인 리스크 보고서를 작성합니다.

보고서 작성 규칙:
- 전문 용어는 괄호 안에 한글 설명 병기
- 화주 관점에서 즉시 취할 행동 제시
- 수치는 반드시 구체적으로 (예: +30%, +14일)
- 총 500자 이내로 간결하게
- 마크다운 형식 사용

출력 형식:
## 🚨 오늘의 해상 리스크 현황
**MRI 등급**: [등급]
**핵심 리스크**: [1-2문장]

## 📋 화주 권고 행동
1. [즉시 조치]
2. [준비 사항]

## 📊 시나리오 전망
[해당 시나리오 및 예상 영향]"""


def _build_user_prompt(today_mri, mri_grade, top_category, scenario_id,
                       scenario_name, news_headlines, affected_count, cost_delta) -> str:
    headlines_text = '\n'.join(f'- {h}' for h in news_headlines[:8])
    return f"""다음 데이터로 오늘의 해상 리스크 보고서를 작성하세요.

**오늘 날짜**: {datetime.today().strftime('%Y년 %m월 %d일')}
**MRI 점수**: {today_mri:.3f} ({mri_grade})
**주요 리스크 카테고리**: {top_category}
**자동 분류 시나리오**: {scenario_id} ({scenario_name})
**영향 받는 출하**: {affected_count}건
**운임 비용 변화**: ${cost_delta:+,}

**오늘의 해사 뉴스 헤드라인**:
{headlines_text}

위 데이터를 바탕으로 화주가 즉시 활용할 수 있는 리스크 보고서를 작성하세요."""


def generate_risk_report(
    today_mri: float,
    mri_grade: str,
    top_category: str,
    scenario_id: str,
    scenario_name: str,
    news_headlines: list[str],
    affected_count: int = 0,
    cost_delta: int = 0,
) -> Iterator[str]:
    """
    MRI 데이터 → 스트리밍 보고서.
    Gemini(무료) 우선, 없으면 Claude Haiku(유료) 사용.
    yields: 텍스트 청크
    """
    gemini_key    = os.environ.get('GEMINI_API_KEY', '')
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY', '')

    user_prompt = _build_user_prompt(
        today_mri, mri_grade, top_category, scenario_id,
        scenario_name, news_headlines, affected_count, cost_delta
    )

    if gemini_key:
        yield from _generate_gemini(gemini_key, user_prompt)
    elif anthropic_key:
        yield from _generate_claude(anthropic_key, user_prompt)
    else:
        yield (
            '⚠️ API 키가 없습니다.\n\n'
            '**무료**: `.env`에 `GEMINI_API_KEY=...` 추가  \n'
            '발급: https://aistudio.google.com → Get API key\n\n'
            '**유료**: `.env`에 `ANTHROPIC_API_KEY=...` 추가  \n'
            '발급: https://console.anthropic.com/settings/keys'
        )


def _generate_gemini(api_key: str, user_prompt: str) -> Iterator[str]:
    """Google Gemini 1.5 Flash — 무료 (일 1,500회 한도)."""
    try:
        import google.generativeai as genai
    except ImportError:
        yield '⚠️ google-generativeai 미설치 → pip install google-generativeai'
        return

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            system_instruction=_SYSTEM_PROMPT,
        )
        response = model.generate_content(user_prompt, stream=True)
        for chunk in response:
            if chunk.text:
                yield chunk.text
    except Exception as e:
        yield f'❌ Gemini 오류: {e}'


def _generate_claude(api_key: str, user_prompt: str) -> Iterator[str]:
    """Claude Haiku 4.5 — 프롬프트 캐싱 적용."""
    try:
        import anthropic
    except ImportError:
        yield '⚠️ anthropic 미설치 → pip install anthropic'
        return

    try:
        client = anthropic.Anthropic(api_key=api_key)
        with client.messages.stream(
            model='claude-haiku-4-5',
            max_tokens=1024,
            system=[{
                'type': 'text',
                'text': _SYSTEM_PROMPT,
                'cache_control': {'type': 'ephemeral'},
            }],
            messages=[{'role': 'user', 'content': user_prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text
    except Exception as e:
        yield f'❌ Claude 오류: {e}'


def active_llm_provider() -> str:
    """현재 사용 가능한 LLM 제공자 반환."""
    if os.environ.get('GEMINI_API_KEY'):
        return 'Google Gemini 1.5 Flash (무료)'
    if os.environ.get('ANTHROPIC_API_KEY'):
        return 'Claude Haiku 4.5 (유료 ~$5/월)'
    return '미설정'


def estimate_monthly_cost(calls_per_day: int = 24) -> dict:
    """월간 API 비용 추정 (Haiku 4.5 기준, 프롬프트 캐싱 적용)."""
    monthly_calls = calls_per_day * 30
    # 캐싱 미적용: 입력 3,000토큰 × $1/M + 출력 800토큰 × $5/M
    cost_no_cache = monthly_calls * (3_000 * 1e-6 + 800 * 5e-6)
    # 캐싱 적용: 시스템(1,500토큰) 캐시 읽기 $0.1/M + 나머지 $1/M
    cost_with_cache = monthly_calls * (1_500 * 0.1e-6 + 1_500 * 1e-6 + 800 * 5e-6)
    return {
        'monthly_calls':   monthly_calls,
        'cost_no_cache':   round(cost_no_cache, 2),
        'cost_with_cache': round(cost_with_cache, 2),
        'savings_pct':     round((1 - cost_with_cache / cost_no_cache) * 100, 1),
    }
