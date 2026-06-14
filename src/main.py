"""게시물 자동 생성 파이프라인.

전송 대상(destination):
  - kakao     : 카카오톡 '나에게 보내기'로 전송 (받아서 직접 인스타에 게시)
  - instagram : 인스타그램 Graph API로 바로 업로드

사용 예시:
    python -m src.main --news                 # 오늘의 뉴스 → 설정된 대상으로
    python -m src.main --news --to kakao      # 카카오톡으로 받기
    python -m src.main "카페 신메뉴" --to instagram
    python -m src.main --news --dry-run       # 생성만, 전송 안 함
"""

import argparse
import sys

from . import (
    caption_generator,
    image_generator,
    instagram_publisher,
    kakao_sender,
    news_fetcher,
    settings,
)


def _generate(image_topic: str, caption_topic: str) -> tuple[str, str]:
    """이미지 URL과 완성된 캡션을 만들어 반환합니다."""
    print("🎨 이미지 생성 중...")
    image_url = image_generator.generate_image(image_topic)
    print(f"   완료: {image_url}\n")

    print("✍️  캡션/해시태그 생성 중...")
    data = caption_generator.generate_caption(caption_topic)
    full_caption = caption_generator.format_full_caption(data)
    print(f"   완료:\n{full_caption}\n")
    return image_url, full_caption


def _deliver(destination: str, image_url: str, headline: str, caption: str) -> None:
    if destination == "kakao":
        print("💬 카카오톡으로 전송 중...")
        kakao_sender.send_post(image_url, headline, caption)
        print("✅ 카카오톡으로 전송 완료! (받은 이미지·캡션으로 인스타에 올리세요)")
    else:
        print("📤 인스타그램 업로드 중...")
        post_id = instagram_publisher.publish_photo(image_url, caption)
        print(f"✅ 업로드 완료! 게시물 ID: {post_id}")


def run(
    topic: str,
    dry_run: bool = False,
    image_topic: str | None = None,
    destination: str = "instagram",
) -> None:
    """topic(캡션 재료)으로 한 건을 생성하고 destination 으로 전송합니다."""
    image_topic = image_topic or topic
    image_url, full_caption = _generate(image_topic, topic)

    if dry_run:
        print("🚧 --dry-run 모드: 전송은 건너뜁니다.")
        return

    _deliver(destination, image_url, image_topic, full_caption)


def run_news(dry_run: bool = False, destination: str | None = None) -> None:
    """오늘의 뉴스를 검색해 게시물을 만들고 전송합니다."""
    destination = destination or settings.load().get("destination", "kakao")

    print("📰 오늘의 뉴스 검색 중...")
    news = news_fetcher.fetch_top_news()
    headline, summary = news["headline"], news["summary"]
    print(f"   헤드라인: {headline}")
    print(f"   요약: {summary}\n")

    run(topic=summary, dry_run=dry_run, image_topic=headline, destination=destination)


def main() -> None:
    parser = argparse.ArgumentParser(description="게시물 자동 생성·전송")
    parser.add_argument(
        "topic",
        nargs="?",
        help="게시물 주제 (생략하고 --news 를 쓰면 오늘의 뉴스로 생성)",
    )
    parser.add_argument(
        "--news", action="store_true", help="오늘의 뉴스를 검색해 게시물 생성"
    )
    parser.add_argument(
        "--to",
        choices=["kakao", "instagram"],
        help="전송 대상 (생략 시 설정값 사용; --news 기본 kakao)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="생성만 하고 전송하지 않음"
    )
    args = parser.parse_args()

    destination = args.to or settings.load().get("destination", "kakao")

    try:
        if args.news:
            run_news(dry_run=args.dry_run, destination=destination)
        elif args.topic:
            run(args.topic, dry_run=args.dry_run, destination=destination)
        else:
            parser.error("주제를 입력하거나 --news 옵션을 사용하세요.")
    except Exception as exc:  # noqa: BLE001 - 최상위에서 사용자 친화적 메시지로 종료
        print(f"\n❌ 오류: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
