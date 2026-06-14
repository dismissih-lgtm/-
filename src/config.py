"""환경 변수를 읽어 한곳에서 관리합니다."""

import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"환경 변수 {name} 가 설정되지 않았습니다. .env 파일을 확인하세요."
        )
    return value


def _optional(name: str, default: str) -> str:
    """빈 문자열(예: 비어 있는 GitHub Secret)도 기본값으로 처리합니다."""
    value = os.getenv(name)
    return value if value else default


# API 키
ANTHROPIC_API_KEY = _require("ANTHROPIC_API_KEY")
OPENAI_API_KEY = _require("OPENAI_API_KEY")

# Instagram Graph API
IG_USER_ID = _require("IG_USER_ID")
IG_ACCESS_TOKEN = _require("IG_ACCESS_TOKEN")
GRAPH_API_VERSION = _optional("GRAPH_API_VERSION", "v21.0")

# 캡션 생성에 사용할 Claude 모델
CAPTION_MODEL = "claude-opus-4-8"

# 뉴스 검색어 (원하는 주제·카테고리로 바꿀 수 있습니다)
NEWS_QUERY = _optional("NEWS_QUERY", "오늘의 한국 주요 뉴스 헤드라인")
