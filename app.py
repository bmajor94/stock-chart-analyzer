"""차트 지표 분석 대시보드 (Streamlit).

실행:  streamlit run app.py
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

import chart
import data
import explain
import indicators
import score as score_mod
import signals as sig_mod
import tickers as tk_mod
from theme import palette

st.set_page_config(page_title="차트 지표 분석", page_icon="📈", layout="wide")

# 인터벌별로 yfinance가 허용하는 조회 기간
PERIODS: dict[str, list[str]] = {
    "1d": ["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"],
    "1wk": ["1y", "2y", "5y", "10y", "max"],
    "1mo": ["5y", "10y", "max"],
    "1h": ["1mo", "3mo", "6mo", "1y", "2y"],
    "30m": ["5d", "1mo"],
    "15m": ["5d", "1mo"],
    "5m": ["5d", "1mo"],
}
INTERVAL_LABEL = {
    "1d": "일봉",
    "1wk": "주봉",
    "1mo": "월봉",
    "1h": "1시간",
    "30m": "30분",
    "15m": "15분",
    "5m": "5분",
}


@st.cache_data(ttl=60, show_spinner=False)
def load(ticker: str, period: str, interval: str, prepost: bool) -> pd.DataFrame:
    return data.fetch(ticker, period, interval, prepost)


@st.cache_data(ttl=86400, show_spinner=False)
def load_profile(ticker: str) -> dict:
    return data.profile(ticker)


# 갱신 주기(30초)보다 짧아야 매번 새 값을 받는다
@st.cache_data(ttl=20, show_spinner=False)
def load_quote(ticker: str) -> dict:
    return data.quote(ticker)


@st.cache_data(ttl=3600, show_spinner=False)
def search_tickers(query: str) -> list[dict]:
    return tk_mod.search(query)


def fmt(v, spec: str = ",.2f") -> str:
    """NaN 을 화면에 'nan' 으로 흘리지 않는다. 값이 없으면 —."""
    return "—" if v is None or pd.isna(v) else format(v, spec)


def detected_mode() -> str:
    """스트림릿이 실제로 그리고 있는 테마(light/dark)를 알아낸다."""
    try:
        return st.context.theme.type or "light"
    except Exception:
        return st.get_option("theme.base") or "light"


# ─────────────────────────── 사이드바 ───────────────────────────
with st.sidebar:
    st.header("설정")

    pick_mode = st.radio(
        "종목 고르기",
        options=["우량주 목록", "직접 검색"],
        horizontal=True,
        help="목록은 눌러서 열고 그냥 타이핑하면 걸러집니다. 'nv'도 '엔비'도 엔비디아를 찾습니다.",
    )

    if pick_mode == "우량주 목록":
        ticker = st.selectbox(
            "종목",
            options=tk_mod.TICKERS,
            index=tk_mod.TICKERS.index("NVDA"),
            format_func=tk_mod.label,
        )
    else:
        query = st.text_input(
            "종목명 또는 티커",
            placeholder="apple, nvidia, TSLA …",
            help="Yahoo 검색은 한글을 못 알아듣습니다. 영문명이나 티커를 넣으세요.",
        )
        hits = search_tickers(query) if query else []
        if query and not hits:
            st.warning("검색 결과가 없습니다. 영문명이나 티커로 다시 시도해 보세요.")
            st.stop()
        if hits:
            ticker = st.selectbox(
                "검색 결과",
                options=[h["티커"] for h in hits],
                format_func=lambda t: next(
                    f"{t} · {h['이름']} ({h['거래소']})" for h in hits if h["티커"] == t
                ),
            )
        else:
            st.info("위에 종목명이나 티커를 입력하세요.")
            st.stop()

    interval = st.selectbox(
        "봉 주기",
        options=list(PERIODS),
        index=0,
        format_func=lambda k: INTERVAL_LABEL[k],
    )
    periods = PERIODS[interval]
    period = st.selectbox(
        "조회 기간",
        options=periods,
        index=min(3, len(periods) - 1),
    )

    intraday = data.is_intraday(interval)
    if intraday:
        prepost = st.checkbox(
            "시간외 거래 포함",
            value=False,
            help="프리마켓(04:00~09:30)·애프터마켓(16:00~20:00) 봉까지 받습니다. "
            "차트에서 옅은 배경으로 표시됩니다.",
        )
    else:
        prepost = False
        st.caption("시간외 거래는 분봉·시간봉에서만 볼 수 있습니다. (일봉 이상은 정규장만 집계)")

    st.divider()
    st.subheader("이동평균")
    ma_cols: list[str] = []
    c1, c2 = st.columns(2)
    with c1:
        if st.checkbox("SMA 20", value=True):
            ma_cols.append("SMA20")
        if st.checkbox("SMA 50", value=True):
            ma_cols.append("SMA50")
        if st.checkbox("SMA 200", value=True):
            ma_cols.append("SMA200")
    with c2:
        if st.checkbox("EMA 12", value=False):
            ma_cols.append("EMA12")
        if st.checkbox("EMA 26", value=False):
            ma_cols.append("EMA26")

    st.divider()
    st.subheader("보조 지표")
    show_bb = st.checkbox("볼린저 밴드", value=True)
    show_volume = st.checkbox("거래량", value=True)
    show_rsi = st.checkbox("RSI", value=True)
    show_macd = st.checkbox("MACD", value=True)

    st.divider()
    st.subheader("해설")
    show_explain = st.checkbox("지표 해설 보기", value=True)
    show_signals = st.checkbox(
        "신호 표시",
        value=True,
        help="골든/데드크로스, RSI 70·30 돌파, MACD 교차가 일어난 봉에 마커를 찍습니다.",
    )

    with st.expander("파라미터 조정"):
        rsi_period = st.number_input("RSI 기간", 2, 100, 14)
        bb_window = st.number_input("볼린저 기간", 5, 200, 20)
        bb_std = st.number_input("볼린저 표준편차 배수", 0.5, 4.0, 2.0, step=0.5)
        macd_fast = st.number_input("MACD 단기", 2, 100, 12)
        macd_slow = st.number_input("MACD 장기", 3, 200, 26)
        macd_signal = st.number_input("MACD 시그널", 2, 100, 9)
        vol_ma_window = st.number_input("거래량 이동평균 기간", 2, 200, 20)

    st.divider()
    theme_choice = st.radio(
        "차트 테마",
        options=["자동", "라이트", "다크"],
        horizontal=True,
        help="'자동'은 스트림릿 테마를 따라갑니다.",
    )

    if st.button("데이터 새로고침", width="stretch"):
        st.cache_data.clear()
        st.rerun()

# ─────────────────────────── 데이터 ───────────────────────────
try:
    with st.spinner(f"{ticker} 데이터를 불러오는 중…"):
        raw = load(ticker, period, interval, prepost)
except Exception as exc:  # noqa: BLE001 — 사용자에게 그대로 보여준다
    st.error(str(exc))
    st.stop()

if macd_fast >= macd_slow:
    st.warning("MACD 단기 기간이 장기 기간보다 짧아야 합니다. 기본값(12/26)으로 계산합니다.")
    macd_fast, macd_slow = 12, 26

df = indicators.build(
    raw,
    rsi_period=int(rsi_period),
    macd_params=(int(macd_fast), int(macd_slow), int(macd_signal)),
    bb_window=int(bb_window),
    bb_std=float(bb_std),
    vol_ma_window=int(vol_ma_window),
)

rsi_col = f"RSI{int(rsi_period)}"
rsi_label = f"RSI {int(rsi_period)}"
vol_ma_col = f"VOL_MA{int(vol_ma_window)}"
last = df.iloc[-1]
prev = df.iloc[-2] if len(df) > 1 else last
meta = load_profile(ticker)
currency = meta.get("currency") or "USD"

# ─────────────────────────── 헤더 ───────────────────────────
# 우량주 목록에 있으면 한글 이름을 먼저 보여준다
korean = tk_mod.korean_name(ticker)
display_name = korean or meta.get("name") or ""
st.title(f"{ticker} · {display_name}" if display_name else ticker)

caption = [INTERVAL_LABEL[interval], f"{len(df):,}개 봉"]
if prepost:
    caption.append("시간외 포함")
if meta.get("exchange"):
    caption.insert(0, meta["exchange"])
# 한글명을 제목에 썼으면 원래 영문명은 캡션에 남긴다
if korean and meta.get("name"):
    caption.insert(0, meta["name"])
caption.append(f"최종 {df.index[-1]:%Y-%m-%d %H:%M}" if interval.endswith(("m", "h")) else f"최종 {df.index[-1]:%Y-%m-%d}")
st.caption(" · ".join(caption))

change = last["Close"] - prev["Close"]
pct = change / prev["Close"] * 100 if prev["Close"] else float("nan")
delta = (
    None
    if pd.isna(change) or pd.isna(pct)
    else f"{change:+,.2f} ({pct:+.2f}%)"
)

@st.fragment(run_every="30s")
def metric_row() -> None:
    """30초마다 이 블록만 다시 그린다. 차트와 지표는 다시 계산하지 않는다."""
    live = load_quote(ticker)

    cols = st.columns(5 if live else 4)
    m1, m2, m3, m4 = cols[0], cols[-3], cols[-2], cols[-1]

    if live:
        gap = live["가격"] - live["기준"] if live["기준"] else None
        cols[1].metric(
            f"현재가 · {live['장상태']}",
            fmt(live["가격"]),
            None if gap is None else f"{gap:+,.2f} ({gap / live['기준'] * 100:+.2f}%)",
            help="차트 마지막 봉 이후의 최신 체결가입니다. 시간외 체결도 포함합니다.",
        )
        cols[1].caption(f"{datetime.now():%H:%M:%S} 갱신")

    m1.metric(f"종가 ({currency})", fmt(last["Close"]), delta)
    m2.metric(
        rsi_label,
        fmt(last[rsi_col], ".1f"),
        help="0~100. 관례적으로 70 위는 과매수, 30 아래는 과매도 구간으로 부릅니다.",
    )
    m3.metric(
        "MACD 히스토그램",
        fmt(last["MACD_HIST"], "+.2f"),
        help="MACD선 − 시그널선. 양수면 MACD선이 시그널선 위에 있습니다.",
    )
    m4.metric(
        "볼린저 %B",
        fmt(last["BB_PERCENT_B"], ".2f"),
        help="1.0 = 상단 밴드, 0.0 = 하단 밴드.",
    )


metric_row()

# ─────────────────────── 종합 판독 ───────────────────────
verdict = score_mod.evaluate(df, rsi_col)
BADGE = {"긍정": "🟢", "부정": "🔴", "중립": "⚪", "판단 불가": "⚪"}

st.subheader("종합 판독")
v1, v2 = st.columns([1, 2])
with v1:
    st.markdown(f"## {BADGE[verdict['판독']]} {verdict['판독']}")
    st.caption(verdict["강도"])
with v2:
    st.markdown(
        f"**{verdict['조건수']}개 조건 중 "
        f"긍정 {verdict['긍정']} · 부정 {verdict['부정']}"
        + (f" · 판단 불가 {verdict['판단불가']}" if verdict["판단불가"] else "")
        + "**"
    )
    if verdict["긍정"] + verdict["부정"]:
        st.progress(
            verdict["긍정"] / (verdict["긍정"] + verdict["부정"]),
            text=f"긍정 비율 {verdict['긍정'] / (verdict['긍정'] + verdict['부정']) * 100:.0f}%",
        )

for w in verdict["경고"]:
    st.warning(w)

with st.expander("어떤 조건이 어느 쪽에 표를 던졌는지 보기"):
    st.dataframe(
        pd.DataFrame(verdict["항목"]),
        width="stretch",
        hide_index=True,
    )

st.caption(
    "이 판독은 위 조건들을 기계적으로 집계한 값입니다. 지표는 이미 일어난 가격 움직임을 요약할 뿐 "
    "앞으로의 주가를 예측하지 않으며, 이 결과는 매수·매도 권유가 아닙니다. "
    "'긍정'은 최근 많이 올랐다는 뜻이지 더 오른다는 뜻이 아닙니다."
)
st.divider()

# ─────────────────────── 지표 해설 ───────────────────────
if show_explain:
    st.subheader("지금 지표가 말하는 것")
    cards = explain.build(df, rsi_col, vol_ma_col)
    for row_start in range(0, len(cards), 3):
        for col, card in zip(st.columns(3), cards[row_start : row_start + 3]):
            with col:
                st.markdown(f"**{card['제목']}**")
                st.markdown(card["요약"])
                for line in card["상세"]:
                    st.caption(line)
    st.caption(
        "위 내용은 지표가 지금 어디에 있는지에 대한 설명일 뿐입니다. "
        "앞으로의 주가를 예측하지 않으며, 매수·매도 판단을 담고 있지 않습니다."
    )

# ─────────────────────────── 차트 ───────────────────────────
mode = {"라이트": "light", "다크": "dark"}.get(theme_choice) or detected_mode()
found = sig_mod.detect(df, rsi_col) if show_signals else None

fig = chart.build_figure(
    df,
    palette(mode),
    ma_cols=ma_cols,
    show_bb=show_bb,
    show_volume=show_volume,
    show_rsi=show_rsi,
    show_macd=show_macd,
    rsi_col=rsi_col,
    vol_ma_col=vol_ma_col,
    extended_mask=data.extended_hours_mask(df.index) if prepost else None,
    session_hours=data.session_hours(interval, prepost),
    signals=found,
)
st.plotly_chart(
    fig,
    width="stretch",
    config={"scrollZoom": True, "displaylogo": False},
)

# ─────────────────────── 최근 신호 ───────────────────────
if show_signals and found is not None:
    st.subheader("최근 신호")
    if found.empty:
        st.info("이 구간에서는 위 조건이 한 번도 충족되지 않았습니다.")
    else:
        recent = found.tail(10).iloc[::-1].copy()
        recent["시점"] = recent["시각"].dt.strftime(
            "%Y-%m-%d %H:%M" if data.is_intraday(interval) else "%Y-%m-%d"
        )
        recent["그때 종가"] = recent["가격"].map(fmt)
        recent["뜻"] = recent["kind"].map(sig_mod.DESCRIPTION)
        st.dataframe(
            recent[["시점", "이름", "그때 종가", "뜻"]],
            width="stretch",
            hide_index=True,
        )
        st.caption(
            f"이 구간에서 조건이 총 {len(found)}번 충족됐습니다. "
            "관례적으로 쓰이는 조건일 뿐 매수·매도 권유가 아니며, 맞을 때도 틀릴 때도 있습니다. "
            "실제로 위 목록에는 신호가 하루 만에 반대로 뒤집힌 경우도 섞여 있습니다."
        )

# ─────────────────────── 지표 현황 요약 ───────────────────────
st.subheader("최근 봉 지표값")

vol_ma_label = f"거래량 MA {int(vol_ma_window)}"

rows = [
    ("종가", fmt(last["Close"]), ""),
    ("고가 / 저가", f"{fmt(last['High'])} / {fmt(last['Low'])}", ""),
    (
        "거래량",
        fmt(last["Volume"], ",.0f"),
        f"{vol_ma_label}: {fmt(last[vol_ma_col], ',.0f')}",
    ),
]
for col in ("SMA20", "SMA50", "SMA200", "EMA12", "EMA26"):
    gap = last["Close"] - last[col]
    rows.append(
        (
            chart.MA_STYLE[col][1],
            fmt(last[col]),
            "—" if pd.isna(gap) else f"종가와 차이 {gap:+,.2f} ({gap / last[col] * 100:+.2f}%)",
        )
    )
rows += [
    (rsi_label, fmt(last[rsi_col], ".1f"), ""),
    ("MACD", fmt(last["MACD"], ".3f"), f"시그널 {fmt(last['MACD_SIGNAL'], '.3f')}"),
    ("MACD 히스토그램", fmt(last["MACD_HIST"], "+.3f"), ""),
    ("볼린저 중심선", fmt(last["BB_MID"]), f"상단 {fmt(last['BB_UPPER'])} / 하단 {fmt(last['BB_LOWER'])}"),
    ("볼린저 밴드폭", fmt(last["BB_WIDTH"], ".4f"), "중심선 대비 밴드 폭 비율"),
    ("볼린저 %B", fmt(last["BB_PERCENT_B"], ".2f"), ""),
]

st.dataframe(
    pd.DataFrame(rows, columns=["지표", "값", "비고"]),
    width="stretch",
    hide_index=True,
)

# ─────────────────────────── 원본 데이터 ───────────────────────────
with st.expander("계산 결과 표 보기"):
    st.dataframe(df.iloc[::-1], width="stretch")

st.download_button(
    "CSV로 내려받기",
    df.to_csv().encode("utf-8-sig"),
    file_name=f"{ticker}_{interval}_{period}_indicators.csv",
    mime="text/csv",
)

st.caption(
    "데이터 출처: Yahoo Finance (yfinance). 지연·누락이 있을 수 있습니다. "
    "이 도구는 지표를 계산해 보여줄 뿐이며 투자 판단의 근거나 투자 자문이 아닙니다."
)
