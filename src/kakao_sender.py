"""카카오톡 '나에게 보내기(메모) API'로 게시물을 본인에게 전송합니다.

친구 승인·사업자 심사 없이, 본인 카카오톡(나와의 채팅)으로 메시지를 보냅니다.
이미지(피드 카드) + 캡션(텍스트, 200자 단위로 분할)을 전송하므로,
받은 이미지를 저장하고 캡션을 복사해 인스타그램에 직접 올리면 됩니다.

필요한 값(.env):
  KAKAO_REST_API_KEY   카카오 개발자 앱의 REST API 키
  KAKAO_REFRESH_TOKEN  talk_message 권한 동의 후 받은 리프레시 토큰
                       (get_kakao_token.py 로 발급)
"""

import json

import requests

from . import config

_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
_MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"

# 카카오 텍스트 기본 템플릿의 text 최대 길이
_TEXT_LIMIT = 200


def _access_token() -> str:
    """리프레시 토큰으로 액세스 토큰을 새로 발급받습니다."""
    resp = requests.post(
        _TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": config.require("KAKAO_REST_API_KEY"),
            "refresh_token": config.require("KAKAO_REFRESH_TOKEN"),
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _send(template_object: dict, token: str) -> None:
    resp = requests.post(
        _MEMO_URL,
        headers={"Authorization": f"Bearer {token}"},
        data={"template_object": json.dumps(template_object, ensure_ascii=False)},
        timeout=30,
    )
    resp.raise_for_status()


def _send_feed(token: str, title: str, image_url: str) -> None:
    """이미지 카드(피드)를 보냅니다. 버튼으로 원본 이미지를 열 수 있습니다."""
    link = {"web_url": image_url, "mobile_web_url": image_url}
    template = {
        "object_type": "feed",
        "content": {
            "title": title[:100],
            "description": "탭하면 이미지를 크게 볼 수 있어요. 저장 후 인스타에 올리세요.",
            "image_url": image_url,
            "image_width": 1024,
            "image_height": 1024,
            "link": link,
        },
        "buttons": [{"title": "이미지 열기/저장", "link": link}],
    }
    _send(template, token)


def _send_text(token: str, text: str) -> None:
    """텍스트 메시지를 200자 단위로 나눠 보냅니다(캡션 복사용)."""
    chunks = [text[i : i + _TEXT_LIMIT] for i in range(0, len(text), _TEXT_LIMIT)] or [
        ""
    ]
    for chunk in chunks:
        template = {
            "object_type": "text",
            "text": chunk,
            "link": {"web_url": "", "mobile_web_url": ""},
        }
        _send(template, token)


def send_post(image_url: str, headline: str, caption: str) -> None:
    """이미지 카드 + 캡션을 본인 카카오톡으로 전송합니다."""
    token = _access_token()
    _send_feed(token, headline or "오늘의 인스타 게시물", image_url)
    _send_text(token, caption)
