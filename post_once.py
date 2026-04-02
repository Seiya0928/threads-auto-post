"""
post_once.py — GitHub Actions から呼び出す1回限りの投稿スクリプト

フロー:
  1. 現在のJST時刻からスロット（morning/noon/evening）を判定
  2. Googleトレンドからキーワード取得（失敗時はフォールバック）
  3. Gemini API でバズる投稿文を動的生成
  4. スロット別ハッシュタグ + アフィリエイトリンクを付与
  5. Threads に投稿
"""

import os
import sys
import logging
from datetime import datetime, timezone, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

HASHTAG_SETS = {
    "morning": "#スキンケア #朝活 #美肌ルーティン #skincare #美容男子",
    "noon":    "#美容の嘘 #スキンケア #コスパ最強 #skincare #美肌",
    "evening": "#夜スキンケア #美容液 #エイジングケア #skincare #保湿",
}


def get_slot() -> str:
    jst_hour = datetime.now(JST).hour
    if 5 <= jst_hour < 11:
        return "morning"
    elif 11 <= jst_hour < 17:
        return "noon"
    else:
        return "evening"


def build_full_text(body: str, slot: str) -> str:
    """本文 + ハッシュタグ + アフィリエイトリンクを組み立てる"""
    hashtags = HASHTAG_SETS.get(slot, HASHTAG_SETS["evening"])
    affiliate_url = os.environ.get("AFFILIATE_URL", "").strip()

    parts = [body, "", hashtags]

    if affiliate_url:
        parts += ["", f"🛒 おすすめはこちら → {affiliate_url}"]

    return "\n".join(parts)


def main():
    # ── 認証情報チェック ──────────────────────────────────
    token = os.environ.get("THREADS_ACCESS_TOKEN", "")
    if not token:
        log.error("THREADS_ACCESS_TOKEN が設定されていません")
        sys.exit(1)

    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        log.warning("GEMINI_API_KEY 未設定 → フォールバックテキストを使用")

    sys.path.insert(0, os.path.dirname(__file__))

    from src.threads_client import ThreadsClient
    from src.trend_fetcher import fetch_beauty_trends
    from src.content_generator import generate_post

    # ── スロット判定 ──────────────────────────────────────
    slot = get_slot()
    log.info(f"スロット: {slot} (JST {datetime.now(JST).strftime('%H:%M')})")

    # ── Googleトレンド取得 ────────────────────────────────
    log.info("Googleトレンドキーワードを取得中...")
    trends = fetch_beauty_trends()
    log.info(f"キーワード: {trends}")

    # ── Gemini で投稿文生成 ───────────────────────────────
    body = None
    if gemini_key:
        log.info("Gemini API で投稿文を生成中...")
        body = generate_post(slot=slot, trend_keywords=trends, api_key=gemini_key)

    # フォールバック
    if not body:
        log.warning("生成失敗 → フォールバックテキストを使用")
        fallback = {
            "morning": "朝の洗顔、熱いお湯使ってない？\n\n40℃以上で洗うと皮脂を取りすぎて夕方べたつく原因になる。ぬるま湯（32〜35℃）が正解。たったこれだけで夕方の崩れ方が変わった。\n\n洗顔ひとつで一日の肌が決まる。",
            "noon":    "「高いコスメ=効く」と思ってたら損してる。\n\n有効成分の濃度と処方が全て。1000円のナイアシンアミド5%配合品より、5000円で0.1%配合の方が意味ない。成分表を読む習慣がついたら、スキンケアの無駄遣いが激減した。",
            "evening": "夜スキンケア、順番間違えてない？\n\n美容液を乳液の後に塗っても浸透しない。正解は化粧水→美容液→乳液→クリームの順。分子の小さいものから大きいものへ。これ知ってから肌の変化が明らかに速くなった。",
        }
        body = fallback.get(slot, fallback["evening"])

    # ── 本文 + ハッシュタグ + アフィリエイト組み立て ────────
    full_text = build_full_text(body, slot)
    log.info(f"投稿テキスト ({len(full_text)}文字):\n{full_text}")

    # ── Threads に投稿 ────────────────────────────────────
    client = ThreadsClient(token)

    try:
        uid = client.user_id
        log.info(f"認証OK: user_id={uid}")
    except Exception as e:
        log.error(f"認証失敗: {e}")
        sys.exit(1)

    try:
        thread_id = client.post_text(full_text)
        log.info(f"投稿成功: thread_id={thread_id}")
    except Exception as e:
        log.error(f"投稿失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
