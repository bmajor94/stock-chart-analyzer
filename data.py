"""yfinance 데이터 수집 계층."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import yfinance as yf

OHLCV = ["Open", "High", "Low", "Close", "Volume"]

# Yahoo 가 응답을 안 주면 호출이 무한정 매달린다. 로컬에선 티가 안 나지만
# 클라우드에서는 페이지 전체가 회색으로 멈춘 채 끝나지 않는다.
_POOL = ThreadPoolExecutor(max_workers=4)


def _bounded(fn, seconds: float, default):
    """제한 시간 안에 못 끝내면 포기한다. 없는 값이 멈춘 화면보다 낫다."""
    # ponytail: 시간 초과해도 스레드는 남는다. 요청이 끝나면 알아서 정리된다.
    #           문제가 되면 세션 단위 취소로 바꾼다.
    try:
        return _POOL.submit(fn).result(timeout=seconds)
    except Exception:
        return default


def is_intraday(interval: str) -> bool:
    """분봉·시간봉이면 True. 시간외 거래는 이 경우에만 받을 수 있다."""
    return interval.endswith(("m", "h"))


def fetch(
    ticker: str,
    period: str = "1y",
    interval: str = "1d",
    prepost: bool = False,
) -> pd.DataFrame:
    """단일 종목의 OHLCV를 받아 평평한 컬럼의 DataFrame으로 돌려준다.

    yfinance는 종목이 하나여도 (필드, 티커) MultiIndex 컬럼을 주므로 여기서 편다.

    prepost=True 면 프리마켓·애프터마켓 봉까지 포함한다. 단 일봉 이상에서는
    Yahoo가 이 옵션을 무시하므로 정규장 데이터만 돌아온다.
    """
    df = yf.download(
        ticker,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
        threads=False,
        prepost=prepost and is_intraday(interval),
        timeout=20,
    )

    if df is None or df.empty:
        raise ValueError(f"'{ticker}' 데이터를 가져오지 못했습니다. 티커를 확인해 주세요.")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    missing = [c for c in OHLCV if c not in df.columns]
    if missing:
        raise ValueError(f"'{ticker}' 응답에 {missing} 컬럼이 없습니다.")

    df = df[OHLCV]

    # 종가 없는 봉은 봉이 아니다. Yahoo 가 요청을 막을 때 형태만 갖추고 값은
    # 전부 NaN 인 응답을 주는데, df.empty 검사만으로는 이걸 걸러내지 못해
    # 화면에 'nan' 이 그대로 찍힌다.
    df = df[df["Close"].notna()]

    if df.empty:
        raise ValueError(
            f"'{ticker}' 응답에 유효한 가격이 없습니다. "
            "Yahoo 가 일시적으로 요청을 거부했을 수 있습니다. "
            "잠시 뒤 '데이터 새로고침'을 눌러 보세요."
        )

    df.index = pd.to_datetime(df.index)
    return df


REGULAR_OPEN = pd.Timestamp("09:30").time()
REGULAR_CLOSE = pd.Timestamp("16:00").time()


def extended_hours_mask(index: pd.DatetimeIndex) -> pd.Series:
    """정규장(09:30~16:00) 밖의 봉을 True로 표시한다.

    yfinance 인트라데이 인덱스는 거래소 현지시각(미국 주식이면 US/Eastern)이라
    시각을 그대로 비교하면 된다.

    일봉 이상은 인덱스 시각이 전부 자정이라 그냥 비교하면 모든 봉이 장 시작 전으로
    잡힌다. 그런 경우는 시간외 개념이 없으므로 전부 False로 돌려준다.
    """
    times = pd.Series(index.time, index=index)
    if (times == pd.Timestamp("00:00").time()).all():
        return pd.Series(False, index=index)
    return (times < REGULAR_OPEN) | (times >= REGULAR_CLOSE)


def session_hours(interval: str, prepost: bool) -> tuple[float, float] | None:
    """인트라데이 차트에서 x축에 남겨둘 시간대 (시작, 끝). 일봉 이상은 None.

    정규장은 09:30~16:00, 시간외까지 받으면 04:00~20:00 (모두 미 동부시각).
    """
    if not is_intraday(interval):
        return None
    return (4.0, 20.0) if prepost else (9.5, 16.0)


MARKET_STATE = {
    "REGULAR": "정규장",
    "PRE": "프리마켓",
    "PREPRE": "장 시작 전",
    "POST": "애프터마켓",
    "POSTPOST": "장 마감 후",
    "CLOSED": "휴장",
}


def quote(ticker: str) -> dict:
    """차트 밖의 최신 체결가. 일봉은 정규장만 담으므로 시간외 움직임은 여기서만 보인다."""
    i = _bounded(lambda: yf.Ticker(ticker).info or {}, seconds=8, default=None)
    if not i:
        return {}

    state = i.get("marketState") or ""
    regular = i.get("regularMarketPrice")

    # 시간외 가격이 있으면 그게 가장 최근 체결가다. 기준선은 그날 정규장 종가.
    pre, post = i.get("preMarketPrice"), i.get("postMarketPrice")
    if state.startswith("PRE") and pre is not None:
        price, base = pre, regular
    elif post is not None:
        price, base = post, regular
    else:
        price, base = regular, i.get("regularMarketPreviousClose")

    if price is None:
        return {}
    return {
        "가격": price,
        "기준": base,
        "장상태": MARKET_STATE.get(state, state or "—"),
        "시간외": price is not regular,
    }


def profile(ticker: str) -> dict:
    """종목명·거래소·통화 등 표시용 메타데이터. 실패해도 예외를 던지지 않는다."""
    info = _bounded(lambda: yf.Ticker(ticker).info or {}, seconds=8, default=None)
    if not info:
        return {}
    return {
        "name": info.get("longName") or info.get("shortName") or "",
        "exchange": info.get("fullExchangeName") or info.get("exchange") or "",
        "currency": info.get("currency") or "",
        "sector": info.get("sector") or "",
    }
