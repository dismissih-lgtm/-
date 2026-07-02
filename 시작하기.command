#!/bin/bash
# macOS용 실행 파일 — 더블클릭으로 실행
cd "$(dirname "$0")"

echo "======================================"
echo "   🎬 동영상 편집 프로그램 시작"
echo "======================================"
echo

# 1. Homebrew 확인
if ! command -v brew >/dev/null 2>&1; then
    echo "⚠ Homebrew가 필요합니다. 아래 명령을 터미널에 붙여넣어 설치한 뒤 다시 실행하세요:"
    echo '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    read -p "엔터를 누르면 창이 닫힙니다..."
    exit 1
fi

# 2. Python / FFmpeg 자동 설치
command -v python3 >/dev/null 2>&1 || { echo "[1/3] Python 설치 중..."; brew install python; }
echo "[1/3] Python 확인 완료 ✓"
command -v ffmpeg >/dev/null 2>&1 || { echo "[2/3] FFmpeg 설치 중..."; brew install ffmpeg; }
echo "[2/3] FFmpeg 확인 완료 ✓"

# 3. 파이썬 패키지 설치
echo "[3/3] 필요한 프로그램 설치 중... (처음 한 번만)"
python3 -m pip install --quiet -r requirements.txt

echo
echo "✅ 준비 완료! 잠시 후 브라우저가 자동으로 열립니다."
python3 -m streamlit run app.py
