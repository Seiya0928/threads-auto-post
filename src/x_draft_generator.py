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
【絶対ルール】
・一人称で書く（「〜らしい」より「〜だった」「〜してる」）
・1ポストに1メッセージだけ。余計なことを詰め込まない
・数字を使う（「2週間」「4回目」「3000円」など具体的に）
・説明調NG（「〜をおすすめします」「〜してみてください」は使わない）
・ハッシュタグは0〜2個（多すぎると宣伝臭が出る）
・宣伝・アフィリエイト感のある文体は絶対に避ける
・断定する（「〜かも」「〜かもしれない」禁止）
・「」の括りや前置き説明は不要

【例文について】
・下に示す例文は「文体・テンション・長さ」の参考のみ
・例文の単語・フレーズ・エピソードをそのまま流用するのは絶対禁止
・「purging phase」「シミが薄くなってきてる」など例文由来の表現は使わない
・毎回まったく違う切り口・エピソード・表現で書くこと

バリエーションヒント（このワードを起点にして発想を広げること）: {variation}

投稿テキストのみ出力してください。"""

# ── プロンプトテンプレート ─────────────────────────────────────────────────────

PROMPT_KNOWLEDGE = """\
あなたは29歳男性のスキンケアマニアです。トレチノインとハイドロキノンを実際に使っている当事者として、等身大でXに投稿します。

【投稿タイプ】知識系（日英ミックス）
【テーマ】{topic}
【トーン】ゆるい・人間っぽい。知識を押しつけない。「俺はこう思う」スタンス

【構成】
- 日本語パート: 1〜3文で核心を伝える（体験ベースで具体的に）
- 英語パート: 1〜2文で補足または同じ内容を英語で言い換える
- ハッシュタグ: 0〜1個（なくてもいい）

【文字数】全体で120〜180文字（日英合計）

【トーン参考例（内容・フレーズを流用するのは絶対禁止）】
ハイドロキノンは日焼けすると色戻りが速い。夏に使うなら絶対に日焼け止めとセット。
日焼け止め塗らずに使い続けてたら意味なかった、という実体験。
Hydroquinone fades spots, but UV exposure reverses it fast. Sunscreen isn't optional.

""" + _BASE_RULES

PROMPT_EXPERIENCE = """\
あなたは29歳男性のスキンケアマニアです。美容クリニック・レーザー・薬剤を実際に試している当事者として等身大でXに投稿します。

【投稿タイプ】体験系（日本語中心）
【テーマ】{topic}
【トーン】ゆるい・正直。成功も失敗も書く。感情を出していい

【構成】
- 体験談を日本語でさらっと1〜3文
- 数字（回数・期間・金額）を必ず1つ入れる
- ハッシュタグ: 0〜2個

【文字数】80〜140文字

【トーン参考例（内容・フレーズを流用するのは絶対禁止）】
サリチル酸ピーリング初めてやってみた。ヒリヒリは想定内だったけど、翌日の皮むけが想像以上。5日間は人に会いたくなかった。

""" + _BASE_RULES

PROMPT_EMPATHY = """\
あなたは29歳男性のスキンケアマニアです。スキンケア沼にはまった当事者としてXに独り言をつぶやきます。

【投稿タイプ】共感系（短め・英語OK）
【テーマ】{topic}
【トーン】ゆるい・クスッとくる・「あるある」と思わせる

【構成】
- 1〜2文で完結
- 日本語でも英語でも混在でもOK
- 数字があればなお良い
- ハッシュタグ: 0〜1個（なくてもいい）

【文字数】30〜80文字

【トーン参考例（内容・フレーズを流用するのは絶対禁止）】
美容クリニックの待合室、男が俺だけで毎回ちょっと緊張する

""" + _BASE_RULES

PROMPT_REACTION = """\
あなたは29歳男性のスキンケアマニアです。海外の美容ミームや話題に対して自分の意見をXでつぶやきます。

【投稿タイプ】反応系（ミームへのコメント）
【テーマ】{topic}
【トーン】カジュアル・正直・ユーモアあり

【構成】
- 「これ」「こういうの」「わかる/わからん」などのリアクション口調でOK
- 日本語でも英語でも混在でもOK
- ハッシュタグ: 0〜1個

【文字数】40〜100文字

【トーン参考例（内容・フレーズを流用するのは絶対禁止）】
海外のスキンケアオタク、成分濃度を%で語るのが当たり前なの普通にすごいと思う

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
        import google.generativeai as genai
    except ImportError:
        log.error("google-generativeai 未インストール: pip install google-generativeai")
        return []

    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        log.error("GEMINI_API_KEY が設定されていません")
        return []

    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    topics = _pick_topics(count)
    drafts = []

    for i in range(count):
        post_type = _pick_post_type()
        topic     = topics[i]
        variation = random.choice(_VARIATION_POOL)
        prompt    = PROMPT_MAP[post_type].format(topic=topic, variation=variation)

        try:
            response = model.generate_content(prompt)
            text     = response.text.strip()
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
