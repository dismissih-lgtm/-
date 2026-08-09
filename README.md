# 뉴스 인스타 게시물 자동 생성 봇

매일 정해진 시간에 **뉴스를 검색**해 AI가 **이미지 + 캡션·해시태그를 자동 생성**하고,
**카카오톡으로 받거나** **인스타그램에 바로 업로드**합니다.

- 🎨 이미지: OpenAI **DALL·E 3**
- ✍️ 캡션·해시태그: **Claude** (`claude-opus-4-8`)
- 📰 뉴스 검색: **Claude 내장 web_search** (추가 API 키 불필요)
- 🛒 **쿠팡 파트너스 카드뉴스**: 파트너스 URL → 인스타 규격 카드뉴스 3~4장 자동 생성
- ⏰ 자동 실행: 매일 **한국 시간 오전 6시** (시간 변경 가능)
- 📬 전송 방법 (둘 중 선택):
  - 💬 **카카오톡으로 받기** — 페이스북/인스타 없이 바로 사용, 받아서 직접 게시 → [SETUP_KAKAO.md](SETUP_KAKAO.md)
  - 📤 **인스타그램 자동 업로드** — 공식 Graph API → [SETUP_INSTAGRAM.md](SETUP_INSTAGRAM.md)

> 💡 페이스북/인스타 설정이 번거롭다면 **카카오톡으로 받기**가 가장 간단합니다.
> 뉴스 게시물이 매일 카톡으로 오면, 마음에 드는 것을 골라 직접 올리면 돼요.

---

## 1. 사전 준비

### (A) 인스타그램 계정 설정 — 가장 중요

공식 Graph API는 **개인 계정으로는 자동 업로드가 불가능**합니다. 아래가 필요합니다.

1. 인스타그램 계정을 **비즈니스** 또는 **크리에이터** 계정으로 전환
2. 해당 계정을 **Facebook 페이지**에 연결
3. [Meta for Developers](https://developers.facebook.com/) 에서 앱 생성
4. 앱에 **Instagram Graph API** 제품 추가
5. 다음 권한을 가진 **장기(long-lived) 액세스 토큰** 발급
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_read_engagement`
6. **IG_USER_ID**(페이지에 연결된 인스타그램 비즈니스 계정 ID) 확인

> 📖 **토큰 발급과 IG_USER_ID 확인은 [SETUP_INSTAGRAM.md](SETUP_INSTAGRAM.md) 에
> 단계별로 정리해 두었습니다.** 헷갈리는 마지막 단계(장기 토큰 변환 + IG_USER_ID 조회)는
> 도우미 스크립트가 자동으로 해줍니다:
>
> ```bash
> python get_credentials.py --app-id <앱ID> --app-secret <앱시크릿> --token <짧은수명토큰>
> ```

### (B) API 키

- **Anthropic API 키** — https://console.anthropic.com/
- **OpenAI API 키** — https://platform.openai.com/

---

## 2. 설치

```bash
pip install -r requirements.txt
```

## 3. 환경 변수 설정

```bash
cp .env.example .env
# .env 파일을 열어 키와 토큰을 채워넣으세요.
```

## 4. 실행 — 화면 보면서 하기 (웹 UI) ⭐

브라우저에서 **미리보기 → 캡션 수정 → 업로드**까지 클릭으로 진행할 수 있습니다.

```bash
streamlit run app.py
```

실행하면 브라우저가 자동으로 열리고, 탭 2개로 나뉩니다.

**✍️ 직접 만들기 (수동)**
- "주제 직접 입력" 또는 "오늘의 뉴스 검색" 선택
- **생성하기** → 이미지와 캡션 미리보기
- 캡션을 직접 다듬은 뒤 **인스타그램에 업로드**

**⏰ 자동 게시 설정**
- 매일 자동 게시 **켜기/끄기**, **실행 시각**(한국 시간), **뉴스 검색어** 설정 후 저장
- **지금 한 번 실행**으로 자동 게시를 즉시 테스트
- 저장한 시각은 `settings.json` 에 기록되며 스케줄러(`python -m src.scheduler`)가 읽어서 실행합니다

## 4-2. 실행 — 명령줄(터미널)에서 하기

먼저 **업로드 없이** 이미지·캡션만 만들어 확인:

```bash
python -m src.main "가을 감성 카페 신메뉴 홍보" --dry-run
```

문제없으면 실제 업로드:

```bash
python -m src.main "가을 감성 카페 신메뉴 홍보"
```

---

## 4-3. 쿠팡 파트너스 카드뉴스 만들기 🛒📱

**휴대폰에서 쿠팡 상품 화면을 캡처해 올리면**, AI가 캡처에서 상품명·가격·특징을
읽고 **상품 사진을 잘라내** 인스타그램 규격(1:1 또는 4:5)의 **카드뉴스 이미지
3~4장 + 캡션(해시태그·파트너스 고지 포함)** 을 만들어줍니다.
상품 사진은 표지와 마지막 카드에 자동으로 들어갑니다.

**사용 순서 (휴대폰):**

1. 쿠팡 앱에서 상품 화면(사진·상품명·가격이 보이게)을 **캡처**
2. 휴대폰 브라우저로 웹 UI 접속 → **🛒 쿠팡 카드뉴스** 탭 → 캡처 업로드
3. 카드 장수(3/4)·테마·비율 선택 → **생성**
4. 미리보기 확인 → **zip 다운로드** → 인스타그램에 여러 장 게시물(캐러셀)로 업로드

파트너스 URL은 선택 입력입니다(캡션에 링크를 넣고 싶을 때). URL만으로 만들던
기존 방식도 그대로 지원합니다.

**휴대폰에서 접속하는 방법:**

- 같은 와이파이의 PC에서 실행: `streamlit run app.py --server.address 0.0.0.0`
  → 휴대폰 브라우저에서 `http://<PC의 IP>:8501` 접속
- 또는 [Streamlit Community Cloud](https://streamlit.io/cloud) 에 무료 배포하면
  어디서든 접속 가능 (Secrets 에 `ANTHROPIC_API_KEY` 등록)

**명령줄에서:**

```bash
python -m src.coupang --image capture.png                 # 화면 캡처로 생성 (추천)
python -m src.coupang --image capture.png --url "https://link.coupang.com/a/xxxxx"
python -m src.coupang --url "https://link.coupang.com/a/xxxxx" --cards 3 --theme "웜 크림"
```

결과물은 `output/coupang_날짜시간/` 폴더에 `card_N.png` 와 `caption.txt` 로 저장됩니다.

> ⚠️ **알아두세요**
> - 캡처에서 상품 사진 추출이 어색하면 "상품 정보/사진 직접 입력"에서 사진을
>   직접 올릴 수 있습니다 (CLI는 `--photo`). 정보 인식이 이상하면 `--name`,
>   `--price`, `--features` 로 덮어쓸 수 있어요.
> - 캡션에 포함되는 **쿠팡 파트너스 고지 문구**("이 포스팅은 쿠팡 파트너스 활동의
>   일환으로...")는 파트너스 약관상 **필수**이니 지우지 마세요. 마지막 카드에도
>   자동으로 들어갑니다.
> - 한글 폰트(Noto Sans KR)는 최초 실행 시 `assets/fonts/` 에 자동 다운로드됩니다.
> - 인스타그램 자동 업로드(캐러셀)는 공개 이미지 URL이 필요해 지원하지 않습니다.
>   다운로드한 이미지를 직접 올려주세요.

---

## 5. 오늘의 뉴스로 자동 게시

주제를 직접 정하지 않고, **오늘의 뉴스를 검색해서** 게시물을 만들 수 있습니다.

```bash
python -m src.main --news --dry-run   # 미리보기 (업로드 안 함)
python -m src.main --news             # 실제 업로드
```

검색 주제를 바꾸려면 `.env` 의 `NEWS_QUERY` 를 수정하세요.
예: `NEWS_QUERY=오늘의 IT 기술 뉴스`

---

## 6. 매일 한국 시간 오전 6시 자동 실행

### 방법 A — 내장 스케줄러 (간단)

```bash
python -m src.scheduler            # settings.json 의 시각에 매일 실행
python -m src.scheduler --dry-run  # 테스트(업로드 안 함)
```

실행 시각·켜짐 여부·뉴스 검색어는 **웹 UI의 "자동 게시 설정" 탭**에서 바꾸면
`settings.json` 에 저장되고, 스케줄러가 그 값을 읽습니다.

이 프로세스가 계속 떠 있어야 동작합니다. 백그라운드 유지 예시:

```bash
nohup python -m src.scheduler >> output/scheduler.log 2>&1 &
```

### 방법 C — GitHub Actions (컴퓨터 없이 자동 실행, 추천) ⭐

내 컴퓨터를 켜둘 필요 없이 **GitHub 서버가 매일 6시(KST)에 대신 실행**합니다.
워크플로 파일은 이미 `.github/workflows/daily-news-post.yml` 에 포함되어 있습니다.

**설정 순서:**

1. 이 저장소를 GitHub에 올립니다(push).
2. GitHub 저장소 → **Settings → Secrets and variables → Actions → New repository secret**
   에서 아래 값을 등록합니다:
   - `ANTHROPIC_API_KEY`
   - `OPENAI_API_KEY`
   - `IG_USER_ID`
   - `IG_ACCESS_TOKEN`
   - (선택) `NEWS_QUERY`, `GRAPH_API_VERSION`
3. 끝! 매일 한국 시간 06:00(UTC 21:00)에 자동으로 게시됩니다.

**손으로 테스트:** 저장소 → **Actions** 탭 → "매일 뉴스 인스타 게시" → **Run workflow**
(미리보기만 하려면 `dry_run` 을 `true` 로).

> ⚠️ **중요:** GitHub Actions의 예약 실행(schedule)은 저장소의 **기본 브랜치**
> (보통 `main`)에 워크플로 파일이 있을 때만 동작합니다. 지금은 작업 브랜치에 있으므로,
> 자동 실행이 되려면 **`main` 브랜치에 병합(merge)** 해야 합니다.
> 참고로 예약 시각은 GitHub 부하 상황에 따라 수 분~수십 분 지연될 수 있습니다.

### 방법 B — cron (직접 운영하는 서버에 권장)

한국 시간은 UTC+9 고정(서머타임 없음)이라 **KST 06:00 = UTC 21:00** 입니다.

서버 시계가 **UTC** 인 경우:

```cron
0 21 * * * cd /path/to/project && /usr/bin/python -m src.main --news >> output/cron.log 2>&1
```

서버 시계가 **KST** 인 경우:

```cron
0 6 * * * cd /path/to/project && /usr/bin/python -m src.main --news >> output/cron.log 2>&1
```

---

## 프로젝트 구조

```
.
├── app.py                     # 웹 UI (streamlit run app.py)
├── get_kakao_token.py         # 카카오 리프레시 토큰 발급 도우미
├── get_credentials.py         # 인스타 토큰/IG_USER_ID 발급 도우미
├── src/
│   ├── config.py              # 환경 변수 로딩
│   ├── image_generator.py     # DALL·E 3 이미지 생성
│   ├── caption_generator.py   # Claude 캡션·해시태그 생성
│   ├── news_fetcher.py        # Claude web_search 로 오늘의 뉴스 검색
│   ├── coupang_fetcher.py     # 쿠팡 파트너스 URL → 상품 정보 수집
│   ├── screenshot_analyzer.py # 쿠팡 화면 캡처 → 상품 정보 + 상품 사진 추출 (비전)
│   ├── card_generator.py      # 카드뉴스 문구 생성 + PNG 렌더링 (Pillow)
│   ├── coupang.py             # 쿠팡 카드뉴스 명령줄 실행 (python -m src.coupang)
│   ├── instagram_publisher.py # Graph API 업로드 (컨테이너 생성 → 발행)
│   ├── kakao_sender.py        # 카카오톡 '나에게 보내기' 전송
│   ├── settings.py            # 자동 실행 설정 저장/로드 (settings.json)
│   ├── scheduler.py           # 설정한 시각에 매일 자동 실행
│   └── main.py                # 전체 흐름 오케스트레이션
├── requirements.txt
├── .env.example
└── README.md
```

---

## 동작 원리

```
주제 입력
  │
  ├─▶ DALL·E 3 ──▶ 이미지 URL (임시, 약 1시간 유효)
  │
  ├─▶ Claude ────▶ 캡션 + 해시태그 (구조화된 JSON)
  │
  └─▶ Instagram Graph API
        1) /media          (image_url + caption) → creation_id
        2) 상태가 FINISHED 될 때까지 대기
        3) /media_publish  (creation_id)         → 게시물 ID ✅
```

DALL·E가 주는 임시 이미지 URL을 인스타가 직접 가져가므로 별도 이미지 호스팅이
필요 없습니다.

---

## 주의사항 / 한계

- **Graph API 제약**: 인스타 비즈니스/크리에이터 계정 + Facebook 페이지 연결이 필수입니다.
- **발행 한도**: 계정당 24시간에 약 50개 게시물 발행 제한이 있습니다.
- **토큰 만료**: 장기 토큰도 약 60일 후 만료됩니다. 주기적 갱신이 필요합니다.
- **이미지 URL 유효시간**: DALL·E URL은 약 1시간 유효하므로, 생성 직후 바로 업로드합니다.
- **비용**: DALL·E 이미지 생성과 Claude/OpenAI API 호출에는 사용료가 부과됩니다.
