# 인스타그램 게시물 자동 생성·업로드 봇

주제 한 줄만 입력하면 **AI가 이미지와 캡션·해시태그를 자동 생성**하고,
**Instagram Graph API(공식 API)** 로 게시물을 업로드합니다.

- 🎨 이미지: OpenAI **DALL·E 3**
- ✍️ 캡션·해시태그: **Claude** (`claude-opus-4-8`)
- 📤 업로드: **Instagram Graph API** (공식, 계정 정지 위험 없음)

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

> 💡 토큰 발급과 IG_USER_ID 확인은 [Graph API Explorer](https://developers.facebook.com/tools/explorer/)
> 에서 할 수 있습니다. 자세한 흐름은 Meta 공식 문서
> ["Content Publishing"](https://developers.facebook.com/docs/instagram-api/guides/content-publishing) 참고.

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

## 4. 실행

먼저 **업로드 없이** 이미지·캡션만 만들어 확인:

```bash
python -m src.main "가을 감성 카페 신메뉴 홍보" --dry-run
```

문제없으면 실제 업로드:

```bash
python -m src.main "가을 감성 카페 신메뉴 홍보"
```

---

## 5. 정기 자동 업로드 (선택)

cron으로 매일 정해진 시간에 자동 실행할 수 있습니다. 예) 매일 오전 9시:

```cron
0 9 * * * cd /path/to/project && /usr/bin/python -m src.main "오늘의 추천 메뉴" >> output/cron.log 2>&1
```

주제를 매번 바꾸고 싶다면, 주제 목록 파일에서 무작위로 뽑거나 날짜별 주제를
정하도록 `src/main.py` 를 응용하면 됩니다.

---

## 프로젝트 구조

```
.
├── src/
│   ├── config.py              # 환경 변수 로딩
│   ├── image_generator.py     # DALL·E 3 이미지 생성
│   ├── caption_generator.py   # Claude 캡션·해시태그 생성
│   ├── instagram_publisher.py # Graph API 업로드 (컨테이너 생성 → 발행)
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
