"""
post_once.py — GitHub Actions から呼び出す1回限りの投稿スクリプト

フロー:
  1. 現在のJST時刻からスロット（morning/noon/evening）を判定
  2. A/Bテストログを読み込み、勝ちスタイルを決定
  3. Googleトレンドからキーワード取得（失敗時はフォールバック）
  4. Gemini API でバズる投稿文を動的生成
  5. スロット別ハッシュタグ + アフィリエイトリンクを付与
  6. 冪等性チェック（直近2時間以内に投稿済みならスキップ）
  7. Threads に投稿
  8. A/Bテストログに結果を記録（直近投稿のメトリクスも更新）
"""

import json
import logging
import os
import random
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
    "morning": "#スキンケア #朝活 #美肌ルーティン #skincare #美容男子",
    "noon":    "#美容の嘘 #スキンケア #コスパ最強 #skincare #美肌",
    "evening": "#夜スキンケア #美容液 #エイジングケア #skincare #保湿",
}

LOG_PATH = Path(__file__).parent / "data" / "post_log.json"
LOG_MAX  = 50  # 保持する最大件数


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
    hashtags      = HASHTAG_SETS.get(slot, HASHTAG_SETS["evening"])
    affiliate_url = os.environ.get("AFFILIATE_URL", "").strip()
    parts         = [body, "", hashtags]
    if affiliate_url:
        parts += ["", f"🛒 おすすめはこちら → {affiliate_url}"]
    return "\n".join(parts)


# ── A/Bテストログ ────────────────────────────────────────────────────────────

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


def update_metrics(entries: list, client) -> list:
    """直近投稿のうち、まだメトリクスが未取得のものを更新する（最大3件）"""
    updated = 0
    for entry in reversed(entries):
        if updated >= 3:
            break
        if entry.get("views") is not None:
            continue
        posted_at = datetime.fromisoformat(entry["posted_at"])
        age_hours = (datetime.now(timezone.utc) - posted_at.astimezone(timezone.utc)).total_seconds() / 3600
        if age_hours < 1:
            continue  # 投稿直後はまだメトリクスが反映されていない
        metrics = client.get_post_metrics(entry["thread_id"])
        if metrics:
            entry["views"]   = metrics.get("views", 0)
            entry["likes"]   = metrics.get("likes", 0)
            entry["replies"] = metrics.get("replies", 0)
            log.info(f"メトリクス更新: id={entry['thread_id']} views={entry['views']} likes={entry['likes']}")
            updated += 1
    return entries


def choose_style(entries: list) -> str:
    """
    A/Bテストの結果から投稿スタイルを選ぶ。
    データが少ない場合は50/50。勝ちスタイルが30%以上リードしたら80%で採用。
    """
    measured = [e for e in entries if e.get("views") is not None]
    if len(measured) < 6:
        style = random.choice(["list", "paragraph"])
        log.info(f"A/Bテスト: データ不足のためランダム選択 → {style}")
        return style

    def avg_views(s):
        vals = [e["views"] for e in measured if e.get("style") == s and e["views"] > 0]
        return sum(vals) / len(vals) if vals else 0

    avg_list = avg_views("list")
    avg_para = avg_views("paragraph")
    log.info(f"A/Bテスト: list avg_views={avg_list:.1f} / paragraph avg_views={avg_para:.1f}")

    if avg_list == 0 and avg_para == 0:
        return random.choice(["list", "paragraph"])

    if avg_list > avg_para * 1.3:
        style = "list" if random.random() < 0.8 else "paragraph"
    elif avg_para > avg_list * 1.3:
        style = "paragraph" if random.random() < 0.8 else "list"
    else:
        style = random.choice(["list", "paragraph"])

    log.info(f"A/Bテスト: 選択スタイル → {style}")
    return style


# ── メイン ────────────────────────────────────────────────────────────────────

def main():
    # ── 認証情報チェック ──────────────────────────────────────────────────
    token = os.environ.get("THREADS_ACCESS_TOKEN", "")
    if not token:
        log.error("THREADS_ACCESS_TOKEN が設定されていません")
        sys.exit(1)

    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key:
        log.warning("GROQ_API_KEY 未設定 → フォールバックテキストを使用")

    sys.path.insert(0, os.path.dirname(__file__))

    from src.threads_client    import ThreadsClient
    from src.trend_fetcher     import fetch_beauty_trends
    from src.content_generator import generate_post

    # ── スロット判定 ──────────────────────────────────────────────────────
    slot = get_slot()
    log.info(f"スロット: {slot} (JST {datetime.now(JST).strftime('%H:%M')})")

    # ── A/Bテストログ読み込み ─────────────────────────────────────────────
    ab_log = load_log()

    # ── Threads クライアント初期化 ────────────────────────────────────────
    client = ThreadsClient(token)

    try:
        uid = client.user_id
        log.info(f"認証OK: user_id={uid}")
    except Exception as e:
        log.error(f"認証失敗: {e}")
        sys.exit(1)

    # ── メトリクス更新（前回投稿分）─────────────────────────────────────
    ab_log = update_metrics(ab_log, client)

    # ── 冪等性チェック（2時間以内に投稿済みならスキップ）───────────────
    force_post = os.environ.get("FORCE_POST", "").lower() == "true"
    if force_post:
        log.warning("FORCE_POST=true のため冪等性チェックをスキップします")
    elif client.was_recently_posted(within_hours=2):
        log.warning("直近2時間以内に投稿済みのため、重複投稿をスキップします")
        save_log(ab_log)
        sys.exit(0)

    # ── A/Bスタイル選択 ──────────────────────────────────────────────────
    style = choose_style(ab_log)

    # ── Googleトレンド取得 ────────────────────────────────────────────────
    log.info("Googleトレンドキーワードを取得中...")
    trends = fetch_beauty_trends()
    log.info(f"キーワード: {trends}")

    # ── Groq で投稿文生成 ────────────────────────────────────────────────
    body = None
    if groq_key:
        log.info(f"Groq API で投稿文を生成中... (style={style})")
        body = generate_post(slot=slot, trend_keywords=trends, api_key=groq_key, style=style)

    # フォールバック
    if not body:
        log.warning("生成失敗 → フォールバックテキストを使用")
        fallback = {
            "morning": "【時短美容】忙しい朝にこれだけはやっておけ\n\n・洗顔はぬるま湯（32〜35℃）で皮脂を取りすぎない\n・化粧水は拭き取らず手のひらで押し込む\n・日焼け止め SPF30以上は必須\n\nたったこれだけで夕方の崩れ方が変わった。\n\n朝のスキンケア、何分かけてる？",
            "noon":    "【意外な事実】実はNGなスキンケア習慣3選\n\n1. 高いコスメ=効く（成分濃度が全て）\n2. 洗顔を念入りにする（皮脂の取りすぎ）\n3. 化粧水をパシャパシャつける（浸透しない）\n\n成分表を読む習慣がついたら無駄遣いが激減した。\n\nあなたの推し成分、何？",
            "evening": "【成分比較】セラミドとヒアルロン酸、どっちが効果高い？\n\n・セラミド: バリア機能を補修、長期的に肌質改善\n・ヒアルロン酸: 即効保水、乾燥した日の緊急ケア\n\n結論: 夜はセラミド配合クリームで土台を作る。ヒアルロン酸は化粧水で十分。\n\nみんなの推し保湿クリームは何？",
        }
        body  = fallback.get(slot, fallback["evening"])
        style = "list"  # フォールバックはリスト形式

    # ── 本文 + ハッシュタグ + アフィリエイト組み立て ──────────────────
    full_text = build_full_text(body, slot)
    log.info(f"投稿テキスト ({len(full_text)}文字):\n{full_text}")

    # ── Threads に投稿 ────────────────────────────────────────────────────
    try:
        thread_id = client.post_text(full_text)
        log.info(f"投稿成功: thread_id={thread_id}")
    except Exception as e:
        log.error(f"投稿失敗: {e}")
        save_log(ab_log)
        sys.exit(1)

    # ── A/Bテストログに記録 ───────────────────────────────────────────────
    ab_log.append({
        "thread_id": thread_id,
        "style":     style,
        "slot":      slot,
        "posted_at": datetime.now(timezone.utc).isoformat(),
        "views":     None,
        "likes":     None,
        "replies":   None,
    })
    save_log(ab_log)
    log.info(f"A/Bログ記録: style={style} / 累計{len(ab_log)}件")


if __name__ == "__main__":
    main()
