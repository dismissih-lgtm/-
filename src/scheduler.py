"""매일 한국 시간(KST)에 뉴스 게시물을 자동 생성합니다.

실행 시각과 켜짐/꺼짐은 settings.json 에서 읽습니다.
(웹 UI의 "자동 게시 설정" 탭에서 바꿀 수 있습니다.)

실행:
    python -m src.scheduler            # settings.json 의 시각에 매일 실행
    python -m src.scheduler --dry-run  # 업로드 없이 테스트

이 스크립트는 계속 떠 있어야 동작합니다(서버/PC에서 nohup, systemd 등).
컴퓨터를 켜둘 수 없다면 README의 GitHub Actions 방식을 권장합니다.
"""

import argparse
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import main, settings

# 한국 시간 (UTC+9, 서머타임 없음)
KST = ZoneInfo("Asia/Seoul")


def _seconds_until(hour: int, minute: int = 0) -> float:
    """다음 KST hour:minute 까지 남은 초를 계산합니다."""
    now = datetime.now(KST)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def run_forever(dry_run: bool = False) -> None:
    print("⏰ 자동 게시 스케줄러 시작 (Ctrl+C 로 종료)")
    while True:
        cfg = settings.load()
        hour = int(cfg["schedule_hour"])
        minute = int(cfg["schedule_minute"])

        wait = _seconds_until(hour, minute)
        next_run = datetime.now(KST) + timedelta(seconds=wait)
        state = "켜짐" if cfg["schedule_enabled"] else "꺼짐(건너뜀)"
        print(
            f"   다음 예정: {next_run:%Y-%m-%d %H:%M} KST "
            f"({wait / 3600:.1f}시간 후) · 자동 게시 {state}"
        )
        time.sleep(wait)

        # 깨어난 시점에 다시 설정을 읽어, 꺼져 있으면 건너뜀
        if settings.load()["schedule_enabled"]:
            print(f"\n🔔 {datetime.now(KST):%Y-%m-%d %H:%M} KST — 실행 시작")
            try:
                main.run_news(dry_run=dry_run)
            except Exception as exc:  # noqa: BLE001 - 한 번 실패해도 계속 동작
                print(f"❌ 실행 중 오류 (내일 다시 시도): {exc}")

        time.sleep(60)  # 같은 분에 중복 실행 방지


def main_cli() -> None:
    parser = argparse.ArgumentParser(description="뉴스 게시물 정기 스케줄러")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="업로드 없이 이미지·캡션만 생성",
    )
    args = parser.parse_args()
    run_forever(dry_run=args.dry_run)


if __name__ == "__main__":
    main_cli()
