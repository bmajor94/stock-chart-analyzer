"""차트 색상 팔레트 — 라이트/다크 두 모드를 각각 선택해서 정의한다.

색은 '역할'로만 참조한다. 모드 전환 시 이 파일 하나만 바뀐다.
"""

from __future__ import annotations

LIGHT = {
    "surface": "#fcfcfb",
    "text": "#0b0b0b",
    "muted": "#898781",
    "grid": "#e1e0d9",
    "axis": "#c3c2b7",
    "up": "#1baf7a",
    "down": "#e34948",
    "sma20": "#2a78d6",
    "sma50": "#eb6834",
    "sma200": "#4a3aa7",
    "ema_fast": "#eda100",
    "ema_slow": "#e87ba4",
    "band": "#898781",
    "band_fill": "rgba(137,135,129,0.10)",
    "zone_fill": "rgba(137,135,129,0.12)",
    "extended_fill": "rgba(137,135,129,0.13)",
}

DARK = {
    "surface": "#1a1a19",
    "text": "#ffffff",
    "muted": "#898781",
    "grid": "#2c2c2a",
    "axis": "#383835",
    "up": "#199e70",
    "down": "#e66767",
    "sma20": "#3987e5",
    "sma50": "#d95926",
    "sma200": "#9085e9",
    "ema_fast": "#c98500",
    "ema_slow": "#d55181",
    "band": "#898781",
    "band_fill": "rgba(137,135,129,0.12)",
    "zone_fill": "rgba(137,135,129,0.14)",
    "extended_fill": "rgba(137,135,129,0.15)",
}


def palette(mode: str) -> dict[str, str]:
    return DARK if mode == "dark" else LIGHT
