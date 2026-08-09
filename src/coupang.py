"""쿠팡 파트너스 카드뉴스 생성 (명령줄).

사용 예시:
    python -m src.coupang --image capture.png            # 휴대폰 화면 캡처로 생성 (추천)
    python -m src.coupang --image capture.png --url "https://link.coupang.com/a/xxxxx"
    python -m src.coupang --url "https://link.coupang.com/a/xxxxx"
    python -m src.coupang --name "상품명" --price "29,900원"   # 정보 직접 지정

결과물은 output/coupang_YYYYmmdd_HHMMSS/ 에 저장됩니다.
  card_1.png ~ card_N.png  (인스타그램 게시물 이미지)
  caption.txt              (캡션 + 해시태그 + 파트너스 고지)
"""

import argparse
import datetime
import sys
from pathlib import Path

from . import card_generator, coupang_fetcher, screenshot_analyzer


def run(
    url: str = "",
    image: str = "",
    photo: str = "",
    cards: int = 4,
    theme: str = "딥 네이비",
    ratio: str = "1:1",
    handle: str = "",
    name: str = "",
    price: str = "",
    features: list[str] | None = None,
    out: str | None = None,
) -> tuple[list[Path], str]:
    """카드뉴스를 생성하고 (이미지 경로 목록, 캡션) 을 반환합니다."""
    product_photo = None
    if photo:
        product_photo = screenshot_analyzer.load_image(Path(photo).read_bytes())

    print("🔍 상품 정보 수집 중...")
    if image:
        product, cropped = screenshot_analyzer.analyze_screenshot(
            Path(image).read_bytes()
        )
        if product_photo is None:
            product_photo = cropped
        product["url"] = url
        if cropped is not None and not photo:
            print("   캡처에서 상품 사진 추출 완료")
    elif name:
        product = {"name": name, "price": price, "category": "", "url": url,
                   "features": features or [], "summary": ""}
    else:
        product = coupang_fetcher.fetch_product_info(url)

    # 직접 지정값이 있으면 우선 적용
    if name:
        product["name"] = name
    if price:
        product["price"] = price
    if features:
        product["features"] = features

    if not product.get("name"):
        raise RuntimeError(
            "상품 정보를 찾지 못했습니다. 캡처에 상품명이 잘 보이는지 확인하거나 "
            "--name (필요시 --price, --features) 옵션으로 직접 지정해 주세요."
        )
    print(f"   상품명: {product['name']}")
    if product.get("price"):
        print(f"   가격: {product['price']}")

    print(f"✍️  카드 문구 생성 중... ({cards}장)")
    copy_data = card_generator.generate_copy(product, n_cards=cards)

    out_dir = Path(out) if out else (
        Path("output") / f"coupang_{datetime.datetime.now():%Y%m%d_%H%M%S}"
    )
    print("🎨 카드 이미지 렌더링 중...")
    paths = card_generator.render_cards(copy_data, out_dir, theme_name=theme,
                                        ratio=ratio, handle=handle,
                                        product_image=product_photo)

    caption = card_generator.format_caption(copy_data, url=url)
    caption_path = out_dir / "caption.txt"
    caption_path.write_text(caption, encoding="utf-8")

    print(f"\n✅ 완료! {len(paths)}장 생성 → {out_dir}/")
    for p in paths:
        print(f"   {p}")
    print(f"   {caption_path}")
    print("\n--- 캡션 (복사해서 사용하세요) ---")
    print(caption)
    return paths, caption


def main() -> None:
    parser = argparse.ArgumentParser(description="쿠팡 파트너스 카드뉴스 생성")
    parser.add_argument("url", nargs="?", default="",
                        help="쿠팡 파트너스 URL (선택, --url 로도 지정 가능)")
    parser.add_argument("--url", dest="url_opt", default="",
                        help="쿠팡 파트너스 URL (캡션에 링크 포함용)")
    parser.add_argument("--image", default="",
                        help="쿠팡 화면 캡처 이미지 경로 (캡처에서 정보+상품사진 자동 추출)")
    parser.add_argument("--photo", default="",
                        help="카드에 넣을 상품 사진 경로 (자동 추출 대신 직접 지정)")
    parser.add_argument("--cards", type=int, choices=[3, 4], default=4, help="카드 장수 (기본 4)")
    parser.add_argument("--theme", choices=list(card_generator.THEMES), default="딥 네이비",
                        help="카드 색상 테마")
    parser.add_argument("--ratio", choices=list(card_generator.RATIOS), default="1:1",
                        help="이미지 비율 (1:1 정사각형 / 4:5 세로형)")
    parser.add_argument("--handle", default="", help="카드에 표시할 인스타 핸들 (예: @my_shop)")
    parser.add_argument("--name", default="", help="상품명 직접 지정 (자동 수집 생략)")
    parser.add_argument("--price", default="", help="가격 직접 지정 (예: 29,900원)")
    parser.add_argument("--features", default="", help="특징 직접 지정 (쉼표로 구분)")
    parser.add_argument("--out", default=None, help="저장 폴더 (기본: output/coupang_날짜시간)")
    args = parser.parse_args()

    features = [f.strip() for f in args.features.split(",") if f.strip()]
    url = args.url or args.url_opt
    if not (url or args.image or args.name):
        parser.error("--image (화면 캡처), URL, --name 중 하나는 필요합니다.")
    try:
        run(url=url, image=args.image, photo=args.photo,
            cards=args.cards, theme=args.theme, ratio=args.ratio,
            handle=args.handle, name=args.name, price=args.price,
            features=features, out=args.out)
    except Exception as exc:  # noqa: BLE001 - 최상위에서 사용자 친화적 메시지로 종료
        print(f"\n❌ 오류: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
