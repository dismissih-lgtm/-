"""매일 한국 시간(KST) 정해진 시각에 뉴스 게시물을 자동 생성합니다.

실행:
    python -m src.scheduler                # 매일 KST 06:00 에 실행
    python -m src.scheduler --hour 7       # 시각 변경
    python -m src.scheduler --dry-run      # 업로드 없이 테스트

이 스크립트는 계속 떠 있어야 동작합니다(서버/PC에서 nohup, systemd, screen 등).
서버 자체가 자주 꺼진다면 README의 cron 방식을 권장합니다.
"""

import argparse
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import main

# 한국 시간 (UTC+9, 서머타임 없음)
KST = ZoneInfo("Asia/Seoul")


def _seconds_until(hour: int, minute: int = 0) -> float:
    """다음 KST hour:minute 까지 남은 초를 계산합니다."""
    now = datetime.now(KST)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def run_forever(hour: int = 6, minute: int = 0, dry_run: bool = False) -> None:
    print(
        f"⏰ 매일 한국 시간 {hour:02d}:{minute:02d} 에 "
        f"뉴스 게시물을 자동 생성합니다. (Ctrl+C 로 종료)"
    )
    while True:
        wait = _seconds_until(hour, minute)
        next_run = datetime.now(KST) + timedelta(seconds=wait)
        print(f"   다음 실행: {next_run:%Y-%m-%d %H:%M} KST ({wait / 3600:.1f}시간 후)")
        time.sleep(wait)

        print(f"\n🔔 {datetime.now(KST):%Y-%m-%d %H:%M} KST — 실행 시작")
        try:
            main.run_news(dry_run=dry_run)
        except Exception as exc:  # noqa: BLE001 - 한 번 실패해도 스케줄러는 계속 동작
            print(f"❌ 실행 중 오류 (다음 날 다시 시도): {exc}")

        time.sleep(60)  # 같은 분에 중복 실행되는 것 방지


def main_cli() -> None:
    parser = argparse.ArgumentParser(description="뉴스 게시물 정기 스케줄러")
    parser.add_argument("--hour", type=int, default=6, help="실행 시각(시, KST). 기본 6")
    parser.add_argument("--minute", type=int, default=0, help="실행 시각(분). 기본 0")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="업로드 없이 이미지·캡션만 생성",
    )
    args = parser.parse_args()
    run_forever(hour=args.hour, minute=args.minute, dry_run=args.dry_run)


if __name__ == "__main__":
    main_cli()
