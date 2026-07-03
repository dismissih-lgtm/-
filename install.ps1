# 동영상 편집 프로그램 - 원클릭 자동 설치 스크립트
# 사용법: PowerShell에 아래 한 줄을 붙여넣고 엔터
#   irm https://raw.githubusercontent.com/dismissih-lgtm/-/claude/video-editing-program-inx23m/install.ps1 | iex

$ErrorActionPreference = "Stop"
$AppDir = Join-Path $env:USERPROFILE "video-editor"

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}

# Microsoft Store 유도용 가짜 python(WindowsApps 스텁)을 걸러내고 진짜 Python을 찾는다
function Get-RealPython {
    # 1) py 런처 (python.org 설치 시 함께 설치됨, 가장 안정적)
    if (Get-Command py.exe -ErrorAction SilentlyContinue) {
        $v = cmd /c "py -3 --version" 2>&1
        if ("$v" -match 'Python 3\.') { return @{ exe = "py.exe"; pre = @("-3") } }
    }
    # 2) PATH의 python 중 스토어 스텁 제외
    foreach ($c in @(Get-Command python.exe -All -ErrorAction SilentlyContinue)) {
        if ($c.Source -match 'WindowsApps') { continue }
        $v = & $c.Source --version 2>&1
        if ("$v" -match 'Python 3\.') { return @{ exe = $c.Source; pre = @() } }
    }
    # 3) 흔한 설치 경로 직접 검색
    $globs = @(
        "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
        "$env:ProgramFiles\Python3*\python.exe"
    )
    foreach ($g in $globs) {
        $hit = Get-ChildItem $g -ErrorAction SilentlyContinue |
               Sort-Object FullName -Descending | Select-Object -First 1
        if ($hit) { return @{ exe = $hit.FullName; pre = @() } }
    }
    return $null
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

# 실행 중인 편집기 앱이 있으면 자동 종료 (업데이트를 위해)
try {
    Get-CimInstance Win32_Process -Filter "Name like 'python%'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'streamlit' } |
        ForEach-Object {
            Write-Host "      실행 중인 편집기를 잠시 종료합니다..."
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
    Start-Sleep -Seconds 1
} catch {}

if (Test-Path $AppDir) {
    try {
        Remove-Item $AppDir -Recurse -Force
    } catch {
        Start-Sleep -Seconds 2
        try {
            Remove-Item $AppDir -Recurse -Force
        } catch {
            Write-Host ""
            Write-Host "기존 프로그램 폴더를 정리할 수 없습니다." -ForegroundColor Red
            Write-Host "편집기 창(검은 창)과 브라우저 탭을 모두 닫은 뒤 이 명령을 다시 실행해주세요."
            return
        }
    }
}
$inner = Get-ChildItem $extract -Directory | Select-Object -First 1
Move-Item $inner.FullName $AppDir
Write-Host "      완료: $AppDir" -ForegroundColor Green

# ── 2/4 Python (가짜 스토어 python은 무시하고 진짜만 인정)
Write-Host "[2/4] Python 확인 중..." -ForegroundColor Yellow
$py = Get-RealPython
if (-not $py) {
    Write-Host "      Python 설치 중... (몇 분 걸릴 수 있어요)"
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements `
        --override "/quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 InstallLauncherAllUsers=0"
    Refresh-Path
    $py = Get-RealPython
}
if (-not $py) {
    Write-Host ""
    Write-Host "Python 자동 설치에 실패했습니다." -ForegroundColor Red
    Write-Host "1) https://www.python.org/downloads/ 에서 Python을 설치하세요."
    Write-Host "   (설치 첫 화면에서 'Add python.exe to PATH' 반드시 체크!)"
    Write-Host "2) 설치가 끝나면 이 명령을 다시 실행하세요."
    return
}
$pyDesc = "$($py.exe) $($py.pre -join ' ')".Trim()
Write-Host "      Python 준비 완료 ($pyDesc)" -ForegroundColor Green

# ── 3/4 FFmpeg
Write-Host "[3/4] FFmpeg 확인 중..." -ForegroundColor Yellow
$ffmpegOk = $false
try { ffmpeg -version *> $null; $ffmpegOk = ($LASTEXITCODE -eq 0) } catch {}
if (-not $ffmpegOk) {
    Write-Host "      FFmpeg 설치 중... (몇 분 걸릴 수 있어요)"
    winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
    Refresh-Path
    $env:Path += ";" + (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links")
}
Write-Host "      FFmpeg 준비 완료" -ForegroundColor Green

# ── 4/4 파이썬 패키지 설치
Write-Host "[4/4] 구성요소 설치 중... (처음 한 번만, 몇 분 소요)" -ForegroundColor Yellow
& $py.exe @($py.pre) -m pip install --quiet --disable-pip-version-check -r (Join-Path $AppDir "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Host "구성요소 설치에 실패했습니다. 인터넷 연결을 확인하고 다시 실행해주세요." -ForegroundColor Red
    return
}
Write-Host "      구성요소 설치 완료" -ForegroundColor Green

# ── 실행 파일(컴퓨터 안에서 생성되므로 차단되지 않음) + 바탕화면 바로가기
$bat = Join-Path $AppDir "run.bat"
if ($py.exe -eq "py.exe") {
    $runCmd = "py -3 -m streamlit run app.py"
} else {
    $runCmd = "`"$($py.exe)`" -m streamlit run app.py"
}
$batLines = @(
    "@echo off",
    "cd /d `"%~dp0`"",
    $runCmd,
    "pause"
)
[System.IO.File]::WriteAllLines($bat, $batLines)

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
& $py.exe @($py.pre) -m streamlit run app.py
