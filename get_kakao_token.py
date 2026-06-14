"""카카오톡 '나에게 보내기' 리프레시 토큰 발급 도우미.

준비물(카카오 개발자 사이트 https://developers.kakao.com):
  1) 애플리케이션 추가 → REST API 키 확인
  2) [제품 설정 → 카카오 로그인] 활성화 ON
  3) [카카오 로그인 → Redirect URI] 에 https://localhost 등록
  4) [카카오 로그인 → 동의항목] 에서 '카카오톡 메시지 전송(talk_message)' 사용 설정

사용법:
    python get_kakao_token.py --rest-api-key <REST_API_KEY>

실행하면 브라우저에서 동의할 주소를 알려주고, 동의 후 이동된 주소(또는 code 값)를
붙여넣으면 .env 에 넣을 KAKAO_REFRESH_TOKEN 을 출력합니다.
"""

import argparse
import os
import sys
import urllib.parse

import requests

AUTHORIZE = "https://kauth.kakao.com/oauth/authorize"
TOKEN = "https://kauth.kakao.com/oauth/token"


def _extract_code(raw: str) -> str:
    """사용자가 붙여넣은 주소 또는 code 문자열에서 인가 코드를 뽑습니다."""
    raw = raw.strip()
    if "code=" in raw:
        query = urllib.parse.urlparse(raw).query or raw.split("?", 1)[-1]
        params = urllib.parse.parse_qs(query)
        if "code" in params:
            return params["code"][0]
    return raw


def main() -> None:
    parser = argparse.ArgumentParser(description="카카오 리프레시 토큰 발급")
    parser.add_argument("--rest-api-key", default=os.getenv("KAKAO_REST_API_KEY"))
    parser.add_argument("--redirect-uri", default="https://localhost")
    args = parser.parse_args()

    if not args.rest_api_key:
        parser.error("--rest-api-key 가 필요합니다 (또는 KAKAO_REST_API_KEY 환경변수).")

    authorize_url = (
        f"{AUTHORIZE}?client_id={args.rest_api_key}"
        f"&redirect_uri={urllib.parse.quote(args.redirect_uri, safe='')}"
        f"&response_type=code&scope=talk_message"
    )

    print("\n1) 아래 주소를 브라우저에서 열고 '동의하기' 를 누르세요:\n")
    print(authorize_url)
    print(
        "\n2) 동의 후 빈 페이지(주소창에 ...?code=XXXX)로 이동합니다.\n"
        "   그 주소 전체 또는 code 값을 복사하세요.\n"
    )

    raw = input("이동된 주소 또는 code 값을 붙여넣으세요: ")
    code = _extract_code(raw)

    try:
        resp = requests.post(
            TOKEN,
            data={
                "grant_type": "authorization_code",
                "client_id": args.rest_api_key,
                "redirect_uri": args.redirect_uri,
                "code": code,
            },
            timeout=30,
        )
        resp.raise_for_status()
    except requests.HTTPError as exc:
        body = exc.response.text if exc.response is not None else ""
        print(f"\n❌ 토큰 발급 실패: {exc}\n{body}", file=sys.stderr)
        sys.exit(1)

    data = resp.json()
    refresh = data.get("refresh_token")
    if not refresh:
        print(
            "\n⚠️ refresh_token 이 응답에 없습니다. 동의항목에 talk_message 가 "
            f"켜져 있는지 확인하세요.\n응답: {data}",
            file=sys.stderr,
        )
        sys.exit(1)

    print("\n✅ 성공! .env 에 아래 두 줄을 넣으세요:\n")
    print(f"KAKAO_REST_API_KEY={args.rest_api_key}")
    print(f"KAKAO_REFRESH_TOKEN={refresh}")
    print()


if __name__ == "__main__":
    main()
