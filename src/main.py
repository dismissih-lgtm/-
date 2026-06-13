"""주제 하나로 이미지 생성 → 캡션 생성 → 인스타그램 업로드까지 한 번에 실행.

사용 예시:
    python -m src.main "가을 감성 카페 신메뉴 홍보"
    python -m src.main "주말 등산 모임 후기" --dry-run
"""

import argparse
import sys

from . import caption_generator, image_generator, instagram_publisher


def run(topic: str, dry_run: bool = False) -> None:
    print(f"📝 주제: {topic}\n")

    print("🎨 이미지 생성 중...")
    image_url = image_generator.generate_image(topic)
    print(f"   완료: {image_url}\n")

    print("✍️  캡션/해시태그 생성 중...")
    caption_data = caption_generator.generate_caption(topic)
    full_caption = caption_generator.format_full_caption(caption_data)
    print(f"   완료:\n{full_caption}\n")

    if dry_run:
        print("🚧 --dry-run 모드: 실제 업로드는 건너뜁니다.")
        return

    print("📤 인스타그램 업로드 중...")
    post_id = instagram_publisher.publish_photo(image_url, full_caption)
    print(f"✅ 업로드 완료! 게시물 ID: {post_id}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="인스타그램 게시물 자동 생성·업로드"
    )
    parser.add_argument("topic", help="게시물 주제")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="이미지와 캡션만 생성하고 업로드는 하지 않음",
    )
    args = parser.parse_args()

    try:
        run(args.topic, dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001 - 최상위에서 사용자 친화적 메시지로 종료
        print(f"\n❌ 오류: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
