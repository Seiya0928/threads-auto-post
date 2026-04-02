"""
main.py — Threads スキンケア・美容自動投稿システム

使い方:
  python main.py --mode schedule      # 1日5〜8件、ランダム間隔で自動投稿（推奨）
  python main.py --mode generate      # スキンケア画像を生成して images/ へ保存
  python main.py --mode test          # 1件だけテスト投稿（ループなし）
  python main.py --mode schedule --dry-run  # スケジュールだけ確認（実際には投稿しない）
"""

import argparse
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / "config" / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

IMAGES_FOLDER = Path(__file__).parent / "images"


def cmd_generate(args):
    from src.image_generator import generate_batch, SKINCARE_PROMPTS
    count = getattr(args, "count", 3)
    prompts = SKINCARE_PROMPTS[:count]
    results = generate_batch(prompts, IMAGES_FOLDER)
    log.info(f"{len(results)}枚生成完了 → {IMAGES_FOLDER}")


def cmd_schedule(args):
    from src.scheduler import run_scheduler
    run_scheduler(dry_run=args.dry_run)


def cmd_test(args):
    """ループなしで1件だけテスト投稿する"""
    from src.threads_client import ThreadsClient
    from src.trend_fetcher import build_post_text

    token = os.environ.get("THREADS_ACCESS_TOKEN", "")
    if not token:
        log.error("THREADS_ACCESS_TOKEN が設定されていません")
        return

    client = ThreadsClient(token)

    # 認証確認
    log.info(f"認証確認: user_id={client.user_id}")

    # テキスト投稿
    text = build_post_text()
    log.info(f"投稿テキスト:\n{text}")

    if args.dry_run:
        log.info("[DRY RUN] 実際には投稿しません")
        return

    thread_id = client.post_text(text)
    log.info(f"投稿成功！ thread_id={thread_id}")


def main():
    parser = argparse.ArgumentParser(description="Threads スキンケア自動投稿システム")
    parser.add_argument(
        "--mode",
        choices=["schedule", "generate", "test"],
        default="schedule",
        help="実行モード",
    )
    parser.add_argument("--count", type=int, default=3, help="generate モードで生成する枚数")
    parser.add_argument("--dry-run", action="store_true", help="実際に投稿せずテスト実行")

    args = parser.parse_args()

    if args.mode == "generate":
        cmd_generate(args)
    elif args.mode == "schedule":
        cmd_schedule(args)
    elif args.mode == "test":
        cmd_test(args)


if __name__ == "__main__":
    main()
