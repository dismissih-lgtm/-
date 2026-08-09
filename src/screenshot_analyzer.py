"""쿠팡 앱/웹 화면 캡처에서 상품 정보를 읽어냅니다 (Claude 비전).

휴대폰에서 쿠팡 상품 화면을 캡처해 올리면:
  1) 상품명·가격·특징 등 텍스트 정보를 읽어내고
  2) 캡처 안의 '상품 사진' 영역 좌표를 찾아 잘라내서
카드뉴스 생성에 바로 쓸 수 있는 형태로 반환합니다.
"""

import base64
import io
import json

import anthropic
from PIL import Image

from . import config

# API 전송 전 축소 기준 (토큰 절약, 좌표는 축소된 이미지 기준으로 주고받음)
_MAX_EDGE = 2200


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=config.require("ANTHROPIC_API_KEY"))


_SYSTEM = (
    "너는 쇼핑 앱 화면 캡처 분석가야. 쿠팡 상품 화면 캡처에서 상품 정보를 "
    "정확히 읽어내. 화면에 실제로 보이는 내용만 추출하고, 보이지 않는 값은 "
    "빈 문자열로 둬. 가격은 할인가(실제 판매가) 기준으로."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "상품명 (화면에 보이는 그대로, 불필요한 옵션 문구는 정리)"},
        "price": {"type": "string", "description": "판매가 (예: 29,900원). 안 보이면 빈 문자열"},
        "category": {"type": "string", "description": "상품 카테고리 추정 (예: 주방용품)"},
        "features": {
            "type": "array",
            "items": {"type": "string"},
            "description": "화면에서 확인되는 특징/장점/옵션 4~5개 (리뷰 평점, 로켓배송 여부 포함 가능)",
        },
        "summary": {"type": "string", "description": "상품을 소개하는 2~3문장 한국어 요약"},
        "product_image_box": {
            "type": "object",
            "description": "캡처 안 '상품 사진' 영역의 픽셀 좌표",
            "properties": {
                "found": {"type": "boolean", "description": "상품 사진이 캡처에 보이는지"},
                "x1": {"type": "integer", "description": "왼쪽 위 x"},
                "y1": {"type": "integer", "description": "왼쪽 위 y"},
                "x2": {"type": "integer", "description": "오른쪽 아래 x"},
                "y2": {"type": "integer", "description": "오른쪽 아래 y"},
            },
            "required": ["found", "x1", "y1", "x2", "y2"],
            "additionalProperties": False,
        },
    },
    "required": ["name", "price", "category", "features", "summary", "product_image_box"],
    "additionalProperties": False,
}


def load_image(data: bytes) -> Image.Image:
    """업로드된 이미지를 RGB 로 열고, 너무 크면 축소합니다."""
    img = Image.open(io.BytesIO(data)).convert("RGB")
    if max(img.size) > _MAX_EDGE:
        img.thumbnail((_MAX_EDGE, _MAX_EDGE), Image.LANCZOS)
    return img


def _crop_product_photo(img: Image.Image, box: dict) -> Image.Image | None:
    """모델이 알려준 좌표로 상품 사진을 잘라냅니다. 좌표가 이상하면 None."""
    if not box or not box.get("found"):
        return None
    x1 = max(0, min(int(box["x1"]), img.width))
    y1 = max(0, min(int(box["y1"]), img.height))
    x2 = max(0, min(int(box["x2"]), img.width))
    y2 = max(0, min(int(box["y2"]), img.height))
    w, h = x2 - x1, y2 - y1
    # 너무 작거나(오탐) 캡처 전체(경계 미인식)면 사용하지 않음
    if w < 180 or h < 180:
        return None
    if w * h < img.width * img.height * 0.04:
        return None
    return img.crop((x1, y1, x2, y2))


def analyze_screenshot(data: bytes) -> tuple[dict, Image.Image | None]:
    """캡처 이미지에서 (상품 정보 dict, 잘라낸 상품 사진 or None) 을 반환합니다."""
    img = load_image(data)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    b64 = base64.standard_b64encode(buf.getvalue()).decode()

    prompt = (
        f"이 화면 캡처(크기 {img.width}x{img.height} 픽셀)에서 상품 정보를 추출해줘.\n"
        "product_image_box 에는 캡처 안에서 상품 '사진'이 차지하는 영역의 픽셀 좌표를 "
        "넣어줘 (x1,y1 = 왼쪽 위, x2,y2 = 오른쪽 아래). 상태바·버튼·텍스트 영역은 "
        "제외하고 사진 부분만 정확하게. 상품 사진이 안 보이면 found 를 false 로 해."
    )
    response = _client().messages.create(
        model=config.CAPTION_MODEL,
        max_tokens=2000,
        thinking={"type": "adaptive"},
        system=_SYSTEM,
        output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": b64},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    text = next(b.text for b in response.content if b.type == "text")
    result = json.loads(text)

    photo = _crop_product_photo(img, result.pop("product_image_box", {}))
    info = {
        "name": result.get("name", ""),
        "price": result.get("price", ""),
        "category": result.get("category", ""),
        "features": result.get("features", []),
        "summary": result.get("summary", ""),
        "url": "",
    }
    return info, photo
