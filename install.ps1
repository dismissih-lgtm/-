# 동영상 편집 프로그램 - 원클릭 자동 설치 스크립트
# 사용법: PowerShell에 아래 한 줄을 붙여넣고 엔터
#   irm https://raw.githubusercontent.com/dismissih-lgtm/-/claude/video-editing-program-inx23m/install.ps1 | iex

$ErrorActionPreference = "Stop"
$AppDir = Join-Path $env:USERPROFILE "video-editor"

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}

function Test-Cmd([string]$exe, [string]$arg) {
    try {
        & $exe $arg *> $null
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "   동영상 편집 프로그램 자동 설치" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# ── 1/4 프로그램 다운로드
Write-Host "[1/4] 프로그램 다운로드 중..." -ForegroundColor Yellow
$zip = Join-Path $env:TEMP "video-editor.zip"
$extract = Join-Path $env:TEMP "video-editor-extract"
Invoke-WebRequest -Uri "https://github.com/dismissih-lgtm/-/archive/refs/heads/claude/video-editing-program-inx23m.zip" -OutFile $zip
if (Test-Path $extract) { Remove-Item $extract -Recurse -Force }
Expand-Archive -Path $zip -DestinationPath $extract -Force
if (Test-Path $AppDir) { Remove-Item $AppDir -Recurse -Force }
$inner = Get-ChildItem $extract -Directory | Select-Object -First 1
Move-Item $inner.FullName $AppDir
Write-Host "      완료: $AppDir" -ForegroundColor Green

# ── 2/4 Python
Write-Host "[2/4] Python 확인 중..." -ForegroundColor Yellow
if (-not (Test-Cmd "python" "--version")) {
    Write-Host "      Python 설치 중... (몇 분 걸릴 수 있어요)"
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    Refresh-Path
}
if (-not (Test-Cmd "python" "--version")) {
    Write-Host ""
    Write-Host "Python 자동 설치에 실패했습니다." -ForegroundColor Red
    Write-Host "https://www.python.org/downloads/ 에서 설치할 때"
    Write-Host "'Add python.exe to PATH'를 체크하고, 이 명령을 다시 실행해주세요."
    return
}
Write-Host "      Python 준비 완료" -ForegroundColor Green

# ── 3/4 FFmpeg
Write-Host "[3/4] FFmpeg 확인 중..." -ForegroundColor Yellow
if (-not (Test-Cmd "ffmpeg" "-version")) {
    Write-Host "      FFmpeg 설치 중... (몇 분 걸릴 수 있어요)"
    winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
    Refresh-Path
    $env:Path += ";" + (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links")
}
Write-Host "      FFmpeg 준비 완료" -ForegroundColor Green

# ── 4/4 파이썬 패키지 설치
Write-Host "[4/4] 구성요소 설치 중... (처음 한 번만, 몇 분 소요)" -ForegroundColor Yellow
& python -m pip install --quiet --disable-pip-version-check -r (Join-Path $AppDir "requirements.txt")
Write-Host "      구성요소 설치 완료" -ForegroundColor Green

# ── 실행 파일(로컬 생성이라 차단되지 않음) + 바탕화면 바로가기
$bat = Join-Path $AppDir "run.bat"
@(
    "@echo off",
    "cd /d `"%~dp0`"",
    "python -m streamlit run app.py"
) | Out-File -FilePath $bat -Encoding ascii

$desktop = [Environment]::GetFolderPath("Desktop")
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut((Join-Path $desktop "동영상 편집기.lnk"))
$lnk.TargetPath = $bat
$lnk.WorkingDirectory = $AppDir
$lnk.Save()

Write-Host ""
Write-Host "✅ 설치 완료!" -ForegroundColor Green
Write-Host "   바탕화면에 '동영상 편집기' 바로가기가 생겼습니다." -ForegroundColor Green
Write-Host "   다음부터는 바로가기만 더블클릭하면 됩니다."
Write-Host ""
Write-Host "지금 바로 실행합니다... (잠시 후 브라우저가 열립니다)"
Set-Location $AppDir
& python -m streamlit run app.py
