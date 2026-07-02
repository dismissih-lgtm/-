@echo off
chcp 65001 >nul
title 동영상 편집 프로그램
cd /d "%~dp0"
set "PATH=%PATH%;%LOCALAPPDATA%\Microsoft\WinGet\Links"

echo ======================================
echo    🎬 동영상 편집 프로그램 시작
echo ======================================
echo.

REM ── 1. Python 확인 (없으면 자동 설치)
python --version >nul 2>nul
if errorlevel 1 (
    echo [1/3] Python 설치 중... 몇 분 걸릴 수 있어요.
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts"
) else (
    echo [1/3] Python 확인 완료 ✓
)

python --version >nul 2>nul
if errorlevel 1 (
    echo.
    echo ⚠ Python 자동 설치에 실패했습니다.
    echo   1. https://www.python.org/downloads/ 에서 Python을 설치하세요.
    echo      ^(설치 첫 화면에서 "Add python.exe to PATH" 반드시 체크!^)
    echo   2. 설치 후 이 파일을 다시 더블클릭하세요.
    echo.
    pause
    exit /b
)

REM ── 2. FFmpeg 확인 (없으면 자동 설치)
ffmpeg -version >nul 2>nul
if errorlevel 1 (
    echo [2/3] FFmpeg 설치 중... 몇 분 걸릴 수 있어요.
    winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
    set "PATH=%PATH%;%LOCALAPPDATA%\Microsoft\WinGet\Links"
) else (
    echo [2/3] FFmpeg 확인 완료 ✓
)

ffmpeg -version >nul 2>nul
if errorlevel 1 (
    echo.
    echo ⚠ FFmpeg 설치 직후에는 다시 시작해야 인식됩니다.
    echo   이 창을 닫고 "시작하기.bat" 를 한 번 더 더블클릭하세요.
    echo.
    pause
    exit /b
)

REM ── 3. 필요한 파이썬 패키지 설치
echo [3/3] 필요한 프로그램 설치 중... ^(처음 한 번만, 몇 분 소요^)
python -m pip install --quiet --disable-pip-version-check -r requirements.txt

echo.
echo ✅ 준비 완료! 잠시 후 브라우저가 자동으로 열립니다.
echo    ^(끝내려면 이 창을 닫으세요^)
echo.
python -m streamlit run app.py

pause
