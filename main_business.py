"""
main_business.py — Threads ビジネス・AI活用 自動投稿スクリプト（GitHub Actions 用）

フロー:
  1. 現在のJST時刻からスロット（morning/noon/evening）を判定
  2. Gemini API でビジネス・AI系投稿文を動的生成
  3. スロット別ハッシュタグを付与
  4. 冪等性チェック（直近2時間以内に投稿済みならスキップ）
  5. Threads に投稿（BUSINESS_THREADS_ACCESS_TOKEN を使用）
  6. ログに記録
"""

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

HASHTAG_SETS = {
    "morning": "#副業 #AI活用 #朝活 #生産性向上 #稼ぐ",
    "noon":    "#AIビジネス #副業収入 #SNS運用 #自動化 #個人事業",
    "evening": "#AI副業 #収益化 #フリーランス #資産形成 #ビジネス",
}

LOG_PATH = Path(__file__).parent / "data" / "post_log_business.json"
LOG_MAX  = 50


# ── スロット判定 ──────────────────────────────────────────────────────────────

def get_slot() -> str:
    jst_hour = datetime.now(JST).hour
    if 5 <= jst_hour < 11:
        return "morning"
    elif 11 <= jst_hour < 17:
        return "noon"
    else:
        return "evening"


# ── テキスト組み立て ─────────────────────────────────────────────────────────

def build_full_text(body: str, slot: str) -> str:
    hashtags = HASHTAG_SETS.get(slot, HASHTAG_SETS["evening"])
    return f"{body}\n\n{hashtags}"


# ── ログ管理 ─────────────────────────────────────────────────────────────────

def load_log() -> list:
    try:
        if LOG_PATH.exists():
            return json.loads(LOG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning(f"ログ読み込み失敗: {e}")
    return []


def save_log(entries: list) -> None:
    try:
        LOG_PATH.parent.mkdir(exist_ok=True)
        LOG_PATH.write_text(
            json.dumps(entries[-LOG_MAX:], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        log.warning(f"ログ保存失敗: {e}")


# ── メイン ────────────────────────────────────────────────────────────────────

def main():
    token = os.environ.get("BUSINESS_THREADS_ACCESS_TOKEN", "")
    if not token:
        log.error("BUSINESS_THREADS_ACCESS_TOKEN が設定されていません")
        sys.exit(1)

    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key:
        log.warning("GROQ_API_KEY 未設定 → フォールバックテキストを使用")

    sys.path.insert(0, os.path.dirname(__file__))
    from src.threads_client import ThreadsClient

    slot = get_slot()
    log.info(f"スロット: {slot} (JST {datetime.now(JST).strftime('%H:%M')})")

    client = ThreadsClient(token)

    try:
        uid = client.user_id
        log.info(f"認証OK: user_id={uid}")
    except Exception as e:
        log.error(f"認証失敗: {e}")
        sys.exit(1)

    # 冪等性チェック（Threads APIで直近投稿を確認）
    post_log = load_log()
    if client.was_recently_posted(within_hours=2):
        log.warning("直近2時間以内に投稿済みのためスキップ")
        save_log(post_log)
        sys.exit(0)

    # コンテンツ生成
    from src.business.content_generator import generate_post
    from src.business.content_generator import FALLBACK_POSTS as BUSINESS_FALLBACK

    body = None
    if groq_key:
        body = generate_post(slot=slot, api_key=groq_key)

    if not body:
        log.warning("生成失敗 → フォールバックテキストを使用")
        body = BUSINESS_FALLBACK.get(slot, BUSINESS_FALLBACK["evening"])

    full_text = build_full_text(body, slot)
    log.info(f"投稿テキスト ({len(full_text)}文字):\n{full_text}")

    # 投稿
    try:
        thread_id = client.post_text(full_text)
        log.info(f"投稿成功: thread_id={thread_id}")
    except Exception as e:
        log.error(f"投稿失敗: {e}")
        save_log(post_log)
        sys.exit(1)

    # ログ記録
    post_log.append({
        "thread_id": thread_id,
        "slot":      slot,
        "posted_at": datetime.now(timezone.utc).isoformat(),
    })
    save_log(post_log)
    log.info(f"ログ記録完了: 累計{len(post_log)}件")


if __name__ == "__main__":
    main()
