"""쿠팡 파트너스 URL에서 상품 정보를 가져옵니다.

쿠팡은 봇 접근을 강하게 차단하므로 3단계로 시도합니다.
  1) 직접 접속해 og:title 등 메타 정보 파싱 (짧은 링크 리다이렉트 포함)
  2) Claude의 web_fetch / web_search 도구로 상품 확인·검색
  3) 둘 다 실패하면 호출자에게 부분 정보만 반환 → UI/CLI에서 직접 입력

반환 형식:
    {"name": str, "price": str, "category": str,
     "features": [str, ...], "summary": str, "url": str}
값을 찾지 못한 항목은 빈 문자열/빈 리스트입니다.
"""

import html
import json
import re

import anthropic
import requests

from . import config

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

_EMPTY = {"name": "", "price": "", "category": "", "features": [], "summary": "", "url": ""}


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=config.require("ANTHROPIC_API_KEY"))


# web_fetch/web_search 는 Anthropic이 서버에서 실행하는 도구입니다.
_TOOLS = [
    {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 5},
    {"type": "web_search_20260209", "name": "web_search", "max_uses": 5},
]

_SYSTEM = (
    "너는 쇼핑 상품 리서처야. 주어진 쿠팡 파트너스 링크의 상품이 무엇인지 "
    "web_fetch 로 확인하고, 부족한 정보는 web_search 로 보충해. "
    "사실에 근거해서만 작성하고, 확인되지 않은 가격·스펙은 빈 값으로 둬."
)


def _scrape(url: str) -> dict:
    """직접 접속해 메타 정보를 파싱합니다. 차단되면 빈 dict."""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": _UA, "Accept-Language": "ko-KR,ko;q=0.9"},
            timeout=10,
            allow_redirects=True,
        )
        if not resp.ok:
            return {"url": resp.url}
        text = resp.text
        info = {"url": resp.url}

        m = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', text)
        if m:
            name = html.unescape(m.group(1))
            info["name"] = re.sub(r"\s*[-|]\s*쿠팡!?$", "", name).strip()

        m = re.search(r'"(?:salePrice|couponPrice|discountedPrice)"\s*:\s*(\d+)', text)
        if m:
            info["price"] = f"{int(m.group(1)):,}원"

        m = re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"', text)
        if m:
            info["summary"] = html.unescape(m.group(1)).strip()

        return info
    except requests.RequestException:
        return {}


def _extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"응답에서 JSON을 찾지 못했습니다:\n{text}")
    return json.loads(text[start : end + 1])


def _ask_claude(url: str, partial: dict) -> dict:
    """Claude web_fetch/web_search 로 상품 정보를 조사합니다."""
    hint = f"참고로 지금까지 파악된 정보: {json.dumps(partial, ensure_ascii=False)}\n" if partial.get("name") else ""
    prompt = (
        f"쿠팡 파트너스 링크야: {url}\n"
        f"{hint}"
        "이 링크의 상품이 무엇인지 확인하고 (링크를 web_fetch 로 열어보고, "
        "안 열리면 상품명을 web_search 로 검색해), 아래 형식의 JSON 으로만 답해 "
        "(다른 설명 없이 JSON만):\n"
        '{"name": "정확한 상품명", "price": "판매가 (예: 29,900원, 모르면 빈 문자열)", '
        '"category": "상품 카테고리 (예: 주방용품)", '
        '"features": ["구매자가 좋아할 핵심 특징/장점 4~5개"], '
        '"summary": "상품을 소개하는 2~3문장의 한국어 요약"}'
    )

    messages = [{"role": "user", "content": prompt}]
    client = _client()
    response = None
    # 서버측 도구가 반복 한도에 걸리면 pause_turn 으로 끊길 수 있어 이어서 호출.
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


def fetch_product_info(url: str) -> dict:
    """쿠팡 파트너스 URL에서 상품 정보를 최대한 수집해 반환합니다."""
    info = dict(_EMPTY)
    info["url"] = url

    scraped = _scrape(url)
    info.update({k: v for k, v in scraped.items() if v})

    # 이름/특징이 부족하면 Claude 로 보충
    if not (info["name"] and info["features"]):
        try:
            found = _ask_claude(url, info)
            for key in ("name", "price", "category", "features", "summary"):
                if found.get(key) and not info.get(key):
                    info[key] = found[key]
        except Exception:  # noqa: BLE001 - 조사 실패 시 부분 정보로 진행
            pass

    return info
