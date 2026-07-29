#!/bin/bash
# 더블클릭으로 차트 지표 분석 대시보드를 켠다.
# 터미널 창이 하나 열리고, 그 창을 닫으면 앱도 함께 꺼진다.

cd "$(dirname "$0")" || exit 1
PORT=8501
URL="http://localhost:$PORT"

# 처음 실행이거나 환경이 지워졌으면 새로 만든다
if [ ! -x .venv/bin/streamlit ]; then
  echo "처음 실행이라 필요한 것들을 설치합니다. 몇 분 걸립니다…"
  echo
  python3 -m venv .venv || {
    echo
    echo "❌ 파이썬 환경을 만들지 못했습니다. python3 가 설치돼 있는지 확인하세요."
    read -r -p "엔터를 누르면 창이 닫힙니다."
    exit 1
  }
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -r requirements.txt || {
    echo
    echo "❌ 패키지 설치에 실패했습니다. 인터넷 연결을 확인하세요."
    read -r -p "엔터를 누르면 창이 닫힙니다."
    exit 1
  }
  echo "설치 완료."
  echo
fi

# 이미 켜져 있으면 새로 띄우지 않고 브라우저만 연다 (두 번 눌러도 안전)
if curl -s -o /dev/null --max-time 2 "$URL"; then
  echo "이미 실행 중입니다. 브라우저만 엽니다."
  open "$URL"
  sleep 1
  exit 0
fi

echo "──────────────────────────────────────────"
echo "  차트 지표 분석"
echo
echo "  잠시 후 브라우저가 자동으로 열립니다."
echo "  끄려면 이 창을 닫거나 Control-C 를 누르세요."
echo "──────────────────────────────────────────"
echo

# 서버가 뜨는 것을 기다렸다가 브라우저를 연다.
# (headless 로 띄우는 이유: 아니면 Streamlit 이 첫 실행 때 이메일을 물어보며 멈춘다)
(
  for _ in $(seq 1 40); do
    sleep 0.5
    curl -s -o /dev/null --max-time 1 "$URL" && break
  done
  open "$URL"
) &

exec .venv/bin/streamlit run app.py --server.port "$PORT" --server.headless true
