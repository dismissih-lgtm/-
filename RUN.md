# 🎬 동영상 편집 프로그램 실행 방법

## ⭐ 가장 쉬운 방법 — 붙여넣기 한 번 (Windows)

> 인터넷에서 받은 실행 파일은 Windows 스마트 앱 컨트롤이 차단할 수 있어서,
> 차단당하지 않는 방식으로 설치합니다.

1. **키보드에서 `윈도우 키`를 누르고 `powershell` 입력 → 엔터** (파란 창이 열립니다)

2. **아래 한 줄을 복사해서 붙여넣고 엔터:**

   ```powershell
   irm https://raw.githubusercontent.com/dismissih-lgtm/-/claude/video-editing-program-inx23m/install.ps1 | iex
   ```

3. 끝! 자동으로 진행됩니다:
   - 프로그램 다운로드 → Python·FFmpeg 자동 설치 → 브라우저에서 앱 실행
   - **바탕화면에 "동영상 편집기" 바로가기 생성** → 다음부터는 더블클릭만 하면 됩니다

(처음 한 번은 설치 때문에 몇 분 걸립니다)

### macOS

폴더 안의 `시작하기.command` 를 더블클릭하세요.
(차단되면: 오른쪽 클릭 → 열기 → 열기)

---

## 방법 1 — 직접 명령어로 실행 (개발자용)

### 1) 코드 받기

```bash
git clone https://github.com/dismissih-lgtm/-.git video-editor
cd video-editor
git checkout claude/video-editing-program-inx23m
```

(이미 받아둔 경우: `git pull` 만 하면 됩니다)

### 2) FFmpeg 설치 (필수, 한 번만)

- **Windows**: https://www.gyan.dev/ffmpeg/builds/ 에서 "release full" 다운로드
  → 압축 풀고 `bin` 폴더를 PATH에 추가
  → 또는 간단하게: `winget install ffmpeg`
- **macOS**: `brew install ffmpeg`
- **Ubuntu/Debian**: `sudo apt install ffmpeg fonts-nanum`

설치 확인: 터미널에서 `ffmpeg -version` 이 출력되면 OK

### 3) 파이썬 패키지 설치 (한 번만)

```bash
pip install -r requirements.txt
```

### 4) 실행

```bash
streamlit run app.py
```

브라우저가 자동으로 열립니다 (`http://localhost:8501`).

---

## 방법 2 — Streamlit Community Cloud 무료 배포 (설치 없이 웹에서 사용)

내 컴퓨터에 아무것도 설치하지 않고 웹 주소로 사용하는 방법입니다.

1. https://share.streamlit.io 접속 → GitHub 계정으로 로그인
2. **New app** 클릭
3. 저장소: `dismissih-lgtm/-`, 브랜치: `claude/video-editing-program-inx23m`, 파일: `app.py` 선택
4. **Deploy** 클릭 → 몇 분 뒤 나만의 웹 주소가 생깁니다

> `packages.txt` 에 ffmpeg와 한글 폰트가 등록되어 있어 배포 시 자동 설치됩니다.
> 무료 플랜은 업로드 용량 제한(약 200MB)이 있으니 큰 영상은 방법 1을 사용하세요.

---

## 사용 순서

1. **동영상 업로드** — MP4/AVI/MOV/MKV
2. **자막 제거 시작** 버튼 클릭
3. **대본 입력** — 한 줄이 자막 하나가 됩니다
4. 자동 분배된 **타이밍 표를 필요하면 수정**
5. 편집 방식 선택 후 **편집 시작**
   - ✂️ 컷 편집 + 새 자막 입히기 (추천)
   - ✂️ 컷 편집만
   - 💬 자막만 입히기
6. 완성된 **동영상 / SRT 자막 다운로드**

---

## 문제 해결

| 증상 | 해결 |
|------|------|
| `ffmpeg not found` | FFmpeg 설치 후 터미널(명령 프롬프트)을 새로 열기 |
| 한글 자막이 □□□ 로 나옴 | (리눅스) `sudo apt install fonts-nanum` / Windows·Mac은 기본 폰트로 자동 대체됨 |
| 업로드가 200MB에서 막힘 | `streamlit run app.py --server.maxUploadSize 2000` 으로 실행 |
| 편집이 오래 걸림 | 정상입니다 — 영상 길이·해상도에 비례합니다 |
