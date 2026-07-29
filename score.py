"""여러 지표 조건을 긍정/부정으로 집계해 종합 판독을 낸다.

이건 '지표가 지금 어느 쪽으로 읽히는가'에 대한 기계적 집계다.
매수·매도 권유가 아니고, 앞으로의 주가를 예측하지도 않는다.
지표는 이미 일어난 가격 움직임을 요약할 뿐이다.
"""

from __future__ import annotations

import pandas as pd

POSITIVE = "긍정"
NEGATIVE = "부정"
NEUTRAL = "판단 불가"


def evaluate(df: pd.DataFrame, rsi_col: str) -> dict:
    """8개 조건을 집계해 종합 판독과 근거 목록을 돌려준다."""
    last = df.iloc[-1]
    close = last["Close"]
    checks: list[dict] = []

    def add(name: str, verdict: str, reason: str) -> None:
        checks.append({"조건": name, "판정": verdict, "근거": reason})

    # 1~3. 종가와 각 이동평균의 위치.
    # 종가가 없으면 비교 자체가 성립하지 않는다. 그냥 두면 NaN 비교가 False 로
    # 떨어져 세 항목이 조용히 '부정'으로 집계되므로 반드시 걸러낸다.
    for col, label in (("SMA20", "단기 추세"), ("SMA50", "중기 추세"), ("SMA200", "장기 추세")):
        val = last.get(col)
        if pd.isna(close):
            add(label, NEUTRAL, "종가가 없어 비교할 수 없음")
            continue
        if pd.isna(val):
            add(label, NEUTRAL, f"{col} 아직 계산 안 됨 (조회 기간 부족)")
            continue
        gap = (close / val - 1) * 100
        verdict = POSITIVE if close >= val else NEGATIVE
        add(label, verdict, f"종가가 {col}({val:,.2f}) 대비 {gap:+.1f}%")

    # 4. 이동평균 배열
    s20, s50 = last.get("SMA20"), last.get("SMA50")
    if pd.isna(s20) or pd.isna(s50):
        add("이동평균 배열", NEUTRAL, "SMA20/50 아직 계산 안 됨")
    else:
        verdict = POSITIVE if s20 >= s50 else NEGATIVE
        add(
            "이동평균 배열",
            verdict,
            f"SMA20({s20:,.2f})이 SMA50({s50:,.2f}) " + ("위 (정배열)" if verdict == POSITIVE else "아래 (역배열)"),
        )

    # 5. MACD 히스토그램 부호
    hist = last.get("MACD_HIST")
    if pd.isna(hist):
        add("MACD 교차 상태", NEUTRAL, "MACD 아직 계산 안 됨")
    else:
        verdict = POSITIVE if hist >= 0 else NEGATIVE
        add(
            "MACD 교차 상태",
            verdict,
            f"히스토그램 {hist:+.3f} — MACD선이 시그널선 " + ("위" if verdict == POSITIVE else "아래"),
        )

    # 6. MACD 0선 위치
    macd = last.get("MACD")
    if pd.isna(macd):
        add("MACD 0선", NEUTRAL, "MACD 아직 계산 안 됨")
    else:
        verdict = POSITIVE if macd >= 0 else NEGATIVE
        add("MACD 0선", verdict, f"MACD {macd:+.3f} — 0선 " + ("위" if verdict == POSITIVE else "아래"))

    # 7. RSI 중심선
    rsi = last.get(rsi_col)
    if pd.isna(rsi):
        add("RSI 방향", NEUTRAL, "RSI 아직 계산 안 됨")
    else:
        verdict = POSITIVE if rsi >= 50 else NEGATIVE
        add("RSI 방향", verdict, f"RSI {rsi:.1f} — 중심선 50 " + ("위" if verdict == POSITIVE else "아래"))

    # 8. 볼린저 밴드 내 위치
    pb = last.get("BB_PERCENT_B")
    if pd.isna(pb):
        add("볼린저 위치", NEUTRAL, "볼린저 밴드 아직 계산 안 됨")
    else:
        verdict = POSITIVE if pb >= 0.5 else NEGATIVE
        add("볼린저 위치", verdict, f"%B {pb:.2f} — 밴드 " + ("상단쪽" if verdict == POSITIVE else "하단쪽"))

    pos = sum(1 for c in checks if c["판정"] == POSITIVE)
    neg = sum(1 for c in checks if c["판정"] == NEGATIVE)
    undecided = sum(1 for c in checks if c["판정"] == NEUTRAL)
    decided = pos + neg

    if decided == 0:
        verdict = NEUTRAL
    elif pos > neg:
        verdict = POSITIVE
    elif neg > pos:
        verdict = NEGATIVE
    else:
        verdict = "중립"

    # 한쪽으로 얼마나 쏠렸는지 (0.5 = 완전히 반반)
    lean = max(pos, neg) / decided if decided else 0.0
    thin = decided < len(checks) / 2  # 절반도 판정 못 했으면 근거가 얇다

    if decided == 0:
        strength = "판단 불가"
    elif thin:
        strength = f"근거 부족 — {len(checks)}개 중 {decided}개만 판정됨"
    elif lean >= 0.85:
        strength = "뚜렷함"
    elif lean >= 0.65:
        strength = "우세함"
    else:
        strength = "혼조 — 조건이 거의 반반으로 갈림"

    # 집계가 놓치는 맥락은 따로 경고로 붙인다
    warnings: list[str] = []
    if not pd.isna(rsi):
        if rsi >= 70:
            warnings.append(
                f"RSI {rsi:.1f} — 관례적 과매수 구간입니다. 위 조건 대부분이 '긍정'으로 잡히는 건 "
                "이미 많이 올랐기 때문이며, 그 자체로 더 오른다는 뜻은 아닙니다."
            )
        elif rsi <= 30:
            warnings.append(
                f"RSI {rsi:.1f} — 관례적 과매도 구간입니다. 조건이 '부정'으로 몰리는 건 "
                "이미 많이 내렸기 때문이며, 그 자체로 더 내린다는 뜻은 아닙니다."
            )
    if thin and decided:
        warnings.append(
            f"조회 기간이 짧아 {len(checks)}개 조건 중 {undecided}개를 판정하지 못했습니다. "
            "조회 기간을 늘려야 의미 있는 판독이 나옵니다."
        )
    elif decided and lean < 0.65:
        warnings.append("조건이 팽팽하게 갈립니다. 이럴 때의 종합 판독은 신뢰도가 낮습니다.")

    return {
        "판독": verdict,
        "강도": strength,
        "긍정": pos,
        "부정": neg,
        "판단불가": undecided,
        "조건수": len(checks),
        "쏠림": lean,
        "항목": checks,
        "경고": warnings,
    }
