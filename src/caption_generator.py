"""Claude를 이용해 인스타그램 캡션과 해시태그를 자동 생성합니다."""

import json

import anthropic

from . import config


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=config.require("ANTHROPIC_API_KEY"))

# 모델이 구조화된 JSON으로 답하도록 강제하는 스키마
_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "caption": {
            "type": "string",
            "description": "본문 캡션. 자연스럽고 매력적인 한국어. 적절한 이모지 포함.",
        },
        "hashtags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "# 기호를 포함한 해시태그 목록 (10~20개).",
        },
    },
    "required": ["caption", "hashtags"],
    "additionalProperties": False,
}

_SYSTEM = (
    "너는 인스타그램 마케팅 전문가야. 주어진 주제에 맞춰 참여율이 높은 "
    "게시물 캡션과 해시태그를 작성해. 캡션은 자연스러운 한국어로, 도입부 한 줄이 "
    "시선을 끌도록 쓰고, 이모지를 적절히 섞어. 해시태그는 주제와 관련성이 높은 "
    "것으로 10~20개 제안해."
)


def generate_caption(topic: str) -> dict:
    """주제를 받아 {'caption': str, 'hashtags': [str, ...]} 를 반환합니다."""
    response = _client().messages.create(
        model=config.CAPTION_MODEL,
        max_tokens=2000,
        thinking={"type": "adaptive"},
        system=_SYSTEM,
        output_config={
            "format": {"type": "json_schema", "schema": _OUTPUT_SCHEMA}
        },
        messages=[
            {
                "role": "user",
                "content": f"다음 주제로 인스타그램 게시물을 만들어줘: {topic}",
            }
        ],
    )

    # output_config.format 을 쓰면 첫 text 블록이 유효한 JSON 입니다.
    text = next(b.text for b in response.content if b.type == "text")
    data = json.loads(text)
    return data


def format_full_caption(data: dict) -> str:
    """캡션 본문과 해시태그를 하나의 문자열로 합칩니다."""
    caption = data["caption"].strip()
    hashtags = " ".join(data["hashtags"])
    return f"{caption}\n\n{hashtags}"
