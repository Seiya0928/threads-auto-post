"""
x_draft_generator.py — X（旧Twitter）用投稿下書き生成モジュール

投稿タイプ比率:
  - 知識系 40%: スキンケアtips・成分解説（日本語）
  - 体験系 25%: 施術・変化の記録（日本語）
  - 共感系 20%: あるある・独り言（短め）
  - 反応系 15%: ミームへのコメント（カジュアル）
"""

import logging
import os
import random
from typing import List, Optional

log = logging.getLogger(__name__)

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

_BASE_RULES = """\
【絶対ルール】
・全文日本語（英単語・英文を一切混ぜない）
・一人称・断定口調（「〜だった」「〜してる」。「〜らしい」「〜かも」禁止）
・1ポストに伝えることは1つだけ
・数字を必ず1つ入れる（期間・回数・金額・濃度など）
・説明調・おすすめ口調禁止（「〜してみてください」「〜をおすすめします」NG）
・ハッシュタグは0〜2個
・宣伝・アフィリエイト臭NG
・ネガティブで終わらない。学び・気づき・次の行動で締める
・施術系の動詞：「レーザーを受けた」「クリニックに行った」（「やった」NG）
・治療薬・成分は日本語表記（「Retinol」→「レチノール」）

【良い例】
・「トレチノインを2ヶ月使って、ようやく赤みが落ち着いてきた。最初の1ヶ月が一番しんどかった。」
・「サリチル酸20%のピーリングを3回試して、毛穴の黒ずみが目に見えて減った。痛みゼロなのが続けられてる理由。」
・「ハイドロキノン4%を朝だけ塗って1ヶ月。シミが薄くなってきてる実感がある。」

【NGサンプル（絶対に出力しない）】
・「サリチル酸ピーリングが皮膚の老化細胞を除去して肌を若返らせた。」→ 説明口調・主語が自分でない
・「2ヶ月続けても変化なし。」→ ネガティブで終わっている
・「毎朝2回塗った」→ 非常識な頻度
・英単語を混入させる

投稿テキストのみ出力してください。前置き・説明・括りは不要。"""

PROMPT_KNOWLEDGE = """\
29歳男性・スキンケアマニアとしてXに投稿する。

テーマ: {topic}
起点: {variation}
トーン: ゆるい・一人称・等身大
構成: 日本語のみで1〜3文
文字数: 80〜150文字
ハッシュタグ: 0〜1個

""" + _BASE_RULES

PROMPT_EXPERIENCE = """\
29歳男性・スキンケアマニアとしてXに投稿する。

テーマ: {topic}
起点: {variation}
トーン: ゆるい・正直・感情あり
構成: 体験談を日本語でさらっと1〜3文
文字数: 80〜140文字
ハッシュタグ: 0〜2個

""" + _BASE_RULES

PROMPT_EMPATHY = """\
29歳男性・スキンケアマニアとしてXに独り言をつぶやく。

テーマ: {topic}
起点: {variation}
トーン: ゆるい・短め・クスッとくる
構成: 1〜2文で完結。具体的な数字や体験を入れて薄くならないようにする
文字数: 40〜80文字（40文字未満はNG）
ハッシュタグ: 0〜1個

""" + _BASE_RULES

PROMPT_REACTION = """\
29歳男性・スキンケアマニアとしてXでリアクションをつぶやく。

テーマ: {topic}
起点: {variation}
トーン: カジュアル・正直・ユーモアあり
構成: 1〜2文。日本語のみ
文字数: 40〜100文字
ハッシュタグ: 0〜1個

""" + _BASE_RULES

PROMPT_MAP = {
    "knowledge": PROMPT_KNOWLEDGE,
    "experience": PROMPT_EXPERIENCE,
    "empathy":   PROMPT_EMPATHY,
    "reaction":  PROMPT_REACTION,
}

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

_FALLBACKS = {
    "knowledge":  "トレチノインを使い始めて最初の2週間、肌が荒れるのは正常。知らなくて辞める人が多すぎる。",
    "experience": "レーザー4回目終わった。シミが薄くなってきてるのは確かだけど、ダウンタイムの赤みがしんどい。美容は我慢と投資だなと毎回思う。",
    "empathy":    "スキンケアに月1万使って、食費より高くなってることに気づいた。後悔はゼロ。",
    "reaction":   "海外の美容界隈、成分オタクが多くて逆に安心する。日本ももっとこうなってほしい。",
}


def _pick_post_type() -> str:
    types, weights = zip(*POST_TYPES)
    return random.choices(types, weights=weights, k=1)[0]


def _pick_topics(n: int) -> List[str]:
    pool = TOPICS[:]
    random.shuffle(pool)
    result = []
    for i in range(n):
        result.append(pool[i % len(pool)])
    return result


def generate_drafts(
    count: int = 4,
    api_key: Optional[str] = None,
) -> List[dict]:
    try:
        import anthropic
    except ImportError:
        log.error("anthropic 未インストール: pip install anthropic")
        return []

    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        log.error("ANTHROPIC_API_KEY が設定されていません")
        return []

    client = anthropic.Anthropic(api_key=key)

    topics = _pick_topics(count)
    drafts = []

    for i in range(count):
        post_type = _pick_post_type()
        topic     = topics[i]
        variation = random.choice(_VARIATION_POOL)
        prompt    = PROMPT_MAP[post_type].format(topic=topic, variation=variation)

        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            log.info(f"生成完了 [{i+1}/{count}] type={post_type} topic={topic} / {len(text)}文字")
            drafts.append({
                "type":  post_type,
                "label": TYPE_LABELS[post_type],
                "text":  text,
            })
        except Exception as e:
            log.error(f"API エラー [{i+1}/{count}]: {e}")
            drafts.append({
                "type":  post_type,
                "label": TYPE_LABELS[post_type],
                "text":  _FALLBACKS.get(post_type, _FALLBACKS["knowledge"]),
            })

    return drafts
