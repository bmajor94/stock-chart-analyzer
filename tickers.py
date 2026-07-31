"""우량주 목록과 종목 검색.

Yahoo 검색은 한글 질의를 못 알아듣는다 ('엔비디아' → 결과 0건). 그래서 자주 쓰는
대형주는 한글 이름을 붙인 목록으로 들고 있고, 그 밖의 종목만 Yahoo 검색에 넘긴다.
"""

from __future__ import annotations

import yfinance as yf

# (티커, 한글명, 분류)
BLUE_CHIPS: list[tuple[str, str, str]] = [
    # 메가캡 기술
    ("NVDA", "엔비디아", "반도체"),
    ("AAPL", "애플", "기술"),
    ("MSFT", "마이크로소프트", "기술"),
    ("GOOGL", "알파벳 (구글)", "기술"),
    ("AMZN", "아마존", "소비재"),
    ("META", "메타 (페이스북)", "기술"),
    ("TSLA", "테슬라", "자동차"),
    ("AVGO", "브로드컴", "반도체"),
    ("ORCL", "오라클", "기술"),
    ("NFLX", "넷플릭스", "미디어"),
    ("CRM", "세일즈포스", "기술"),
    ("ADBE", "어도비", "기술"),
    ("AMD", "AMD", "반도체"),
    ("INTC", "인텔", "반도체"),
    ("QCOM", "퀄컴", "반도체"),
    ("TXN", "텍사스인스트루먼트", "반도체"),
    ("MU", "마이크론", "반도체"),
    ("ARM", "ARM 홀딩스", "반도체"),
    ("MRVL", "마벨테크놀로지", "반도체"),
    ("PLTR", "팔란티어", "기술"),
    ("NOW", "서비스나우", "기술"),
    ("INTU", "인튜이트", "기술"),
    ("IBM", "IBM", "기술"),
    ("CSCO", "시스코", "기술"),
    ("ACN", "액센츄어", "기술"),
    ("UBER", "우버", "기술"),
    ("SHOP", "쇼피파이", "기술"),
    ("PYPL", "페이팔", "핀테크"),
    ("COIN", "코인베이스", "핀테크"),
    # 금융
    ("BRK-B", "버크셔해서웨이", "금융"),
    ("JPM", "JP모건체이스", "금융"),
    ("V", "비자", "금융"),
    ("MA", "마스터카드", "금융"),
    ("BAC", "뱅크오브아메리카", "금융"),
    ("GS", "골드만삭스", "금융"),
    ("MS", "모건스탠리", "금융"),
    ("BLK", "블랙록", "금융"),
    ("SPGI", "S&P 글로벌", "금융"),
    # 헬스케어
    ("LLY", "일라이릴리", "헬스케어"),
    ("UNH", "유나이티드헬스", "헬스케어"),
    ("JNJ", "존슨앤드존슨", "헬스케어"),
    ("ABBV", "애브비", "헬스케어"),
    ("MRK", "머크", "헬스케어"),
    ("TMO", "써모피셔", "헬스케어"),
    ("ABT", "애벗", "헬스케어"),
    ("DHR", "다나허", "헬스케어"),
    ("AMGN", "암젠", "헬스케어"),
    ("PFE", "화이자", "헬스케어"),
    # 소비재
    ("WMT", "월마트", "소비재"),
    ("COST", "코스트코", "소비재"),
    ("HD", "홈디포", "소비재"),
    ("LOW", "로우스", "소비재"),
    ("PG", "프록터앤드갬블", "소비재"),
    ("KO", "코카콜라", "소비재"),
    ("PEP", "펩시코", "소비재"),
    ("MCD", "맥도날드", "소비재"),
    ("SBUX", "스타벅스", "소비재"),
    ("NKE", "나이키", "소비재"),
    ("PM", "필립모리스", "소비재"),
    ("DIS", "디즈니", "미디어"),
    ("BKNG", "부킹홀딩스", "소비재"),
    # 산업·에너지·통신
    ("XOM", "엑슨모빌", "에너지"),
    ("CVX", "셰브론", "에너지"),
    ("GE", "GE 에어로스페이스", "산업재"),
    ("CAT", "캐터필러", "산업재"),
    ("RTX", "RTX (레이시온)", "산업재"),
    ("HON", "허니웰", "산업재"),
    ("UNP", "유니온퍼시픽", "산업재"),
    ("BA", "보잉", "산업재"),
    ("LIN", "린데", "소재"),
    ("T", "AT&T", "통신"),
    ("VZ", "버라이즌", "통신"),
    ("F", "포드", "자동차"),
    ("GM", "제너럴모터스", "자동차"),
    # ETF
    ("SPY", "S&P 500 ETF", "ETF"),
    ("QQQ", "나스닥 100 ETF", "ETF"),
    ("VOO", "뱅가드 S&P 500 ETF", "ETF"),
    ("DIA", "다우존스 ETF", "ETF"),
    ("IWM", "러셀 2000 ETF", "ETF"),
    ("SCHD", "슈왑 배당주 ETF", "ETF"),
]

# 한글명만으로는 안 걸리는 별칭. 한글명에 이미 들어 있는 말은 여기 넣지 않는다
# (넣으면 '알파벳 (구글) (구글)' 처럼 라벨에 두 번 찍힌다).
ALIASES: dict[str, str] = {
    "GE": "제너럴일렉트릭",
    "SPY": "스파이",
    "QQQ": "큐큐큐",
}

TICKERS = [t for t, _, _ in BLUE_CHIPS]
_BY_TICKER = {t: (kr, cat) for t, kr, cat in BLUE_CHIPS}


def label(ticker: str) -> str:
    """셀렉트박스에 보일 문자열. 여기 담긴 글자가 곧 검색 대상이 된다."""
    kr, cat = _BY_TICKER.get(ticker, ("", ""))
    if not kr:
        return ticker
    alias = ALIASES.get(ticker)
    tail = f" · {cat}" if cat else ""
    return f"{ticker} · {kr}{f' ({alias})' if alias else ''}{tail}"


def korean_name(ticker: str) -> str:
    return _BY_TICKER.get(ticker, ("", ""))[0]


def search(query: str, limit: int = 8) -> list[dict]:
    """Yahoo 종목 검색. 한글 질의는 지원되지 않으므로 영문명이나 티커를 넣어야 한다."""
    query = query.strip()
    if not query:
        return []
    from data import _bounded  # 같은 타임아웃 정책을 쓴다

    quotes = _bounded(
        lambda: yf.Search(query, max_results=limit).quotes or [], seconds=8, default=None
    )
    if not quotes:
        return []

    out = []
    for q in quotes:
        symbol = q.get("symbol")
        if not symbol:
            continue
        out.append(
            {
                "티커": symbol,
                "이름": q.get("shortname") or q.get("longname") or "",
                "종류": q.get("quoteType") or "",
                "거래소": q.get("exchange") or "",
            }
        )
    return out
