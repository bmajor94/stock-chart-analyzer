"""지표 조건이 충족된 시점을 찾아낸다.

여기서 말하는 '신호'는 널리 쓰이는 관례적 조건이 충족된 날짜일 뿐이고,
매수·매도 권유가 아니다. 같은 조건에서 주가가 오르기도 내리기도 한다.
"""

from __future__ import annotations

import pandas as pd

# 신호 정의: 키 → (표시 이름, 그려질 패널, 방향)
# 방향 up/down 은 '조건의 성격'일 뿐 수익 방향을 뜻하지 않는다.
CATALOG = {
    "golden_cross": ("골든크로스", "price", "up"),
    "dead_cross": ("데드크로스", "price", "down"),
    "rsi_overbought": ("RSI 70 상향 돌파", "rsi", "down"),
    "rsi_oversold": ("RSI 30 하향 돌파", "rsi", "up"),
    "macd_bull_cross": ("MACD 상향 교차", "macd", "up"),
    "macd_bear_cross": ("MACD 하향 교차", "macd", "down"),
}

DESCRIPTION = {
    "golden_cross": "단기 이동평균(SMA20)이 장기(SMA50)를 아래에서 위로 통과",
    "dead_cross": "단기 이동평균(SMA20)이 장기(SMA50)를 위에서 아래로 통과",
    "rsi_overbought": "RSI가 과매수 기준선 70을 위로 통과",
    "rsi_oversold": "RSI가 과매도 기준선 30을 아래로 통과",
    "macd_bull_cross": "MACD선이 시그널선을 아래에서 위로 통과",
    "macd_bear_cross": "MACD선이 시그널선을 위에서 아래로 통과",
}


def _cross_up(a: pd.Series, b: pd.Series) -> pd.Series:
    """a가 b를 아래에서 위로 통과한 지점. 직전 값이 비어 있으면 False."""
    prev_a, prev_b = a.shift(1), b.shift(1)
    valid = a.notna() & b.notna() & prev_a.notna() & prev_b.notna()
    return valid & (prev_a <= prev_b) & (a > b)


def _cross_down(a: pd.Series, b: pd.Series) -> pd.Series:
    prev_a, prev_b = a.shift(1), b.shift(1)
    valid = a.notna() & b.notna() & prev_a.notna() & prev_b.notna()
    return valid & (prev_a >= prev_b) & (a < b)


def detect(df: pd.DataFrame, rsi_col: str) -> pd.DataFrame:
    """조건이 충족된 시점을 모아 (시각, 종류, 이름, 패널, 방향, 가격) 표로 돌려준다."""
    hits: dict[str, pd.Series] = {}

    if {"SMA20", "SMA50"} <= set(df.columns):
        hits["golden_cross"] = _cross_up(df["SMA20"], df["SMA50"])
        hits["dead_cross"] = _cross_down(df["SMA20"], df["SMA50"])

    if rsi_col in df:
        level70 = pd.Series(70.0, index=df.index)
        level30 = pd.Series(30.0, index=df.index)
        hits["rsi_overbought"] = _cross_up(df[rsi_col], level70)
        hits["rsi_oversold"] = _cross_down(df[rsi_col], level30)

    if {"MACD", "MACD_SIGNAL"} <= set(df.columns):
        hits["macd_bull_cross"] = _cross_up(df["MACD"], df["MACD_SIGNAL"])
        hits["macd_bear_cross"] = _cross_down(df["MACD"], df["MACD_SIGNAL"])

    rows = []
    for key, mask in hits.items():
        label, panel, direction = CATALOG[key]
        for ts in df.index[mask.fillna(False)]:
            rows.append(
                {
                    "시각": ts,
                    "kind": key,
                    "이름": label,
                    "panel": panel,
                    "direction": direction,
                    "가격": df.loc[ts, "Close"],
                    "rsi": df.loc[ts, rsi_col] if rsi_col in df else float("nan"),
                    "macd": df.loc[ts, "MACD"] if "MACD" in df else float("nan"),
                }
            )

    if not rows:
        return pd.DataFrame(
            columns=["시각", "kind", "이름", "panel", "direction", "가격", "rsi", "macd"]
        )
    return pd.DataFrame(rows).sort_values("시각").reset_index(drop=True)
