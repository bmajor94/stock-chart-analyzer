"""기술적 지표 계산 함수 모음.

모든 함수는 pandas Series/DataFrame을 받아 같은 인덱스의 결과를 돌려준다.
외부 지표 라이브러리(TA-Lib 등) 의존성 없이 pandas만 사용한다.
"""

from __future__ import annotations

import pandas as pd


def sma(close: pd.Series, window: int) -> pd.Series:
    """단순이동평균."""
    return close.rolling(window=window, min_periods=window).mean()


def ema(close: pd.Series, span: int) -> pd.Series:
    """지수이동평균."""
    return close.ewm(span=span, adjust=False, min_periods=span).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI (Wilder 방식 평활).

    상승분/하락분의 평활 평균 비율로 0~100 사이 값을 만든다.
    """
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    # Wilder 평활 = alpha 1/period 인 지수평균
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss
    out = 100.0 - (100.0 / (1.0 + rs))
    # 하락분이 전혀 없는 구간은 rs 가 inf → RSI 100
    return out.where(avg_loss != 0, 100.0).where(avg_gain.notna())


def macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """MACD 선, 시그널 선, 히스토그램."""
    macd_line = (
        close.ewm(span=fast, adjust=False).mean()
        - close.ewm(span=slow, adjust=False).mean()
    )
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    # slow 기간 이전 값은 워밍업 구간이라 신뢰할 수 없어 잘라낸다
    macd_line.iloc[: slow - 1] = float("nan")
    signal_line.iloc[: slow + signal - 2] = float("nan")
    return pd.DataFrame(
        {
            "macd": macd_line,
            "signal": signal_line,
            "hist": macd_line - signal_line,
        }
    )


def bollinger(close: pd.Series, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    """볼린저 밴드 (중심선, 상단, 하단, %B, 밴드폭)."""
    mid = close.rolling(window=window, min_periods=window).mean()
    std = close.rolling(window=window, min_periods=window).std(ddof=0)
    upper = mid + num_std * std
    lower = mid - num_std * std
    width = (upper - lower) / mid
    percent_b = (close - lower) / (upper - lower)
    return pd.DataFrame(
        {
            "mid": mid,
            "upper": upper,
            "lower": lower,
            "width": width,
            "percent_b": percent_b,
        }
    )


def volume_ma(volume: pd.Series, window: int = 20) -> pd.Series:
    """거래량 이동평균."""
    return volume.rolling(window=window, min_periods=window).mean()


def build(
    df: pd.DataFrame,
    sma_windows: tuple[int, ...] = (20, 50, 200),
    ema_spans: tuple[int, ...] = (12, 26),
    rsi_period: int = 14,
    macd_params: tuple[int, int, int] = (12, 26, 9),
    bb_window: int = 20,
    bb_std: float = 2.0,
    vol_ma_window: int = 20,
) -> pd.DataFrame:
    """OHLCV 데이터프레임에 모든 지표 컬럼을 붙여서 돌려준다."""
    out = df.copy()
    close = out["Close"]

    for w in sma_windows:
        out[f"SMA{w}"] = sma(close, w)
    for s in ema_spans:
        out[f"EMA{s}"] = ema(close, s)

    out[f"RSI{rsi_period}"] = rsi(close, rsi_period)

    m = macd(close, *macd_params)
    out["MACD"] = m["macd"]
    out["MACD_SIGNAL"] = m["signal"]
    out["MACD_HIST"] = m["hist"]

    bb = bollinger(close, bb_window, bb_std)
    out["BB_MID"] = bb["mid"]
    out["BB_UPPER"] = bb["upper"]
    out["BB_LOWER"] = bb["lower"]
    out["BB_WIDTH"] = bb["width"]
    out["BB_PERCENT_B"] = bb["percent_b"]

    out[f"VOL_MA{vol_ma_window}"] = volume_ma(out["Volume"], vol_ma_window)

    return out
