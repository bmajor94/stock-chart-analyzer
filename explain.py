"""지표 숫자를 평이한 한국어 문장으로 옮긴다.

전부 '지금 값이 어디에 있는지'에 대한 사실 서술이다. 앞으로의 주가를 예측하지
않으며 매수·매도 판단을 담지 않는다.
"""

from __future__ import annotations

import pandas as pd


def _pct(a: float, b: float) -> float:
    return (a / b - 1.0) * 100.0


def _trend(last: pd.Series) -> tuple[str, list[str]]:
    close = last["Close"]
    if pd.isna(close):
        return "판단 불가", ["종가가 없어 이동평균과 비교할 수 없습니다."]

    lines: list[str] = []
    above = 0
    total = 0

    for col, name in (("SMA20", "단기(20)"), ("SMA50", "중기(50)"), ("SMA200", "장기(200)")):
        val = last.get(col)
        if pd.isna(val):
            continue
        total += 1
        gap = _pct(close, val)
        if gap >= 0:
            above += 1
        lines.append(f"{name} 이동평균 {val:,.2f} 대비 **{gap:+.1f}%**")

    if total == 0:
        return "판단 불가", ["조회 기간이 짧아 이동평균이 아직 만들어지지 않았습니다."]

    if above == total:
        headline = f"이동평균 {total}개를 모두 위에 두고 있음"
    elif above == 0:
        headline = f"이동평균 {total}개를 모두 아래에 두고 있음"
    else:
        headline = f"이동평균 {total}개 중 {above}개 위, {total - above}개 아래"

    return headline, lines


def _rsi(last: pd.Series, rsi_col: str) -> tuple[str, list[str]]:
    val = last.get(rsi_col)
    if pd.isna(val):
        return "판단 불가", ["조회 기간이 짧아 RSI가 아직 계산되지 않았습니다."]

    if val >= 70:
        zone = "관례적 과매수 구간(70 이상)"
    elif val <= 30:
        zone = "관례적 과매도 구간(30 이하)"
    elif val >= 60:
        zone = "과매수 기준선(70)에 가까움"
    elif val <= 40:
        zone = "과매도 기준선(30)에 가까움"
    else:
        zone = "중립 구간(30~70 사이)"

    return f"{val:.1f} — {zone}", [
        "RSI는 최근 상승폭과 하락폭의 비율입니다. 높을수록 최근에 많이 올랐다는 뜻이지, "
        "앞으로 떨어진다는 뜻은 아닙니다."
    ]


def _bollinger(last: pd.Series, df: pd.DataFrame) -> tuple[str, list[str]]:
    pb = last.get("BB_PERCENT_B")
    if pd.isna(pb):
        return "판단 불가", ["조회 기간이 짧아 볼린저 밴드가 아직 계산되지 않았습니다."]

    if pb >= 1:
        where = "상단 밴드 위로 나감"
    elif pb >= 0.8:
        where = "상단 밴드 부근"
    elif pb <= 0:
        where = "하단 밴드 아래로 나감"
    elif pb <= 0.2:
        where = "하단 밴드 부근"
    else:
        where = "밴드 중간쯤"

    lines = [f"%B **{pb:.2f}** (0 = 하단 밴드, 1 = 상단 밴드)"]

    width = last.get("BB_WIDTH")
    hist = df["BB_WIDTH"].dropna()
    if not pd.isna(width) and len(hist) > 20:
        rank = (hist < width).mean() * 100
        verdict = (
            "평소보다 좁습니다 (변동성 축소)."
            if rank < 25
            else "평소보다 넓습니다 (변동성 확대)."
            if rank > 75
            else "평소 수준입니다."
        )
        lines.append(
            f"밴드폭 {width:.3f} — 조회 구간에서 {rank:.0f} 백분위. {verdict}"
        )

    return where, lines


def _macd(last: pd.Series, df: pd.DataFrame) -> tuple[str, list[str]]:
    hist = last.get("MACD_HIST")
    if pd.isna(hist):
        return "판단 불가", ["조회 기간이 짧아 MACD가 아직 계산되지 않았습니다."]

    side = "MACD선이 시그널선 **위**" if hist >= 0 else "MACD선이 시그널선 **아래**"

    lines = [f"히스토그램 **{hist:+.3f}** — {side}에 있습니다."]

    recent = df["MACD_HIST"].dropna().tail(5)
    if len(recent) >= 3:
        if recent.iloc[-1] > recent.iloc[0]:
            lines.append("최근 5개 봉 동안 히스토그램이 커지는 쪽으로 움직였습니다.")
        elif recent.iloc[-1] < recent.iloc[0]:
            lines.append("최근 5개 봉 동안 히스토그램이 줄어드는 쪽으로 움직였습니다.")

    return side.replace("**", ""), lines


def _volume(last: pd.Series, vol_ma_col: str) -> tuple[str, list[str]]:
    vol = last.get("Volume")
    avg = last.get(vol_ma_col)
    if pd.isna(vol) or pd.isna(avg) or avg == 0:
        return "판단 불가", ["거래량 평균이 아직 계산되지 않았습니다."]

    ratio = vol / avg * 100
    if ratio >= 150:
        note = "평소보다 크게 많음"
    elif ratio >= 110:
        note = "평소보다 다소 많음"
    elif ratio <= 60:
        note = "평소보다 크게 적음"
    elif ratio <= 90:
        note = "평소보다 다소 적음"
    else:
        note = "평소 수준"

    return f"평균의 {ratio:.0f}% — {note}", [
        f"최근 봉 {vol:,.0f}주 / 평균 {avg:,.0f}주"
    ]


def build(df: pd.DataFrame, rsi_col: str, vol_ma_col: str) -> list[dict]:
    """해설 카드 목록. 각 항목은 {제목, 요약, 상세}."""
    last = df.iloc[-1]

    sections = [
        ("추세", _trend(last)),
        ("과열도 (RSI)", _rsi(last, rsi_col)),
        ("변동성 (볼린저 밴드)", _bollinger(last, df)),
        ("모멘텀 (MACD)", _macd(last, df)),
        ("거래량", _volume(last, vol_ma_col)),
    ]

    return [
        {"제목": title, "요약": headline, "상세": details}
        for title, (headline, details) in sections
    ]
