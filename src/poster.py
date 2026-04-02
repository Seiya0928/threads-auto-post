"""
poster.py — 画像フォルダから Threads に投稿するメインモジュール
投稿間隔をランダム化してAPI制限を回避する
"""

import os
import random
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

_env_file = Path(__file__).parent.parent / "config" / ".env"
if _env_file.exists():
    load_dotenv(_env_file)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(Path(__file__).parent.parent / "logs" / "poster.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def get_pending_images(folder: Path) -> list:
    """フォルダ内の未投稿画像を取得（古い順）"""
    posted_log = folder / ".posted"
    posted = set()
    if posted_log.exists():
        posted = set(posted_log.read_text().splitlines())

    images = sorted(
        [p for p in folder.iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS],
        key=lambda p: p.stat().st_mtime,
    )
    return [img for img in images if img.name not in posted]


def mark_as_posted(folder: Path, image_name: str) -> None:
    posted_log = folder / ".posted"
    with posted_log.open("a") as f:
        f.write(image_name + "\n")


def random_interval_seconds(min_minutes: int, max_minutes: int) -> int:
    return random.randint(min_minutes * 60, max_minutes * 60)


def run_poster(
    images_folder: Optional[str] = None,
    tweet_text: Optional[str] = None,
    min_interval: Optional[int] = None,
    max_interval: Optional[int] = None,
    dry_run: bool = False,
) -> None:
    """
    指定フォルダの画像を順番に Threads へ投稿するメインループ。

    画像がある場合 → Imgur にアップロードして画像付き投稿
    画像がない場合 → テキストのみ投稿
    """
    from src.threads_client import ThreadsClient
    from src.imgur_uploader import upload_image

    folder = Path(images_folder or os.environ.get("IMAGES_FOLDER", "./images"))
    folder.mkdir(parents=True, exist_ok=True)

    hashtags = os.environ.get("DEFAULT_HASHTAGS", "#スキンケア #美容 #skincare")
    text = tweet_text or hashtags
    min_m = min_interval or int(os.environ.get("POST_MIN_INTERVAL", 60))
    max_m = max_interval or int(os.environ.get("POST_MAX_INTERVAL", 180))

    access_token = os.environ["THREADS_ACCESS_TOKEN"]
    imgur_client_id = os.environ.get("IMGUR_CLIENT_ID", "")

    client = ThreadsClient(access_token)
    log.info(f"起動: フォルダ={folder}, 間隔={min_m}〜{max_m}分, dry_run={dry_run}")

    while True:
        pending = get_pending_images(folder)

        if not pending:
            log.info("投稿待ち画像なし。テキストのみ投稿します。")
            if not dry_run:
                thread_id = client.post_text(text)
                log.info(f"テキスト投稿完了: {thread_id}")
        else:
            image = pending[0]
            log.info(f"投稿準備: {image.name}")

            if dry_run:
                log.info(f"[DRY RUN] スキップ: {image.name}")
            else:
                try:
                    if imgur_client_id:
                        image_url = upload_image(image, imgur_client_id)
                        thread_id = client.post_image(image_url, text)
                    else:
                        log.warning("IMGUR_CLIENT_ID 未設定 → テキストのみ投稿")
                        thread_id = client.post_text(text)

                    mark_as_posted(folder, image.name)
                    log.info(f"投稿完了: thread_id={thread_id}")
                except Exception as e:
                    log.error(f"投稿失敗: {e}")

        wait_sec = random_interval_seconds(min_m, max_m)
        next_time = datetime.fromtimestamp(time.time() + wait_sec).strftime("%H:%M:%S")
        log.info(f"次の投稿は {wait_sec // 60}分{wait_sec % 60}秒後 ({next_time})")
        time.sleep(wait_sec)


if __name__ == "__main__":
    run_poster(dry_run=False)
