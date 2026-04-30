"""
main_rakuten.py — 楽天アフィリエイト用 Threads 投稿レーン

初期安全設計:
  - DRY_RUN=true がデフォルト
  - DRY_RUN=true では投稿せず、生成文とログ出力のみ
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent
DATA_PATH = BASE_DIR / "data" / "post_log_rakuten.json"


def env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    sys.path.insert(0, str(BASE_DIR))

    from src.rakuten.content_generator import generate_post, load_log, save_log

    dry_run = env_flag("DRY_RUN", True)
    token = os.environ.get("RAKUTEN_THREADS_ACCESS_TOKEN", "").strip()
    user_id = os.environ.get("RAKUTEN_THREADS_USER_ID", "").strip()
    affiliate_url = os.environ.get("RAKUTEN_AFFILIATE_URL", "").strip()
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()

    entries = load_log(DATA_PATH)
    post = generate_post(entries, affiliate_url=affiliate_url, api_key=groq_key)
    has_affiliate_link = bool(
        affiliate_url and affiliate_url in post.text or "http://" in post.text or "https://" in post.text
    )

    now_jst = datetime.now(JST).isoformat()
    log.info("楽天投稿カテゴリ: %s", post.category)
    log.info("affiliate_post: %s", post.is_affiliate)
    log.info("has_affiliate_link: %s", has_affiliate_link)
    log.info("fallback使用: %s", post.used_fallback)
    log.info("dry_run: %s", dry_run)
    log.info("投稿文 (%s文字):\n%s", len(post.text), post.text)

    record = {
        "posted_at": now_jst,
        "category": post.category,
        "affiliate_post": post.is_affiliate,
        "is_affiliate": post.is_affiliate,
        "has_affiliate_link": has_affiliate_link,
        "used_fallback": post.used_fallback,
        "dry_run": dry_run,
        "text": post.text,
        "success": False,
        "thread_id": None,
        "error": "",
    }

    if dry_run:
        record["success"] = True
        entries.append(record)
        save_log(DATA_PATH, entries)
        print("\n=== DRY RUN ===")
        print(post.text)
        return 0

    if not token:
        log.error("RAKUTEN_THREADS_ACCESS_TOKEN が設定されていません")
        record["error"] = "missing token"
        entries.append(record)
        save_log(DATA_PATH, entries)
        return 1

    # 将来の運用確認用。現時点では user_id 自体は client で自動取得される。
    if not user_id:
        log.warning("RAKUTEN_THREADS_USER_ID が未設定です（現状は token だけで動作可能）")

    from src.threads_client import ThreadsClient

    client = ThreadsClient(token)
    try:
        thread_id = client.post_text(post.text)
        record["success"] = True
        record["thread_id"] = thread_id
        entries.append(record)
        save_log(DATA_PATH, entries)
        log.info("投稿成功: thread_id=%s", thread_id)
        return 0
    except Exception as exc:
        record["error"] = str(exc)
        entries.append(record)
        save_log(DATA_PATH, entries)
        log.error("投稿失敗: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
