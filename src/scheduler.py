"""
scheduler.py — 1日5〜8件、60〜180分ランダム間隔で Threads に自動投稿するスケジューラー

動作:
  - 毎朝、その日の投稿時刻リストをランダム生成
  - 各時刻になったら投稿（画像あり → Imgur 経由、なし → テキストのみ）
  - 日付が変わると翌日分を自動再生成
"""

import os
import logging
import time
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "config" / ".env")

log = logging.getLogger(__name__)

# 投稿可能な時間帯（時）
POSTING_START_HOUR = 8
POSTING_END_HOUR = 23

# 1日の投稿件数
MIN_POSTS_PER_DAY = 5
MAX_POSTS_PER_DAY = 8

# 投稿間隔（分）
MIN_INTERVAL_MIN = 60
MAX_INTERVAL_MIN = 180


def generate_schedule(
    post_count: int,
    start_hour: int = POSTING_START_HOUR,
    end_hour: int = POSTING_END_HOUR,
    min_interval: int = MIN_INTERVAL_MIN,
    max_interval: int = MAX_INTERVAL_MIN,
) -> List[datetime]:
    """
    今日の投稿時刻リストをランダム生成して返す。

    start_hour 以降から始めて、min〜max 分のランダム間隔を積み上げる。
    end_hour を超えた分はカットして返す。
    """
    today = date.today()
    # 開始時刻: 今日の start_hour 〜 start_hour+30分 のランダム
    start_dt = datetime(today.year, today.month, today.day, start_hour, random.randint(0, 30))
    end_dt = datetime(today.year, today.month, today.day, end_hour, 0)

    schedule: List[datetime] = []
    current = start_dt

    for _ in range(post_count):
        if current >= end_dt:
            break
        schedule.append(current)
        interval = random.randint(min_interval, max_interval)
        current += timedelta(minutes=interval)

    return schedule


def seconds_until(dt: datetime) -> float:
    return max(0.0, (dt - datetime.now()).total_seconds())


def do_post(dry_run: bool = False) -> None:
    """1回分の投稿処理（画像あり優先、なければテキスト）"""
    from src.threads_client import ThreadsClient
    from src.imgur_uploader import upload_image
    from src.trend_fetcher import build_post_text
    from src.poster import get_pending_images, mark_as_posted

    images_folder = Path(os.environ.get("IMAGES_FOLDER", "./images"))
    images_folder.mkdir(parents=True, exist_ok=True)

    access_token = os.environ["THREADS_ACCESS_TOKEN"]
    imgur_client_id = os.environ.get("IMGUR_CLIENT_ID", "")
    client = ThreadsClient(access_token)

    text = build_post_text(os.environ.get("DEFAULT_HASHTAGS", ""))
    pending = get_pending_images(images_folder)

    if dry_run:
        log.info(f"[DRY RUN] テキスト: {text[:60]}...")
        if pending:
            log.info(f"[DRY RUN] 画像: {pending[0].name}")
        return

    try:
        if pending and imgur_client_id:
            image = pending[0]
            image_url = upload_image(image, imgur_client_id)
            thread_id = client.post_image(image_url, text)
            mark_as_posted(images_folder, image.name)
            log.info(f"画像付き投稿完了: thread_id={thread_id} / {image.name}")
        else:
            if pending and not imgur_client_id:
                log.warning("IMGUR_CLIENT_ID 未設定 → テキストのみ投稿")
            thread_id = client.post_text(text)
            log.info(f"テキスト投稿完了: thread_id={thread_id}")
    except Exception as e:
        log.error(f"投稿失敗: {e}")


def run_scheduler(dry_run: bool = False) -> None:
    """
    メインスケジューラーループ。
    毎日の投稿スケジュールを生成し、時刻が来たら投稿する。
    """
    log.info("スケジューラー起動")
    today = None
    schedule: List[datetime] = []
    post_index = 0

    while True:
        now = datetime.now()

        # 日付が変わったら当日スケジュールを再生成
        if today != now.date():
            today = now.date()
            post_count = random.randint(MIN_POSTS_PER_DAY, MAX_POSTS_PER_DAY)
            schedule = generate_schedule(post_count)
            post_index = 0

            # 現在時刻より過去のスロットはスキップ
            while post_index < len(schedule) and schedule[post_index] <= now:
                log.info(f"起動時刻が過ぎているスロットをスキップ: {schedule[post_index].strftime('%H:%M')}")
                post_index += 1

            log.info(
                f"【{today}】今日の投稿スケジュール ({post_count}件):\n"
                + "\n".join(f"  {i+1}. {dt.strftime('%H:%M')}" for i, dt in enumerate(schedule))
            )

        # 全スロット完了 → 翌日まで待機
        if post_index >= len(schedule):
            tomorrow = datetime(today.year, today.month, today.day) + timedelta(days=1)
            wait_sec = seconds_until(tomorrow)
            log.info(f"本日の投稿完了（{len(schedule)}件）。翌日 00:00 まで待機...")
            time.sleep(wait_sec)
            continue

        next_dt = schedule[post_index]
        wait_sec = seconds_until(next_dt)

        if wait_sec > 0:
            log.info(f"次の投稿: {next_dt.strftime('%H:%M')} （あと {int(wait_sec // 60)}分）")
            time.sleep(min(wait_sec, 60))  # 60秒ごとに起き直して時刻を再チェック
            continue

        # 投稿実行
        log.info(f"--- 投稿 {post_index + 1}/{len(schedule)} ({next_dt.strftime('%H:%M')}) ---")
        do_post(dry_run=dry_run)
        post_index += 1
