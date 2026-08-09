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
                   w: int, h: int, radius: int = 28, fit: str = "cover",
                   bg: tuple = (255, 255, 255)) -> None:
    """둥근 모서리로 사진을 붙입니다.

    fit="cover"  : 프레임을 사진으로 꽉 채움 (사진 가장자리가 잘릴 수 있음)
    fit="contain": 흰 배경 위에 사진 전체가 보이게 넣음 (상품 사진에 적합)
    """
    if fit == "cover":
        fitted = _fit_image(photo.convert("RGB"), w, h)
    else:
        panel = Image.new("RGB", (w, h), bg)
        scale = min(w / photo.width, h / photo.height)
        nw = max(1, int(photo.width * scale))
        nh = max(1, int(photo.height * scale))
        resized = photo.convert("RGB").resize((nw, nh), Image.LANCZOS)
        panel.paste(resized, ((w - nw) // 2, (h - nh) // 2))
        fitted = panel
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
        # 프레임 폭은 사진 비율에 맞춰 조절 (세로형 사진도 잘리지 않게)
        aspect = photo.width / photo.height
        frame_w = min(max_w, max(int(photo_h * aspect), int(photo_h * 0.85)))
        _paste_rounded(img, photo, (width - frame_w) // 2, badge_bottom + 34,
                       frame_w, photo_h, fit="contain")
        draw = ImageDraw.Draw(img)  # paste 이후 다시 획득

        y = badge_bottom + 34 + photo_h + 46
        max_lines = 2 if height <= 1100 else 3
        y = _draw_wrapped(draw, _font(58, 800), cover["headline"], _MARGIN, y, max_w,
                          theme["text"], line_gap=1.22, max_lines=max_lines)
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
        # 정사각 상품 사진을 상단 중앙에 배치 (전체가 보이게)
        ph = int(height * 0.26)
        _paste_rounded(img, photo, (width - ph) // 2, int(height * 0.09), ph, ph,
                       fit="contain")
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


# ─────────────────────────────────────────────────────
# 4. 프로모 스타일 렌더링 (밝은 배경 + 상품 크게 + 링크번호 푸터)
# ─────────────────────────────────────────────────────

_PROMO = {
    "bg_top": (253, 251, 255), "bg_bottom": (225, 216, 244),
    "red": (222, 32, 44), "purple": (86, 48, 166), "purple_deep": (58, 36, 120),
    "text": (45, 35, 75), "sub": (108, 96, 150),
    "yellow": (255, 209, 59), "ring": (156, 124, 212),
    "footer_bg": (50, 32, 108), "footer_sub": (196, 184, 232),
    "banner_bg": (94, 53, 177),
}

# 쿠팡 파트너스 고지 (프로모 카드 푸터용 — 예시 이미지와 동일한 문구)
PROMO_DISCLOSURE = "쿠팡 파트너스 활동의 일환으로 일정액의 수수료를 제공받을 수 있습니다."


def _promo_bg(size: tuple[int, int]) -> Image.Image:
    """밝은 라벤더 그라데이션 + 반투명 버블 배경."""
    img = _gradient(size, _PROMO["bg_top"], _PROMO["bg_bottom"]).convert("RGBA")
    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    w, h = size
    bubbles = [
        (int(w * 0.06), int(h * 0.55), 46, 26), (int(w * 0.93), int(h * 0.40), 34, 30),
        (int(w * 0.88), int(h * 0.72), 56, 22), (int(w * 0.12), int(h * 0.80), 30, 30),
        (int(w * 0.55), int(h * 0.30), 22, 18), (int(w * 0.97), int(h * 0.58), 26, 26),
    ]
    for cx, cy, r, alpha in bubbles:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(150, 110, 220, alpha))
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(150, 110, 220, alpha + 25), width=3)
    return Image.alpha_composite(img, overlay)


def _draw_sparkle(draw, cx, cy, r, color):
    """4갈래 반짝이 모양."""
    draw.polygon(
        [(cx, cy - r), (cx + r * 0.28, cy - r * 0.28), (cx + r, cy),
         (cx + r * 0.28, cy + r * 0.28), (cx, cy + r), (cx - r * 0.28, cy + r * 0.28),
         (cx - r, cy), (cx - r * 0.28, cy - r * 0.28)],
        fill=color,
    )


def _draw_segments_centered(draw, segments, fonts_colors, y, width):
    """여러 색 텍스트 조각을 가운데 정렬로 한 줄에 그립니다."""
    total = sum(f.getlength(t) for (t, _), f in zip(segments, fonts_colors))
    x = (width - total) / 2
    for (text, color), font in zip(segments, fonts_colors):
        draw.text((x, y), text, font=font, fill=color)
        x += font.getlength(text)


def _promo_two_color_title(draw, title_parts, y, width, max_width, base_size=104):
    """빨강+보라 두 색 큰 제목. 길면 폰트를 줄입니다."""
    size = base_size
    while size > 56:
        font = _font(size, 900)
        total = sum(font.getlength(t) for t, _ in title_parts)
        if total <= max_width:
            break
        size -= 6
    font = _font(size, 900)
    colors = {"red": _PROMO["red"], "purple": _PROMO["purple"]}
    segs = [(t, colors.get(c, _PROMO["purple"])) for t, c in title_parts]
    _draw_segments_centered(draw, segs, [font] * len(segs), y, width)
    return y + int(size * 1.18)


def _promo_footer(img, link_no: str):
    """하단: 검색 안내 바 + 쿠팡 파트너스 고지."""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    bar_h = 150
    draw.rectangle([0, h - bar_h, w, h], fill=_PROMO["footer_bg"])

    # 돋보기 아이콘
    f_main = _font(44, 800)
    text_parts = [("프로필 링크에서 ", (255, 255, 255)),
                  (f"{link_no}번", _PROMO["yellow"]),
                  ("을 검색하세요", (255, 255, 255))]
    total = sum(f_main.getlength(t) for t, _ in text_parts)
    icon_r = 20
    start_x = (w - total - 64) / 2 + 64
    icon_cx = start_x - 46
    icon_cy = h - bar_h + 56
    draw.ellipse([icon_cx - icon_r, icon_cy - icon_r, icon_cx + icon_r, icon_cy + icon_r],
                 outline=(255, 255, 255), width=6)
    draw.line([icon_cx + icon_r * 0.7, icon_cy + icon_r * 0.7,
               icon_cx + icon_r * 1.5, icon_cy + icon_r * 1.5], fill=(255, 255, 255), width=6)

    x = start_x
    y = h - bar_h + 32
    for text, color in text_parts:
        draw.text((x, y), text, font=f_main, fill=color)
        x += f_main.getlength(text)

    f_small = _font(23, 400)
    tw = f_small.getlength(PROMO_DISCLOSURE)
    draw.text(((w - tw) / 2, h - 44), PROMO_DISCLOSURE, font=f_small, fill=_PROMO["footer_sub"])


def _fit_font(text: str, size: int, weight: int, max_width: float) -> ImageFont.FreeTypeFont:
    """max_width 에 들어갈 때까지 폰트 크기를 줄입니다."""
    while size > 18:
        font = _font(size, weight)
        if font.getlength(text) <= max_width:
            return font
        size -= 2
    return _font(size, weight)


def _promo_circle(img, cx, cy, r, line1, line2):
    """흰 원 + 보라 테두리 + 2줄 텍스트 특징 뱃지."""
    draw = ImageDraw.Draw(img)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255),
                 outline=_PROMO["ring"], width=5)
    _draw_sparkle(draw, cx + r * 0.62, cy - r * 0.72, 12, _PROMO["ring"])
    max_w = r * 2 - 36
    f1 = _fit_font(line1, 27, 500, max_w)
    f2 = _fit_font(line2, 32, 800, max_w)
    w1, w2 = f1.getlength(line1), f2.getlength(line2)
    draw.text((cx - w1 / 2, cy - 38), line1, font=f1, fill=_PROMO["sub"])
    draw.text((cx - w2 / 2, cy + 2), line2, font=f2, fill=_PROMO["purple_deep"])


def render_promo_cards(
    cards: list[dict],
    out_dir: str | Path,
    product_image: Image.Image,
    link_no: str,
    ratio: str = "1:1",
) -> list[Path]:
    """프로모(밝은) 스타일 카드 렌더링.

    cards 항목 형식:
      {"kicker": str,                       # 상단 작은 문구
       "title": [(text, "red"|"purple"), ...],  # 두 색 큰 제목
       "banner": str,                       # 보라 배너 문구
       "circles": [(줄1, 줄2) x 3],          # 왼쪽 원형 특징 뱃지 (표지형)
       "rows": [str, ...],                  # 왼쪽 체크 리스트 (후기/정보형, circles 대신)
       "tag": str}                          # 사진 위 노란 스티커 (선택)

    모든 카드에 '광고' 표시 + "프로필 링크에서 N번을 검색하세요" + 파트너스 고지가
    자동으로 들어갑니다. 카드 1장씩 만들려면 cards 에 dict 하나만 넣으면 됩니다.
    """
    size = RATIOS.get(ratio) or RATIOS["1:1"]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    width, height = size
    paths: list[Path] = []

    for i, card in enumerate(cards):
        img = _promo_bg(size)
        draw = ImageDraw.Draw(img)

        # '광고' 표시 (오른쪽 위)
        f_ad = _font(26, 700)
        ad_w = f_ad.getlength("광고") + 36
        draw.rounded_rectangle([width - 56 - ad_w, 42, width - 56, 90], radius=12,
                               outline=_PROMO["sub"], width=3)
        draw.text((width - 56 - ad_w + 18, 50), "광고", font=f_ad, fill=_PROMO["sub"])

        # 상단 킥커 + 반짝이
        f_kicker = _font(40, 700)
        kw = f_kicker.getlength(card["kicker"])
        draw.text(((width - kw) / 2, 46), card["kicker"], font=f_kicker, fill=_PROMO["text"])
        _draw_sparkle(draw, (width - kw) / 2 - 44, 70, 14, _PROMO["ring"])

        # 두 색 큰 제목
        y = _promo_two_color_title(draw, card["title"], 108, width, width - 160)

        # 보라 배너
        f_banner = _font(38, 700)
        bw = f_banner.getlength(card["banner"]) + 100
        bx = (width - bw) / 2
        by = y + 12
        draw.rounded_rectangle([bx, by, bx + bw, by + 74], radius=37, fill=_PROMO["banner_bg"])
        draw.text((bx + 50, by + 15), card["banner"], font=f_banner, fill=(255, 255, 255))

        # 중앙 영역: 상품 사진 패널 + (원형 뱃지 3개 또는 체크 리스트)
        top = by + 74 + 36
        bottom = height - 150 - 30
        panel_h = bottom - top
        rows = card.get("rows")

        if rows:
            # 리스트형 (후기/제품정보 카드): 왼쪽 체크 리스트 + 오른쪽 사진
            list_w = int(width * 0.52)
            panel_w = width - list_w - 64 * 2 - 24
            px = width - 64 - panel_w
        else:
            panel_w = min(int(width * 0.52), panel_h)
            px = width - panel_w - 64

        draw.rounded_rectangle([px, top, px + panel_w, top + panel_h], radius=34,
                               fill=(255, 255, 255), outline=(214, 202, 240), width=3)
        _paste_rounded(img, product_image, px + 14, top + 14, panel_w - 28, panel_h - 28,
                       radius=26, fit="contain")
        draw = ImageDraw.Draw(img)

        if rows:
            lx = 64
            draw.rounded_rectangle([lx, top, lx + list_w, top + panel_h], radius=34,
                                   fill=(255, 255, 255), outline=(214, 202, 240), width=3)
            check_theme = {"accent": _PROMO["banner_bg"], "accent_text": (255, 255, 255)}
            f_row = _font(34, 600)
            fy = top + 44
            for row in rows[:5]:
                _draw_check(draw, check_theme, lx + 54, fy + int(f_row.size * 0.62), r=19)
                fy = _draw_wrapped(draw, f_row, row, lx + 96, fy, list_w - 136,
                                   _PROMO["text"], max_lines=2) + 20
        else:
            # 왼쪽 원형 특징 뱃지 3개
            r = min(102, panel_h // 6)
            cx = 64 + int(width * 0.19)
            circles = card.get("circles", [])
            gap = (panel_h - r * 2) // 2 if len(circles) > 1 else 0
            for j, (l1, l2) in enumerate(circles[:3]):
                cy = top + r + j * max(gap, int(r * 2.2))
                _promo_circle(img, cx, cy, r, l1, l2)
            draw = ImageDraw.Draw(img)

        # 노란 스티커 (사진 오른쪽 아래)
        if card.get("tag"):
            f_tag = _font(34, 800)
            tw = f_tag.getlength(card["tag"]) + 76
            tx = px + panel_w - tw + 20
            ty = top + panel_h - 46
            draw.rounded_rectangle([tx, ty, tx + tw, ty + 78], radius=24,
                                   fill=_PROMO["yellow"],
                                   outline=(255, 255, 255), width=4)
            draw.text((tx + 38, ty + 17), card["tag"], font=f_tag, fill=_PROMO["purple_deep"])

        _promo_footer(img, link_no)

        path = out_dir / f"card_{i + 1}.png"
        img.convert("RGB").save(path, "PNG")
        paths.append(path)

    return paths


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
