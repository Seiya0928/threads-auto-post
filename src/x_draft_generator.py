"""
x_draft_generator.py — X（旧Twitter）用投稿下書き生成モジュール

投稿タイプ比率:
  - 知識系 40%: スキンケアtips・成分解説（日英ミックス）
  - 体験系 25%: 施術・変化の記録（日本語中心）
  - 共感系 20%: あるある・独り言（短め・英語OK）
  - 反応系 15%: ミームへのコメント（カジュアル）
"""

import logging
import os
import random
from typing import List, Optional

log = logging.getLogger(__name__)

# ── コンテンツネタストック（ローテーション） ─────────────────────────────────

TOPICS = [
    "トレチノイン経過報告",
    "ハイドロキノン併用法",
    "レチノールvsトレチノイン",
    "サリチル酸ピーリング体験",
    "医療脱毛の実態",
    "レーザー経過記録",
    "スキンケアに使った総額",
    "日本人男性と美容の話",
    "スキンケア沼あるある",
    "海外の美容ミームへの反応",
]

# ── 投稿タイプ（type名, 重み） ─────────────────────────────────────────────────

POST_TYPES = [
    ("knowledge", 40),
    ("experience", 25),
    ("empathy", 20),
    ("reaction", 15),
]

TYPE_LABELS = {
    "knowledge": "知識系",
    "experience": "体験系",
    "empathy":   "共感系",
    "reaction":  "反応系",
}

# ── 共通ルール ─────────────────────────────────────────────────────────────────

_BASE_RULES = """\
【ルール】
・一人称・断定口調（「〜だった」「〜してる」。「〜らしい」「〜かも」禁止）
・1ポストに1メッセージだけ
・数字を必ず1つ入れる（期間・回数・金額・濃度など）
・説明調・おすすめ口調禁止（「〜してみてください」「〜をおすすめします」NG）
・ハッシュタグは0〜2個
・宣伝・アフィリエイト臭NG
・前置きや「」の括りは不要

投稿テキストのみ出力してください。"""

# ── プロンプトテンプレート ─────────────────────────────────────────────────────

PROMPT_KNOWLEDGE = """\
29歳男性・スキンケアマニアとしてXに投稿する。

テーマ: {topic}
起点: {variation}
トーン: ゆるい・一人称・等身大
構成: 日本語1〜3文 → 英語1〜2文（同内容を言い換えるか補足）
文字数: 120〜180文字（日英合計）
ハッシュタグ: 0〜1個

""" + _BASE_RULES

PROMPT_EXPERIENCE = """\
29歳男性・スキンケアマニアとしてXに投稿する。

テーマ: {topic}
起点: {variation}
トーン: ゆるい・正直・感情あり（成功も失敗も書く）
構成: 体験談を日本語でさらっと1〜3文
文字数: 80〜140文字
ハッシュタグ: 0〜2個

""" + _BASE_RULES

PROMPT_EMPATHY = """\
29歳男性・スキンケアマニアとしてXに独り言をつぶやく。

テーマ: {topic}
起点: {variation}
トーン: ゆるい・短め・クスッとくる
構成: 1〜2文で完結。日本語でも英語でも混在でもOK
文字数: 30〜80文字
ハッシュタグ: 0〜1個

""" + _BASE_RULES

PROMPT_REACTION = """\
29歳男性・スキンケアマニアとしてXでリアクションをつぶやく。

テーマ: {topic}
起点: {variation}
トーン: カジュアル・正直・ユーモアあり
構成: 1〜2文。日本語でも英語でも混在でもOK
文字数: 40〜100文字
ハッシュタグ: 0〜1個

""" + _BASE_RULES

PROMPT_MAP = {
    "knowledge": PROMPT_KNOWLEDGE,
    "experience": PROMPT_EXPERIENCE,
    "empathy":   PROMPT_EMPATHY,
    "reaction":  PROMPT_REACTION,
}

# ── バリエーションヒント（毎回異なる発想の起点にする） ──────────────────────────

_VARIATION_POOL = [
    "朝のルーティンで気づいたこと",
    "先週失敗したこと",
    "コスパに気づいた瞬間",
    "友達に話した内容",
    "続けて3ヶ月たった感想",
    "ネットで見て試したこと",
    "意外と効かなかったもの",
    "やめてよかったこと",
    "金額と効果の話",
    "男目線でのスキンケア",
    "クリニックで言われたこと",
    "自分の失敗談から学んだこと",
    "最近ハマってること",
    "昔の自分に教えたいこと",
    "SNSでよく見る誤解",
]

# ── フォールバック ─────────────────────────────────────────────────────────────

_FALLBACKS = {
    "knowledge": (
        "トレチノインを使い始めて最初の2週間、肌が荒れるのは正常。これ知らなくて辞める人が多すぎる。\n"
        'The "purging phase" is real — give it 4-6 weeks before judging results.'
    ),
    "experience": (
        "レーザー4回目終わった。シミが薄くなってきてるのは確かだけど、ダウンタイムの赤みがしんどい。"
        "美容は我慢と投資だなと毎回思う。"
    ),
    "empathy":  "spending more on skincare than on food and feeling zero regret about it",
    "reaction": "海外の美容界隈、成分オタクが多くて逆に安心する。日本ももっとこうなってほしい。",
}


# ── ヘルパー ───────────────────────────────────────────────────────────────────

def _pick_post_type() -> str:
    types, weights = zip(*POST_TYPES)
    return random.choices(types, weights=weights, k=1)[0]


def _pick_topics(n: int) -> List[str]:
    """連続しないようにシャッフルして n 個返す"""
    pool = TOPICS[:]
    random.shuffle(pool)
    # n > len(pool) の場合はラップアラウンド（ただし隣接は避ける）
    result = []
    for i in range(n):
        result.append(pool[i % len(pool)])
    return result


# ── メイン関数 ────────────────────────────────────────────────────────────────

def generate_drafts(
    count: int = 4,
    api_key: Optional[str] = None,
) -> List[dict]:
    """
    X用投稿下書きを count 本生成する。

    Args:
        count:   生成本数（3〜5推奨）
        api_key: Gemini API キー（省略時は GEMINI_API_KEY 環境変数）

    Returns:
        List of {"type": str, "label": str, "text": str}
    """
    try:
        from google import genai
    except ImportError:
        log.error("google-genai 未インストール: pip install google-genai")
        return []

    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        log.error("GEMINI_API_KEY が設定されていません")
        return []

    client = genai.Client(api_key=key)

    topics = _pick_topics(count)
    drafts = []

    for i in range(count):
        post_type = _pick_post_type()
        topic     = topics[i]
        variation = random.choice(_VARIATION_POOL)
        prompt    = PROMPT_MAP[post_type].format(topic=topic, variation=variation)

        try:
            response = client.models.generate_content(
                model="gemini-1.5-flash-8b",
                contents=prompt,
            )
            text = response.text.strip()
            log.info(f"生成完了 [{i+1}/{count}] type={post_type} topic={topic} / {len(text)}文字")
            drafts.append({
                "type":  post_type,
                "label": TYPE_LABELS[post_type],
                "text":  text,
            })
        except Exception as e:
            log.error(f"Gemini API エラー [{i+1}/{count}]: {e}")
            drafts.append({
                "type":  post_type,
                "label": TYPE_LABELS[post_type],
                "text":  _FALLBACKS.get(post_type, _FALLBACKS["knowledge"]),
            })

    return drafts
