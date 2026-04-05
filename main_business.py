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
    "morning": "#副業 #AI活用 #朝活 #生産性向上 #稼ぐ",
    "noon":    "#AIビジネス #副業収入 #SNS運用 #自動化 #個人事業",
    "evening": "#AI副業 #収益化 #フリーランス #資産形成 #ビジネス",
}

LOG_PATH = Path(__file__).parent / "data" / "post_log_business.json"
LOG_MAX  = 50

# ── スロット別コンテンツ設定 ──────────────────────────────────────────────────

SLOT_CONFIG = {
    "morning": {
        "label": "朝の意識高い系に刺さるAI活用tips",
        "tone":  "今日から使えるAIツールの時短テクニックや生産性ハック",
        "hook_templates": [
            "【AI時短術】1日30分の作業を5分にした方法",
            "【朝の生産性】AIを使い始めてから変わった3つのこと",
            "【副業初心者へ】朝1時間でできるAI収益化の始め方",
        ],
    },
    "noon": {
        "label": "昼の暴露系・本音トーク投稿",
        "tone":  "AIビジネスや副業の失敗談・裏事情・業界の嘘を本音で語る",
        "hook_templates": [
            "【本音】AIで稼げると思ってた俺が気づいた現実",
            "【暴露】副業で失敗する人の共通点{n}選",
            "【実態】SNS自動化ツールの限界と可能性",
        ],
    },
    "evening": {
        "label": "夜のゴールデンタイム向け・実践系投稿",
        "tone":  "今夜から動ける具体的なAI副業・収益化の手順を解説",
        "hook_templates": [
            "【完全版】AIで月{amount}稼ぐための最短ルート",
            "【実践】Threadsアフィリエイトで収益化した仕組み",
            "【今夜やること】AI副業を始める前に知っておくべき{n}つの事実",
        ],
    },
}

CTA_POOL = [
    "AIで副業してる人いる？",
    "今どんなAIツール使ってる？",
    "副業収入、月いくら目標にしてる？",
    "自動化で楽になった作業、何かある？",
    "同じような挑戦してる人いたら教えて。",
    "これ知らなかった人、いいね押してって。",
    "どのSNSから収益化した？",
]

FALLBACK_POSTS = {
    "morning": """\
【AI時短術】ChatGPTを使い始めてから変わった朝のルーティン

・メール返信: 3分 → 30秒
・企画書の叩き台: 2時間 → 15分
・SNS投稿文: 20分 → 2分

合計で毎朝2時間以上を取り戻した。
その時間を副業に全振りしてる。

AIを使えてない人は、使えてる人に時間で負けてる。

今どんなAIツール使ってる？""",

    "noon": """\
【本音】「AIで簡単に稼げる」は嘘だと気づいた

・ツールを入れるだけでは稼げない
・自動化しても中身がなければ意味がない
・結局、試行回数と改善の繰り返し

それでも可能性があると思うのは、
失敗コストが限りなく低いから。

0円でスタートして、うまくいったら続ける。
それだけ。

副業で失敗した経験ある人いる？""",

    "evening": """\
【実践】Threads自動投稿×アフィリエイトの仕組みを作った話

やったこと:
1. Gemini APIで毎日投稿文を自動生成
2. GitHub Actionsで1日2回自動投稿
3. 投稿にアフィリエイトリンクを埋め込む

費用: ほぼ0円（無料枠だけで動いてる）

まだ収益は出てないけど、仕組みは動いてる。
あとは伸ばすだけ。

同じような挑戦してる人いたら教えて。""",
}


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


# ── Gemini でコンテンツ生成 ──────────────────────────────────────────────────

def generate_business_post(slot: str, api_key: str) -> str | None:
    try:
        import google.generativeai as genai
    except ImportError:
        log.error("google-generativeai 未インストール")
        return None

    config = SLOT_CONFIG.get(slot, SLOT_CONFIG["evening"])
    hook_raw = random.choice(config["hook_templates"])

    # テンプレート変数を埋める
    hook = hook_raw.format(
        n=random.choice([3, 4, 5]),
        amount=random.choice(["3万円", "5万円", "10万円"]),
    )
    cta = random.choice(CTA_POOL)

    prompt = f"""\
あなたはAI副業・SNS収益化に取り組んでいる等身大の日本人男性です。
成功者ぶらず、リアルな試行錯誤を本音で語るアカウントです。

【この投稿の役割】{config["label"]}
【トーン】{config["tone"]}

【必須構成（厳守）】
1行目（そのまま使う）:
{hook}

中盤: 具体的な数字・ツール名・手順を含めて150〜250文字で語る
・「なんとなく」「らしい」禁止。断言する。
・絵文字は1〜2個まで

末尾CTA（そのまま使う）:
{cta}

投稿テキストのみ出力してください。前置き・説明・「」の括りは一切不要です。"""

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        text = response.text.strip()
        log.info(f"Gemini生成完了: {len(text)}文字 / slot={slot}")
        return text
    except Exception as e:
        log.error(f"Gemini API エラー: {e}")
        return None


# ── メイン ────────────────────────────────────────────────────────────────────

def main():
    token = os.environ.get("BUSINESS_THREADS_ACCESS_TOKEN", "")
    if not token:
        log.error("BUSINESS_THREADS_ACCESS_TOKEN が設定されていません")
        sys.exit(1)

    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        log.warning("GEMINI_API_KEY 未設定 → フォールバックテキストを使用")

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
    body = None
    if gemini_key:
        body = generate_business_post(slot=slot, api_key=gemini_key)

    if not body:
        log.warning("生成失敗 → フォールバックテキストを使用")
        body = FALLBACK_POSTS.get(slot, FALLBACK_POSTS["evening"])

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
