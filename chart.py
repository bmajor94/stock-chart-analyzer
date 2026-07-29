"""Plotly 차트 조립.

가격 / 거래량 / RSI / MACD 를 x축을 공유하는 별도 행으로 쌓는다.
(하나의 축에 스케일이 다른 두 지표를 겹치지 않는다.)
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

LINE_W = 2

MA_STYLE = {
    "SMA20": ("sma20", "SMA 20"),
    "SMA50": ("sma50", "SMA 50"),
    "SMA200": ("sma200", "SMA 200"),
    "EMA12": ("ema_fast", "EMA 12"),
    "EMA26": ("ema_slow", "EMA 26"),
}


def _extended_spans(mask: pd.Series) -> list[tuple]:
    """True 구간이 이어지는 덩어리를 (시작, 끝) 목록으로 묶는다."""
    spans: list[tuple] = []
    start = None
    prev = None
    for ts, flag in mask.items():
        if flag and start is None:
            start = ts
        elif not flag and start is not None:
            spans.append((start, ts))
            start = None
        prev = ts
    if start is not None and prev is not None:
        spans.append((start, prev))
    return spans


def build_figure(
    df: pd.DataFrame,
    pal: dict[str, str],
    *,
    ma_cols: list[str],
    show_bb: bool,
    show_volume: bool,
    show_rsi: bool,
    show_macd: bool,
    rsi_col: str,
    vol_ma_col: str,
    price_fmt: str = ".2f",
    extended_mask: pd.Series | None = None,
    session_hours: tuple[float, float] | None = None,
    signals: pd.DataFrame | None = None,
) -> go.Figure:
    rows = [("price", 0.52)]
    if show_volume:
        rows.append(("volume", 0.14))
    if show_rsi:
        rows.append(("rsi", 0.17))
    if show_macd:
        rows.append(("macd", 0.17))

    total = sum(h for _, h in rows)
    heights = [h / total for _, h in rows]
    index_of = {name: i + 1 for i, (name, _) in enumerate(rows)}

    rsi_label = f"RSI {rsi_col.removeprefix('RSI')}"
    vol_ma_label = f"거래량 MA {vol_ma_col.removeprefix('VOL_MA')}"

    # 패널 이름은 y축 제목이 담당한다 (서브플롯 제목은 범례와 겹친다)
    axis_titles = {
        "price": "가격",
        "volume": "거래량",
        "rsi": rsi_label,
        "macd": "MACD",
    }

    fig = make_subplots(
        rows=len(rows),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.035,
        row_heights=heights,
    )

    # ── 가격: 볼린저 밴드(뒤) → 캔들 → 이동평균(앞) 순서로 겹친다
    r = index_of["price"]

    if show_bb and "BB_UPPER" in df:
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["BB_UPPER"],
                name="볼린저 상단",
                line=dict(color=pal["band"], width=1, dash="dot"),
                hovertemplate="상단 %{y:" + price_fmt + "}<extra></extra>",
                legendgroup="bb",
            ),
            row=r,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["BB_LOWER"],
                name="볼린저 하단",
                line=dict(color=pal["band"], width=1, dash="dot"),
                fill="tonexty",
                fillcolor=pal["band_fill"],
                hovertemplate="하단 %{y:" + price_fmt + "}<extra></extra>",
                legendgroup="bb",
            ),
            row=r,
            col=1,
        )

    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="주가",
            increasing=dict(
                line=dict(color=pal["up"], width=1), fillcolor=pal["up"]
            ),
            decreasing=dict(
                line=dict(color=pal["down"], width=1), fillcolor=pal["down"]
            ),
            showlegend=False,
        ),
        row=r,
        col=1,
    )

    for col in ma_cols:
        # 조회 기간이 지표 기간보다 짧으면 전부 NaN — 빈 범례만 남으므로 건너뛴다
        if col not in df or df[col].isna().all():
            continue
        role, label = MA_STYLE[col]
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df[col],
                name=label,
                line=dict(color=pal[role], width=LINE_W),
                hovertemplate=label + " %{y:" + price_fmt + "}<extra></extra>",
            ),
            row=r,
            col=1,
        )

    # ── 거래량: 종가 방향에 따라 색을 나눈다
    if show_volume:
        r = index_of["volume"]
        direction = df["Close"] >= df["Open"]
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df["Volume"],
                name="거래량",
                marker=dict(
                    color=[pal["up"] if up else pal["down"] for up in direction],
                    line=dict(width=0),
                ),
                opacity=0.55,
                showlegend=False,
                hovertemplate="거래량 %{y:,.0f}<extra></extra>",
            ),
            row=r,
            col=1,
        )
        if vol_ma_col in df:
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df[vol_ma_col],
                    name=vol_ma_label,
                    line=dict(color=pal["sma20"], width=LINE_W),
                    hovertemplate=vol_ma_label + " %{y:,.0f}<extra></extra>",
                ),
                row=r,
                col=1,
            )

    # ── RSI: 30~70 밴드를 배경으로 깔고 선을 얹는다
    if show_rsi:
        r = index_of["rsi"]
        fig.add_hrect(
            y0=30,
            y1=70,
            fillcolor=pal["zone_fill"],
            line_width=0,
            row=r,
            col=1,
        )
        for level in (30, 70):
            fig.add_hline(
                y=level,
                line=dict(color=pal["muted"], width=1, dash="dot"),
                row=r,
                col=1,
            )
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df[rsi_col],
                name=rsi_label,
                line=dict(color=pal["sma20"], width=LINE_W),
                hovertemplate=rsi_label + " %{y:.1f}<extra></extra>",
                showlegend=False,  # y축 제목이 이미 이름을 달고 있는 단일 계열
            ),
            row=r,
            col=1,
        )
        # 기준선 값을 축 눈금으로 직접 달아준다
        fig.update_yaxes(
            range=[0, 100],
            tickmode="array",
            tickvals=[0, 30, 50, 70, 100],
            row=r,
            col=1,
        )

    # ── MACD: 히스토그램 + 선 2개
    if show_macd:
        r = index_of["macd"]
        hist = df["MACD_HIST"]
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=hist,
                name="히스토그램",
                marker=dict(
                    color=[
                        pal["up"] if (pd.notna(v) and v >= 0) else pal["down"]
                        for v in hist
                    ],
                    line=dict(width=0),
                ),
                opacity=0.5,
                hovertemplate="히스토그램 %{y:.3f}<extra></extra>",
            ),
            row=r,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["MACD"],
                name="MACD",
                line=dict(color=pal["sma20"], width=LINE_W),
                hovertemplate="MACD %{y:.3f}<extra></extra>",
            ),
            row=r,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["MACD_SIGNAL"],
                name="시그널",
                line=dict(color=pal["sma50"], width=LINE_W),
                hovertemplate="시그널 %{y:.3f}<extra></extra>",
            ),
            row=r,
            col=1,
        )
        fig.add_hline(
            y=0, line=dict(color=pal["muted"], width=1), row=r, col=1
        )

    # ── 신호 마커: 조건이 충족된 봉에, 그 조건이 속한 패널에 찍는다.
    # 색만으로 구분하지 않도록 방향별로 삼각형 모양을 다르게 주고 이름은 호버에 담는다.
    if signals is not None and not signals.empty:
        y_source = {
            "price": ("Low", "High", df["High"].sub(df["Low"]).median() or 1.0),
            "rsi": (rsi_col, rsi_col, 8.0),
            "macd": ("MACD", "MACD", (df["MACD"].abs().median() or 1.0) * 0.8),
        }
        for panel in ("price", "rsi", "macd"):
            if panel not in index_of:
                continue
            part = signals[signals["panel"] == panel]
            if part.empty:
                continue
            low_col, high_col, pad = y_source[panel]
            for direction, symbol, role in (
                ("up", "triangle-up", "up"),
                ("down", "triangle-down", "down"),
            ):
                sub = part[part["direction"] == direction]
                if sub.empty:
                    continue
                ts = pd.DatetimeIndex(sub["시각"])
                base = df.loc[ts, low_col if direction == "up" else high_col]
                y = base - pad if direction == "up" else base + pad
                fig.add_trace(
                    go.Scatter(
                        x=ts,
                        y=y,
                        mode="markers",
                        name=f"신호 ({'상향' if direction == 'up' else '하향'})",
                        marker=dict(
                            symbol=symbol,
                            size=11,
                            color=pal[role],
                            line=dict(width=1, color=pal["surface"]),
                        ),
                        customdata=sub["이름"].to_numpy(),
                        hovertemplate="%{customdata}<extra></extra>",
                        showlegend=panel == "price",
                        legendgroup=f"signal-{direction}",
                    ),
                    row=index_of[panel],
                    col=1,
                )

    # ── 시간외 거래 구간을 모든 패널에 옅은 배경으로 깔아 정규장과 구분한다.
    # add_vrect 는 트레이스가 없는 서브플롯을 건너뛰므로 반드시 트레이스를 다 얹은 뒤 호출한다.
    if extended_mask is not None and extended_mask.any():
        for start, end in _extended_spans(extended_mask):
            fig.add_vrect(
                x0=start,
                x1=end,
                fillcolor=pal["extended_fill"],
                line_width=0,
                layer="below",
                row="all",
                col=1,
            )

    # ── 공통 크롬: 그리드/축은 뒤로 물리고, 호버는 x축 통합 크로스헤어
    fig.update_layout(
        height=260 + 620 * total,
        margin=dict(l=8, r=8, t=64, b=8),
        paper_bgcolor=pal["surface"],
        plot_bgcolor=pal["surface"],
        font=dict(
            color=pal["text"],
            family='system-ui, -apple-system, "Segoe UI", sans-serif',
            size=12,
        ),
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor=pal["surface"],
            bordercolor=pal["axis"],
            font_color=pal["text"],
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.008,
            xanchor="left",
            x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=pal["text"], size=11),
            itemsizing="constant",
        ),
        barmode="overlay",
        dragmode="pan",
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor=pal["grid"],
        gridwidth=1,
        linecolor=pal["axis"],
        tickcolor=pal["axis"],
        tickfont=dict(color=pal["muted"]),
        rangeslider_visible=False,
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikecolor=pal["axis"],
        spikethickness=1,
        spikedash="dot",
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=pal["grid"],
        gridwidth=1,
        zeroline=False,
        linecolor=pal["axis"],
        tickcolor=pal["axis"],
        tickfont=dict(color=pal["muted"]),
    )
    for name, _ in rows:
        fig.update_yaxes(
            title_text=axis_titles[name],
            title_font=dict(color=pal["muted"], size=11),
            row=index_of[name],
            col=1,
        )

    # 거래가 없는 시간대를 x축에서 접는다. 접지 않으면 밤·주말 공백 때문에
    # 캔들이 뭉치고 이동평균이 계단처럼 꺾여 보인다.
    breaks: list[dict] = []
    if session_hours is not None:
        # 인트라데이: 주말 + 장 마감~다음 장 시작
        open_h, close_h = session_hours
        breaks.append(dict(bounds=["sat", "mon"]))
        breaks.append(dict(bounds=[close_h, open_h], pattern="hour"))
    elif len(df) > 2:
        # 일봉일 때만 주말을 접는다.
        # (주봉·월봉에 적용하면 토·일에 걸린 봉이 통째로 사라진다)
        step = pd.Series(df.index).diff().median().total_seconds()
        if 86400 <= step < 5 * 86400:
            breaks.append(dict(bounds=["sat", "mon"]))
    if breaks:
        fig.update_xaxes(rangebreaks=breaks)
        # rangebreaks 가 걸리면 plotly 의 자동 범위 계산이 뒤쪽 구간을 잘라먹는다.
        # 데이터 전체 구간을 명시해 마지막 봉까지 항상 보이게 한다.
        fig.update_xaxes(range=[df.index[0], df.index[-1]], autorange=False)

    return fig
