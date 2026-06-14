"""인스타그램 토큰/ID 발급 도우미.

Graph API Explorer에서 받은 '짧은 수명 토큰'을 넣으면
  1) 만료 안 되는 장기 토큰으로 바꾸고
  2) 연결된 인스타그램 비즈니스 계정의 IG_USER_ID 를 찾아
.env 에 넣을 값을 그대로 출력합니다.

사용법:
    python get_credentials.py \
        --app-id 1234567890 \
        --app-secret abcdef... \
        --token EAAG...(짧은 수명 사용자 토큰)

또는 환경변수로:
    FB_APP_ID, FB_APP_SECRET, FB_SHORT_TOKEN
"""

import argparse
import os
import sys

import requests

GRAPH = "https://graph.facebook.com/v21.0"


def exchange_long_lived(app_id: str, app_secret: str, short_token: str) -> str:
    """짧은 수명 토큰을 장기(약 60일) 사용자 토큰으로 교환합니다."""
    resp = requests.get(
        f"{GRAPH}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def find_pages(user_token: str) -> list[dict]:
    """내 페이지 목록과 각 페이지에 연결된 인스타 계정을 조회합니다.

    장기 사용자 토큰에서 나온 페이지 토큰은 사실상 만료되지 않습니다.
    """
    resp = requests.get(
        f"{GRAPH}/me/accounts",
        params={
            "fields": "name,id,access_token,instagram_business_account{id,username}",
            "access_token": user_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def main() -> None:
    parser = argparse.ArgumentParser(description="인스타 토큰/ID 발급 도우미")
    parser.add_argument("--app-id", default=os.getenv("FB_APP_ID"))
    parser.add_argument("--app-secret", default=os.getenv("FB_APP_SECRET"))
    parser.add_argument("--token", default=os.getenv("FB_SHORT_TOKEN"))
    args = parser.parse_args()

    if not (args.app_id and args.app_secret and args.token):
        parser.error(
            "app-id, app-secret, token 이 모두 필요합니다 "
            "(인자 또는 FB_APP_ID/FB_APP_SECRET/FB_SHORT_TOKEN 환경변수)."
        )

    try:
        print("🔄 장기 토큰으로 교환 중...")
        long_token = exchange_long_lived(args.app_id, args.app_secret, args.token)

        print("🔍 연결된 인스타그램 계정 조회 중...\n")
        pages = find_pages(long_token)
    except requests.HTTPError as exc:
        body = exc.response.text if exc.response is not None else ""
        print(f"\n❌ 요청 실패: {exc}\n{body}", file=sys.stderr)
        sys.exit(1)

    found = False
    for page in pages:
        ig = page.get("instagram_business_account")
        if not ig:
            continue
        found = True
        print("=" * 60)
        print(f"📄 페이지: {page['name']} (id={page['id']})")
        print(f"📸 인스타: @{ig.get('username', '?')}")
        print("\n👉 .env 에 아래 값을 넣으세요:\n")
        print(f"IG_USER_ID={ig['id']}")
        print(f"IG_ACCESS_TOKEN={page['access_token']}")
        print("=" * 60 + "\n")

    if not found:
        print(
            "⚠️ 인스타그램 비즈니스 계정이 연결된 페이지를 찾지 못했습니다.\n"
            "   - 인스타가 '비즈니스/크리에이터' 계정인지\n"
            "   - 페이스북 페이지에 연결되어 있는지\n"
            "   - 토큰에 instagram_basic, pages_show_list 권한이 있는지\n"
            "   확인하세요.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
