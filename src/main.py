"""게시물 자동 생성·업로드 파이프라인.

사용 예시:
    # 주제를 직접 입력
    python -m src.main "가을 감성 카페 신메뉴 홍보"

    # 오늘의 뉴스를 검색해서 게시물 생성
    python -m src.main --news

    # 업로드 없이 이미지·캡션만 미리보기
    python -m src.main --news --dry-run
"""

import argparse
import sys

from . import caption_generator, image_generator, instagram_publisher, news_fetcher


def run(topic: str, dry_run: bool = False, image_topic: str | None = None) -> None:
    """topic(캡션 재료)과 image_topic(이미지 프롬프트)으로 한 건을 게시합니다.

    image_topic 을 따로 주지 않으면 topic 을 이미지에도 사용합니다.
    """
    image_topic = image_topic or topic

    print("🎨 이미지 생성 중...")
    image_url = image_generator.generate_image(image_topic)
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


def run_news(dry_run: bool = False) -> None:
    """오늘의 뉴스를 검색해 게시물을 만듭니다."""
    print("📰 오늘의 뉴스 검색 중...")
    news = news_fetcher.fetch_top_news()
    headline = news["headline"]
    summary = news["summary"]
    print(f"   헤드라인: {headline}")
    print(f"   요약: {summary}\n")

    # 이미지는 짧은 헤드라인으로, 캡션은 풍부한 요약으로 생성
    run(topic=summary, dry_run=dry_run, image_topic=headline)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="인스타그램 게시물 자동 생성·업로드"
    )
    parser.add_argument(
        "topic",
        nargs="?",
        help="게시물 주제 (생략하고 --news 를 쓰면 오늘의 뉴스로 생성)",
    )
    parser.add_argument(
        "--news",
        action="store_true",
        help="오늘의 뉴스를 검색해 게시물 생성",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="이미지와 캡션만 생성하고 업로드는 하지 않음",
    )
    args = parser.parse_args()

    try:
        if args.news:
            run_news(dry_run=args.dry_run)
        elif args.topic:
            run(args.topic, dry_run=args.dry_run)
        else:
            parser.error("주제를 입력하거나 --news 옵션을 사용하세요.")
    except Exception as exc:  # noqa: BLE001 - 최상위에서 사용자 친화적 메시지로 종료
        print(f"\n❌ 오류: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
