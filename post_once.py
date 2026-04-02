"""
post_once.py — GitHub Actions から呼び出す1回限りの投稿スクリプト

環境変数から認証情報を読み込み、Threads にテキストを1件投稿して終了する。
.env ファイルは不要（GitHub Secrets が直接 env に注入される）。
"""

import os
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def main():
    token = os.environ.get("THREADS_ACCESS_TOKEN", "")
    if not token:
        log.error("THREADS_ACCESS_TOKEN が設定されていません")
        sys.exit(1)

    # src/ をパスに追加
    sys.path.insert(0, os.path.dirname(__file__))

    from src.threads_client import ThreadsClient
    from src.trend_fetcher import build_post_text

    client = ThreadsClient(token)

    # 認証確認
    try:
        uid = client.user_id
        log.info(f"認証OK: user_id={uid}")
    except Exception as e:
        log.error(f"認証失敗: {e}")
        sys.exit(1)

    # 投稿テキスト生成（時間帯・曜日に合わせたスキンケアコンテンツ）
    hashtags = os.environ.get("DEFAULT_HASHTAGS", "#スキンケア #美容 #skincare")
    text = build_post_text(hashtags)
    log.info(f"投稿テキスト:\n{text}")

    # 投稿
    try:
        thread_id = client.post_text(text)
        log.info(f"投稿成功: thread_id={thread_id}")
    except Exception as e:
        log.error(f"投稿失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
