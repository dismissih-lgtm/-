"""Claude의 내장 web_search 도구로 오늘의 뉴스를 검색·정리합니다.

별도의 뉴스 API 키 없이, 이미 사용 중인 Anthropic 키만으로 동작합니다.
검색 결과 중 게시물로 만들기 좋은 뉴스 하나를 골라
{"headline": ..., "summary": ...} 형태로 돌려줍니다.
"""

import json

import anthropic

from . import config

client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

# web_search 는 Anthropic이 서버에서 실행하는 도구입니다 (GA).
_TOOLS = [{"type": "web_search_20260209", "name": "web_search"}]

_SYSTEM = (
    "너는 뉴스 큐레이터야. web_search 도구로 오늘의 최신 뉴스를 검색하고, "
    "인스타그램 게시물로 만들기 좋은 가장 흥미롭고 긍정적인 뉴스 하나를 골라 정리해. "
    "선정성·자극적이거나 비극적인 사건은 피하고, 사실에 기반해 작성해."
)


def _extract_json(text: str) -> dict:
    """web_search 응답 텍스트에서 JSON 객체만 추출합니다."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"응답에서 JSON을 찾지 못했습니다:\n{text}")
    return json.loads(text[start : end + 1])


def fetch_top_news(query: str | None = None) -> dict:
    """오늘의 뉴스를 검색해 {'headline': str, 'summary': str} 를 반환합니다."""
    query = query or config.NEWS_QUERY
    prompt = (
        f"'{query}' 를(을) 검색해서 가장 흥미로운 뉴스 하나를 선정해줘. "
        "그런 다음 아래 형식의 JSON 으로만 답해 (다른 설명·인용 없이 JSON만):\n"
        '{"headline": "이미지 생성에 쓸 한 줄 핵심 헤드라인", '
        '"summary": "게시물 캡션 재료가 될 2~4문장의 친근한 한국어 요약"}'
    )

    messages = [{"role": "user", "content": prompt}]

    # web_search 가 서버측 반복 한도에 걸리면 pause_turn 으로 끊길 수 있어 이어서 호출.
    response = None
    for _ in range(5):
        response = client.messages.create(
            model=config.CAPTION_MODEL,
            max_tokens=4000,
            system=_SYSTEM,
            tools=_TOOLS,
            messages=messages,
        )
        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue
        break

    text = "".join(b.text for b in response.content if b.type == "text")
    return _extract_json(text)
