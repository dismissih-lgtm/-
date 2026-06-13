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


# API 키
ANTHROPIC_API_KEY = _require("ANTHROPIC_API_KEY")
OPENAI_API_KEY = _require("OPENAI_API_KEY")

# Instagram Graph API
IG_USER_ID = _require("IG_USER_ID")
IG_ACCESS_TOKEN = _require("IG_ACCESS_TOKEN")
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v21.0")

# 캡션 생성에 사용할 Claude 모델
CAPTION_MODEL = "claude-opus-4-8"
