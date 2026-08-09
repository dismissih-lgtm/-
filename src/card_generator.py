"""쿠팡 파트너스 카드뉴스 생성.

  1) Claude 로 카드별 문구(카피)를 구조화된 JSON 으로 생성
  2) Pillow 로 인스타그램 규격(1:1 1080x1080 / 4:5 1080x1350) PNG 렌더링

한글 폰트(Noto Sans KR)는 assets/fonts/ 에 없으면 최초 1회 자동 다운로드합니다.
CARD_FONT_PATH 환경 변수로 다른 폰트를 지정할 수도 있습니다.
"""

import json
import os
from pathlib import Path

import anthropic
import requests
from PIL import Image, ImageDraw, ImageFont

from . import config

# 쿠팡 파트너스 필수 고지 문구 (카드와 캡션에 항상 포함)
DISCLOSURE = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."

RATIOS = {"1:1": (1080, 1080), "4:5": (1080, 1350)}

THEMES = {
    "딥 네이비": {
        "bg_top": (13, 21, 40), "bg_bottom": (30, 58, 95),
        "text": (255, 255, 255), "sub": (196, 208, 224),
        "accent": (245, 158, 11), "accent_text": (20, 24, 38),
    },
    "웜 크림": {
        "bg_top": (246, 242, 234), "bg_bottom": (235, 226, 210),
        "text": (43, 38, 34), "sub": (110, 100, 90),
        "accent": (196, 90, 56), "accent_text": (255, 250, 242),
    },
    "차콜 민트": {
        "bg_top": (24, 26, 27), "bg_bottom": (38, 44, 44),
        "text": (245, 245, 244), "sub": (178, 186, 184),
        "accent": (52, 211, 153), "accent_text": (17, 24, 22),
    },
}

# ─────────────────────────────────────────────────────
# 1. 카드 문구 생성 (Claude)
# ─────────────────────────────────────────────────────

_COPY_SCHEMA = {
    "type": "object",
    "properties": {
        "cover": {
            "type": "object",
            "properties": {
                "badge": {"type": "string", "description": "상단 작은 배지 문구 (2~6자, 예: 오늘의 발견)"},
                "headline": {"type": "string", "description": "시선을 끄는 큰 헤드라인 (질문형/공감형, 30자 이내)"},
                "sub": {"type": "string", "description": "헤드라인을 보조하는 한 문장 (40자 이내)"},
            },
            "required": ["badge", "headline", "sub"],
            "additionalProperties": False,
        },
        "features": {
            "type": "array",
            "description": "특징 카드 목록",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "카드 제목 (20자 이내)"},
                    "points": {
                        "type": "array",
                        "items": {"type": "string", "description": "특징 한 줄 (35자 이내)"},
                        "description": "특징 3~4개",
                    },
                },
                "required": ["title", "points"],
                "additionalProperties": False,
            },
        },
        "cta": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "마지막 카드 제목 (예: 지금이 가장 좋을 때, 20자 이내)"},
                "sub": {"type": "string", "description": "행동 유도 한 문장 (40자 이내)"},
                "price_line": {"type": "string", "description": "가격 강조 문구 (가격을 모르면 빈 문자열)"},
            },
            "required": ["title", "sub", "price_line"],
            "additionalProperties": False,
        },
        "caption": {"type": "string", "description": "인스타그램 캡션 본문 (이모지 포함 가능)"},
        "hashtags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "# 포함 해시태그 10~15개",
        },
    },
    "required": ["cover", "features", "cta", "caption", "hashtags"],
    "additionalProperties": False,
}

_COPY_SYSTEM = (
    "너는 쿠팡 파트너스 카드뉴스 카피라이터야. 상품 정보를 받아 인스타그램 "
    "카드뉴스용 문구를 작성해. 규칙:\n"
    "1) 카드에 들어가는 문구(cover/features/cta)에는 이모지·특수기호를 절대 쓰지 마 "
    "(렌더링 폰트가 지원하지 않음). 캡션(caption)에는 이모지를 써도 좋아.\n"
    "2) 첫 카드는 스크롤을 멈추게 하는 공감형/질문형 훅으로 써.\n"
    "3) 과장·허위 문구(최저가 보장, 효과 보장 등)는 금지. 사실 기반으로만.\n"
    "4) 문장은 짧고 구어체로, 카드 한 장에서 바로 읽히게.\n"
    "5) 캡션 마지막에 '링크는 프로필에서 확인하세요' 같은 유도 문구를 넣어."
)


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=config.require("ANTHROPIC_API_KEY"))


def generate_copy(product: dict, n_cards: int = 4) -> dict:
    """상품 정보로 카드 문구 JSON 을 생성합니다. n_cards 는 3 또는 4."""
    n_features = max(1, n_cards - 2)  # 표지 1 + 특징 n + CTA 1
    prompt = (
        f"다음 상품으로 카드뉴스 {n_cards}장 문구를 만들어줘 "
        f"(표지 1장 + 특징 카드 {n_features}장 + 마지막 행동유도 카드 1장).\n"
        f"상품 정보:\n{json.dumps(product, ensure_ascii=False, indent=2)}"
    )
    response = _client().messages.create(
        model=config.CAPTION_MODEL,
        max_tokens=3000,
        thinking={"type": "adaptive"},
        system=_COPY_SYSTEM,
        output_config={"format": {"type": "json_schema", "schema": _COPY_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    text = next(b.text for b in response.content if b.type == "text")
    data = json.loads(text)
    data["features"] = data["features"][:n_features]
    return data


def format_caption(copy_data: dict, url: str = "") -> str:
    """캡션 + 해시태그 + 파트너스 고지를 하나의 문자열로 합칩니다."""
    parts = [copy_data["caption"].strip()]
    if url:
        parts.append(f"🛒 구매 링크\n{url}")
    parts.append(" ".join(copy_data["hashtags"]))
    parts.append(DISCLOSURE)
    return "\n\n".join(parts)


# ─────────────────────────────────────────────────────
# 2. 폰트 준비
# ─────────────────────────────────────────────────────

_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_FONT_PATH = _FONT_DIR / "NotoSansKR.ttf"
_FONT_URLS = [
    "https://raw.githubusercontent.com/google/fonts/main/ofl/notosanskr/NotoSansKR%5Bwght%5D.ttf",
    "https://github.com/google/fonts/raw/main/ofl/notosanskr/NotoSansKR%5Bwght%5D.ttf",
    "https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/notosanskr/NotoSansKR%5Bwght%5D.ttf",
]


def _ensure_font() -> Path:
    """한글 폰트 경로를 반환합니다. 없으면 다운로드합니다."""
    custom = os.getenv("CARD_FONT_PATH")
    if custom and Path(custom).exists():
        return Path(custom)
    if _FONT_PATH.exists():
        return _FONT_PATH

    _FONT_DIR.mkdir(parents=True, exist_ok=True)
    last_error = None
    for url in _FONT_URLS:
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            _FONT_PATH.write_bytes(resp.content)
            return _FONT_PATH
        except requests.RequestException as exc:
            last_error = exc
    raise RuntimeError(
        "한글 폰트 다운로드에 실패했습니다. 인터넷 연결을 확인하거나 "
        "CARD_FONT_PATH 환경 변수로 한글 TTF 경로를 지정하세요."
    ) from last_error


def _font(size: int, weight: int = 400) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(_ensure_font()), size)
    try:  # 가변 폰트 굵기 (FreeType 미지원 환경이면 기본 굵기 사용)
        font.set_variation_by_axes([weight])
    except OSError:
        pass
    return font


# ─────────────────────────────────────────────────────
# 3. 렌더링 (Pillow)
# ─────────────────────────────────────────────────────

_MARGIN = 96


def _wrap(font: ImageFont.FreeTypeFont, text: str, max_width: int) -> list[str]:
    """단어 단위로 줄바꿈하되, 한 단어가 너무 길면 글자 단위로 자릅니다."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if font.getlength(candidate) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        # 단어 자체가 폭을 넘으면 글자 단위 분할
        while font.getlength(word) > max_width:
            for i in range(len(word), 0, -1):
                if font.getlength(word[:i]) <= max_width:
                    lines.append(word[:i])
                    word = word[i:]
                    break
            else:
                break
        current = word
    if current:
        lines.append(current)
    return lines or [""]


def _draw_wrapped(draw, font, text, x, y, max_width, fill, line_gap=1.28, max_lines=None):
    """줄바꿈된 텍스트를 그리고 다음 y 좌표를 반환합니다."""
    lines = _wrap(font, text, max_width)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip() + "…"
    line_height = int(font.size * line_gap)
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


def _fit_image(photo: Image.Image, w: int, h: int) -> Image.Image:
    """사진을 (w, h) 영역에 꽉 차게(cover) 맞춰 자릅니다."""
    scale = max(w / photo.width, h / photo.height)
    resized = photo.resize(
        (int(photo.width * scale) + 1, int(photo.height * scale) + 1), Image.LANCZOS
    )
    left = (resized.width - w) // 2
    top = (resized.height - h) // 2
    return resized.crop((left, top, left + w, top + h))


def _paste_rounded(base: Image.Image, photo: Image.Image, x: int, y: int,
                   w: int, h: int, radius: int = 28) -> None:
    """둥근 모서리로 사진을 붙입니다."""
    fitted = _fit_image(photo.convert("RGB"), w, h)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    base.paste(fitted, (x, y), mask)


def _gradient(size: tuple[int, int], top: tuple, bottom: tuple) -> Image.Image:
    width, height = size
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(height):
        t = y / max(height - 1, 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(width):
            px[x, y] = color
    return img


def _draw_dots(draw, size, theme, index, total):
    """하단 중앙 페이지 인디케이터."""
    width, height = size
    r, gap = 7, 30
    total_w = (total - 1) * gap
    x0 = width // 2 - total_w // 2
    y = height - 64
    for i in range(total):
        color = theme["accent"] if i == index else theme["sub"]
        rr = r + 2 if i == index else r
        draw.ellipse([x0 + i * gap - rr, y - rr, x0 + i * gap + rr, y + rr], fill=color)


def _draw_page_number(draw, size, theme, index, total):
    text = f"{index + 1}/{total}"
    font = _font(30, 500)
    draw.text((size[0] - _MARGIN - font.getlength(text), 60), text, font=font, fill=theme["sub"])


def _draw_badge(draw, theme, text, x, y):
    font = _font(34, 700)
    pad_x, pad_y = 30, 16
    w = font.getlength(text)
    draw.rounded_rectangle(
        [x, y, x + w + pad_x * 2, y + font.size + pad_y * 2],
        radius=(font.size + pad_y * 2) // 2,
        fill=theme["accent"],
    )
    draw.text((x + pad_x, y + pad_y), text, font=font, fill=theme["accent_text"])
    return y + font.size + pad_y * 2


def _draw_check(draw, theme, cx, cy, r=22):
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=theme["accent"])
    line_w = 6
    draw.line([cx - r * 0.45, cy, cx - r * 0.1, cy + r * 0.35], fill=theme["accent_text"], width=line_w)
    draw.line([cx - r * 0.1, cy + r * 0.35, cx + r * 0.5, cy - r * 0.35], fill=theme["accent_text"], width=line_w)


def _render_cover(img, theme, cover, index, total, photo=None):
    draw = ImageDraw.Draw(img)
    width, height = img.size
    max_w = width - _MARGIN * 2

    if photo is not None:
        # 사진이 있으면: 배지 → 상품 사진 → 헤드라인 → 보조 문장
        badge_bottom = _draw_badge(draw, theme, cover["badge"], _MARGIN, 78)
        photo_h = int(height * 0.38)
        _paste_rounded(img, photo, _MARGIN, badge_bottom + 34, max_w, photo_h)
        draw = ImageDraw.Draw(img)  # paste 이후 다시 획득

        y = badge_bottom + 34 + photo_h + 46
        y = _draw_wrapped(draw, _font(60, 800), cover["headline"], _MARGIN, y, max_w,
                          theme["text"], line_gap=1.22, max_lines=3)
        y += 18
        _draw_wrapped(draw, _font(37, 400), cover["sub"], _MARGIN, y, max_w,
                      theme["sub"], max_lines=2)
    else:
        _draw_badge(draw, theme, cover["badge"], _MARGIN, int(height * 0.14))

        y = int(height * 0.30)
        y = _draw_wrapped(draw, _font(86, 800), cover["headline"], _MARGIN, y, max_w,
                          theme["text"], line_gap=1.24, max_lines=4)

        y += 36
        draw.rounded_rectangle([_MARGIN, y, _MARGIN + 140, y + 10], radius=5, fill=theme["accent"])
        y += 52
        _draw_wrapped(draw, _font(42, 400), cover["sub"], _MARGIN, y, max_w, theme["sub"], max_lines=3)

    hint = "밀어서 넘겨보기"
    font = _font(32, 500)
    draw.text((width // 2 - font.getlength(hint) / 2, img.size[1] - 130), hint,
              font=font, fill=theme["sub"])
    _draw_dots(draw, img.size, theme, index, total)
    _draw_page_number(draw, img.size, theme, index, total)


def _render_feature(img, theme, feature, point_no, index, total):
    draw = ImageDraw.Draw(img)
    width, height = img.size
    max_w = width - _MARGIN * 2

    kicker_font = _font(36, 700)
    draw.text((_MARGIN, int(height * 0.13)), f"POINT {point_no}", font=kicker_font, fill=theme["accent"])

    y = int(height * 0.13) + 70
    y = _draw_wrapped(draw, _font(66, 800), feature["title"], _MARGIN, y, max_w,
                      theme["text"], max_lines=3)

    y += 40
    body_font = _font(42, 400)
    text_x = _MARGIN + 66
    for point in feature["points"][:4]:
        _draw_check(draw, theme, _MARGIN + 22, y + int(body_font.size * 0.62))
        next_y = _draw_wrapped(draw, body_font, point, text_x, y, max_w - 66,
                               theme["text"], max_lines=2)
        y = next_y + 30

    _draw_dots(draw, img.size, theme, index, total)
    _draw_page_number(draw, img.size, theme, index, total)


def _render_cta(img, theme, cta, index, total, photo=None):
    draw = ImageDraw.Draw(img)
    width, height = img.size
    max_w = width - _MARGIN * 2

    if photo is not None:
        # 정사각 상품 사진을 상단 중앙에 배치
        ph = int(height * 0.26)
        _paste_rounded(img, photo, (width - ph) // 2, int(height * 0.09), ph, ph)
        draw = ImageDraw.Draw(img)
        y = int(height * 0.09) + ph + 50
        title_font = _font(62, 800)
    else:
        y = int(height * 0.20)
        title_font = _font(74, 800)

    y = _draw_wrapped(draw, title_font, cta["title"], _MARGIN, y, max_w,
                      theme["text"], max_lines=3)

    if cta.get("price_line"):
        y += 24
        y = _draw_wrapped(draw, _font(52 if photo else 58, 700), cta["price_line"],
                          _MARGIN, y, max_w, theme["accent"], max_lines=2)

    y += 26
    _draw_wrapped(draw, _font(38 if photo else 42, 400), cta["sub"], _MARGIN, y,
                  max_w, theme["sub"], max_lines=2 if photo else 3)

    # 링크 안내 박스 (하단 기준 고정 배치)
    box_text = "구매 링크는 프로필에서 확인"
    box_font = _font(40, 700)
    pad_x, pad_y = 44, 26
    bw = box_font.getlength(box_text) + pad_x * 2
    bx = width / 2 - bw / 2
    by = height - 296
    draw.rounded_rectangle([bx, by, bx + bw, by + box_font.size + pad_y * 2],
                           radius=18, fill=theme["accent"])
    draw.text((bx + pad_x, by + pad_y), box_text, font=box_font, fill=theme["accent_text"])

    # 파트너스 고지 (필수)
    small = _font(24, 400)
    _draw_wrapped(draw, small, DISCLOSURE, _MARGIN, height - 158, max_w, theme["sub"], max_lines=2)

    _draw_dots(draw, img.size, theme, index, total)
    _draw_page_number(draw, img.size, theme, index, total)


def render_cards(
    copy_data: dict,
    out_dir: str | Path,
    theme_name: str = "딥 네이비",
    ratio: str = "1:1",
    handle: str = "",
    product_image: Image.Image | None = None,
) -> list[Path]:
    """카드 문구로 PNG 파일들을 렌더링해 경로 목록을 반환합니다."""
    theme = THEMES.get(theme_name) or THEMES["딥 네이비"]
    size = RATIOS.get(ratio) or RATIOS["1:1"]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cards = (
        [("cover", copy_data["cover"])]
        + [("feature", f) for f in copy_data["features"]]
        + [("cta", copy_data["cta"])]
    )
    total = len(cards)
    paths: list[Path] = []

    for i, (kind, data) in enumerate(cards):
        img = _gradient(size, theme["bg_top"], theme["bg_bottom"])
        if kind == "cover":
            _render_cover(img, theme, data, i, total, photo=product_image)
        elif kind == "feature":
            point_no = sum(1 for k, _ in cards[: i + 1] if k == "feature")
            _render_feature(img, theme, data, point_no, i, total)
        else:
            _render_cta(img, theme, data, i, total, photo=product_image)

        if handle:
            draw = ImageDraw.Draw(img)
            font = _font(30, 500)
            draw.text((_MARGIN, size[1] - 78), handle, font=font, fill=theme["sub"])

        path = out_dir / f"card_{i + 1}.png"
        img.save(path, "PNG")
        paths.append(path)

    return paths
