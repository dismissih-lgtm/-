"""Instagram Graph API로 사진 게시물을 업로드합니다.

업로드는 2단계입니다.
  1) 미디어 컨테이너 생성: POST /{ig-user-id}/media  (image_url + caption)
  2) 발행:               POST /{ig-user-id}/media_publish (creation_id)
"""

import time

import requests

from . import config

_BASE = f"https://graph.facebook.com/{config.GRAPH_API_VERSION}"


def _create_media_container(image_url: str, caption: str) -> str:
    """1단계: 미디어 컨테이너를 만들고 creation_id 를 반환합니다."""
    url = f"{_BASE}/{config.require('IG_USER_ID')}/media"
    resp = requests.post(
        url,
        data={
            "image_url": image_url,
            "caption": caption,
            "access_token": config.require("IG_ACCESS_TOKEN"),
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def _wait_until_ready(creation_id: str, max_attempts: int = 10) -> None:
    """컨테이너가 발행 가능한 상태(FINISHED)가 될 때까지 대기합니다."""
    url = f"{_BASE}/{creation_id}"
    for _ in range(max_attempts):
        resp = requests.get(
            url,
            params={
                "fields": "status_code",
                "access_token": config.require("IG_ACCESS_TOKEN"),
            },
            timeout=30,
        )
        resp.raise_for_status()
        status = resp.json().get("status_code")
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError("미디어 컨테이너 처리 중 오류가 발생했습니다.")
        time.sleep(3)
    raise TimeoutError("미디어 컨테이너가 제한 시간 내에 준비되지 않았습니다.")


def _publish_media(creation_id: str) -> str:
    """2단계: 컨테이너를 발행하고 게시물 ID 를 반환합니다."""
    url = f"{_BASE}/{config.require('IG_USER_ID')}/media_publish"
    resp = requests.post(
        url,
        data={
            "creation_id": creation_id,
            "access_token": config.require("IG_ACCESS_TOKEN"),
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def publish_photo(image_url: str, caption: str) -> str:
    """사진 1장을 캡션과 함께 업로드하고 게시물 ID를 반환합니다."""
    creation_id = _create_media_container(image_url, caption)
    _wait_until_ready(creation_id)
    return _publish_media(creation_id)
