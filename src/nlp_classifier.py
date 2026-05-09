"""
nlp_classifier.py — 해운 도메인 키워드 사전 기반 뉴스 리스크 분류기
향후 KoBERT fine-tuning으로 교체 가능한 인터페이스 설계.
"""
from __future__ import annotations

import pandas as pd

from src.config import RISK_KEYWORDS, RISK_WEIGHTS, NEG_WORDS, POS_WORDS


def classify_risk(text: str) -> dict:
    """
    단일 뉴스 텍스트 → 리스크 카테고리 + 감성 판정.
    반환: {category, risk_weight, keyword_hits, sentiment}
    """
    scores = {
        cat: sum(1 for kw in kws if kw in text)
        for cat, kws in RISK_KEYWORDS.items()
    }
    best_cat = max(scores, key=scores.get)
    if scores[best_cat] == 0:
        best_cat = '정상'

    neg_cnt = sum(1 for w in NEG_WORDS if w in text)
    pos_cnt = sum(1 for w in POS_WORDS if w in text)
    if neg_cnt > pos_cnt:
        sentiment = 'negative'
    elif pos_cnt > neg_cnt:
        sentiment = 'positive'
    else:
        sentiment = 'neutral'

    return {
        'category':     best_cat,
        'risk_weight':  RISK_WEIGHTS.get(best_cat, 0.0),
        'keyword_hits': scores[best_cat],
        'sentiment':    sentiment,
    }


def classify_news_df(news_df: pd.DataFrame,
                     title_col: str = 'title',
                     text_col: str = 'text') -> pd.DataFrame:
    """
    뉴스 DataFrame 전체에 분류 적용 → 컬럼 추가 후 반환.
    """
    df = news_df.copy()
    combined = df[title_col].fillna('') + ' ' + df[text_col].fillna('')
    results = combined.map(classify_risk)
    df['pred_category']  = results.map(lambda r: r['category'])
    df['risk_weight']    = results.map(lambda r: r['risk_weight'])
    df['keyword_hits']   = results.map(lambda r: r['keyword_hits'])
    df['pred_sentiment'] = results.map(lambda r: r['sentiment'])
    return df


def top_category(news_df: pd.DataFrame) -> str:
    """분류된 뉴스 DataFrame에서 최다 출현 카테고리 반환."""
    if 'pred_category' not in news_df.columns or news_df.empty:
        return '정상'
    return news_df['pred_category'].mode()[0]
