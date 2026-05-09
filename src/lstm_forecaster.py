"""
lstm_forecaster.py — LSTM 부산항 물동량 예측
시간순 분할 필수 (data leakage 방지). random_split 절대 금지.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_percentage_error

logger = logging.getLogger(__name__)

FEATURES = ['throughput', 'gdp_growth', 'exchange_rate', 'oil_price', 'mri']
LOOKBACK = 12
HORIZON  = 3


def _try_import_torch():
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import Dataset, DataLoader
        return torch, nn, Dataset, DataLoader
    except ImportError:
        return None, None, None, None


class _TSDataset:
    def __init__(self, data: np.ndarray, lookback: int, horizon: int):
        import torch
        self.X, self.y = [], []
        for i in range(len(data) - lookback - horizon + 1):
            self.X.append(data[i: i + lookback])
            self.y.append(data[i + lookback: i + lookback + horizon, 0])
        self.X = torch.FloatTensor(np.array(self.X))
        self.y = torch.FloatTensor(np.array(self.y))

    def __len__(self) -> int:
        return len(self.X)

    def __getitem__(self, idx: int):
        return self.X[idx], self.y[idx]


class _LSTMModel:
    """torch.nn.Module을 래핑해서 PyTorch 의존성을 런타임까지 지연."""

    def __new__(cls, in_dim: int = 5, hidden: int = 64, layers: int = 2, horizon: int = 3):
        import torch.nn as nn
        import torch

        class _Inner(nn.Module):
            def __init__(self):
                super().__init__()
                self.lstm = nn.LSTM(in_dim, hidden, layers,
                                    dropout=0.2, batch_first=True)
                self.fc = nn.Sequential(
                    nn.Linear(hidden, 32), nn.ReLU(),
                    nn.Dropout(0.2), nn.Linear(32, horizon),
                )

            def forward(self, x):
                out, _ = self.lstm(x)
                return self.fc(out[:, -1, :])

        torch.manual_seed(42)
        return _Inner()


def train_and_forecast(
    main_df: pd.DataFrame,
    epochs: int = 120,
    batch_size: int = 8,
    lr: float = 0.001,
    early_stop_patience: int = 20,
) -> dict:
    """
    LSTM 학습 후 3개월 예측 반환.
    반환: {future_real, mape_3m, train_losses, val_losses}
    PyTorch 미설치 시 더미 값 반환.

    [MAPE 계산 방식]
    검증셋 예측값·실제값을 역정규화(원래 TEU 단위)한 후 계산.
    정규화 공간 MAPE는 작은 값에서 과대 추정되므로 원단위 사용.

    [조기종료]
    early_stop_patience 에포크 동안 val_loss 개선 없으면 종료.
    과적합 방지 + 최적 가중치 자동 복원.
    """
    torch, nn, Dataset, DataLoader = _try_import_torch()
    if torch is None:
        logger.warning('PyTorch 미설치 — LSTM 건너뜀')
        recent_avg = float(main_df['throughput'].tail(6).mean())
        return {
            'future_real': np.array([recent_avg] * HORIZON),
            'mape_3m': -1.0,
            'train_losses': [],
            'val_losses': [],
        }

    scaler = MinMaxScaler()
    data_scaled = scaler.fit_transform(main_df[FEATURES])

    dataset = _TSDataset(data_scaled, LOOKBACK, HORIZON)
    train_size = int(len(dataset) * 0.80)
    # ★ 시간순 분할 — random_split 절대 금지
    import torch as _torch
    import copy
    train_ds = _torch.utils.data.Subset(dataset, list(range(train_size)))
    val_ds   = _torch.utils.data.Subset(dataset, list(range(train_size, len(dataset))))
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False)

    model = _LSTMModel(in_dim=len(FEATURES), horizon=HORIZON)
    opt   = _torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    crit  = nn.MSELoss()
    sched = _torch.optim.lr_scheduler.ReduceLROnPlateau(opt, factor=0.5, patience=8, min_lr=1e-5)

    train_losses, val_losses = [], []
    best_val_loss  = float('inf')
    best_weights   = None
    no_improve     = 0

    for epoch in range(epochs):
        model.train()
        tl = 0.0
        for X, y in train_loader:
            opt.zero_grad()
            loss = crit(model(X), y)
            loss.backward()
            _torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            tl += loss.item()
        train_losses.append(tl / len(train_loader))

        model.eval()
        vl = 0.0
        with _torch.no_grad():
            for X, y in val_loader:
                vl += crit(model(X), y).item()
        vl /= max(len(val_loader), 1)
        val_losses.append(vl)
        sched.step(vl)

        # 조기종료: 최적 가중치 저장
        if vl < best_val_loss - 1e-6:
            best_val_loss = vl
            best_weights  = copy.deepcopy(model.state_dict())
            no_improve    = 0
        else:
            no_improve += 1
            if no_improve >= early_stop_patience:
                logger.info('조기종료: epoch %d (best val_loss=%.5f)', epoch + 1, best_val_loss)
                break

    # 최적 가중치 복원
    if best_weights is not None:
        model.load_state_dict(best_weights)

    # 미래 예측
    model.eval()
    last_seq = _torch.FloatTensor(data_scaled[-LOOKBACK:]).unsqueeze(0)
    with _torch.no_grad():
        future_norm = model(last_seq).numpy()[0]

    dummy = np.zeros((HORIZON, len(FEATURES)))
    dummy[:, 0] = future_norm
    future_real = scaler.inverse_transform(dummy)[:, 0]

    # MAPE — 원래 TEU 단위로 역정규화 후 계산 (정규화 공간 MAPE 사용 금지)
    val_pred_norm, val_true_norm = [], []
    with _torch.no_grad():
        for X, y in val_loader:
            val_pred_norm.append(model(X).numpy())
            val_true_norm.append(y.numpy())
    val_pred_norm = np.concatenate(val_pred_norm)   # (N, HORIZON)
    val_true_norm = np.concatenate(val_true_norm)   # (N, HORIZON)

    # 역정규화: throughput (col 0) 만 복원
    def _denorm(norm_vals: np.ndarray) -> np.ndarray:
        out = []
        for row in norm_vals:
            d = np.zeros((len(row), len(FEATURES)))
            d[:, 0] = row
            out.append(scaler.inverse_transform(d)[:, 0])
        return np.array(out)

    val_pred_teu = _denorm(val_pred_norm).flatten()
    val_true_teu = _denorm(val_true_norm).flatten()
    mape_3m = float(mean_absolute_percentage_error(val_true_teu, val_pred_teu) * 100)

    return {
        'future_real':  future_real,
        'mape_3m':      mape_3m,
        'train_losses': train_losses,
        'val_losses':   val_losses,
    }


def build_main_df(
    dates: pd.DatetimeIndex,
    mri_series: np.ndarray,
    throughput_df: pd.DataFrame | None = None,
    exchange_rate_df: pd.DataFrame | None = None,
    oil_price_df: pd.DataFrame | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """
    부산항 물동량 + 거시경제 변수 통합 DataFrame 생성.
    실데이터(throughput_df / exchange_rate_df / oil_price_df) 우선 사용.
    없으면 시뮬로 폴백. 평균 약 200만 TEU/월 (2024년 실제 203만 TEU).
    """
    rng = np.random.default_rng(seed)
    M   = len(dates)

    # ── 물동량 ──
    if throughput_df is not None:
        dates_real = pd.date_range(
            throughput_df['date'].min(), throughput_df['date'].max(), freq='MS'
        )
        main_df = pd.DataFrame({'date': dates_real}).merge(
            throughput_df, on='date', how='left'
        )
        dates = dates_real
        M = len(dates)
    else:
        seasonal = np.tile([200, 185, 195, 198, 205, 210, 215, 220, 210, 200, 205, 220], 7)[:M]
        base = seasonal.copy().astype(float)
        covid    = (dates >= '2020-03-01') & (dates <= '2021-06-01')
        hong_hae = (dates >= '2023-12-01') & (dates <= '2024-06-01')
        tariff   = dates >= '2025-04-01'
        base[covid]    *= 0.88
        base[hong_hae] *= 0.94
        base[tariff]   *= 0.97
        main_df = pd.DataFrame({
            'date': dates,
            'throughput': np.clip(base + rng.normal(0, 6, M), 150, 260),
        })

    # ── GDP (시뮬만 가능, ECOS 필요) ──
    main_df['gdp_growth'] = rng.normal(2.5, 0.8, M) / 100

    # ── 환율 (실데이터 우선) ──
    if exchange_rate_df is not None:
        fx = (exchange_rate_df
              .set_index('date')['exchange_rate']
              .reindex(main_df['date'])
              .ffill().bfill()
              .values)
        main_df['exchange_rate'] = fx
        logger.info('환율: 실데이터 사용 (%d개월)', len(exchange_rate_df))
    else:
        main_df['exchange_rate'] = 1200 + np.cumsum(rng.normal(0, 15, M))

    # ── 유가 (실데이터 우선) ──
    if oil_price_df is not None:
        oil = (oil_price_df
               .set_index('date')['oil_price']
               .reindex(main_df['date'])
               .ffill().bfill()
               .values)
        main_df['oil_price'] = oil
        logger.info('유가: 실데이터 사용 (%d개월)', len(oil_price_df))
    else:
        main_df['oil_price'] = 70 + np.cumsum(rng.normal(0, 2, M))

    main_df = main_df.ffill().bfill()
    main_df['mri'] = np.interp(
        np.arange(M), np.linspace(0, M - 1, len(mri_series)), mri_series
    )
    return main_df.reset_index(drop=True)
