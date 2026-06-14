"""자동 게시 설정을 settings.json 파일에 저장/로드합니다.

UI에서 시간·켜짐 여부 등을 바꾸면 이 파일에 기록되고,
스케줄러가 실행할 때마다 이 값을 읽어 동작합니다. (코드 수정 불필요)
"""

import json
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "settings.json"

DEFAULTS = {
    "schedule_enabled": True,  # 매일 자동 실행 켜기/끄기
    "schedule_hour": 6,        # 실행 시각(시, KST)
    "schedule_minute": 0,      # 실행 시각(분)
    "news_query": "",          # 비우면 config.NEWS_QUERY 기본값 사용
    "destination": "kakao",    # 전송 대상: "kakao" 또는 "instagram"
}


def load() -> dict:
    """설정을 읽어 반환합니다. 파일이 없으면 기본값을 돌려줍니다."""
    data = {}
    if _PATH.exists():
        try:
            data = json.loads(_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    return {**DEFAULTS, **data}


def save(updates: dict) -> dict:
    """기존 설정에 updates 를 병합해 저장하고, 최종 설정을 반환합니다."""
    merged = {**load(), **updates}
    _PATH.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return merged
