"""
business/content_generator.py — ビジネス・AI副業アカウント用コンテンツ生成

キャラクター: AI副業に挑戦中の等身大の人間
トーン:      試行錯誤のリアルさ + 具体的なツール紹介の組み合わせ
ターゲット:  AIで何か始めたいけどまだ形になっていない人
方針:        上から目線NG。一緒に模索している雰囲気で。
"""

import logging
import os
import random
from typing import Optional

log = logging.getLogger(__name__)

# ── スロット別設定 ────────────────────────────────────────────────────────────

SLOT_CONFIG = {
    "morning": {
        "role": "今日やることを決める朝の投稿。自分への宣言 or 昨日の小さな気づき",
        "tone": "「よし、やるか」という前向きさ。ただし盛らない。等身大で。",
        "hooks": [
            "昨日、{tool}を初めて触ってみた話",
            "AI副業を始めて{period}経った正直な感想",
            "今日やること、宣言しておく",
            "{tool}を使ったら{time}かかってた作業が{short_time}で終わった",
            "朝イチで気づいた、自動化の盲点",
        ],
    },
    "noon": {
        "role": "具体的なツール紹介 or 失敗談の暴露。昼に流し読みされることを意識",
        "tone": "「これ俺もやってた」と共感されるリアルさ。失敗も隠さない。",
        "hooks": [
            "正直に言うと、{tool}を使っても最初は全然うまくいかなかった",
            "【実験中】{method}を試してみた結果",
            "AI副業で失敗する人の共通点、自分がそれだったと気づいた話",
            "{tool}の使い方、誰も教えてくれなかった{n}つのこと",
            "やってみてわかった、{topic}の現実",
        ],
    },
    "evening": {
        "role": "今日の進捗報告 or 具体的な手順の共有。夜に腰を据えて読まれる",
        "tone": "具体的な数字・ツール名・手順を出す。ただし成功自慢にならないように。",
        "hooks": [
            "今日やったこと、正直に報告する",
            "【手順メモ】{tool}で{task}を自動化した方法",
            "月{amount}を目標に動いてる、今の進捗",
            "{tool}×{tool2}の組み合わせが思ったより使えた話",
            "夜にやってみてほしい、{topic}の最初の一歩",
        ],
    },
}

# ── フック変数プール ──────────────────────────────────────────────────────────

HOOK_VARS = {
    "tool":       ["Claude Code", "Gemini API", "GitHub Actions", "Threads API",
                   "A8.net", "CapCut", "Canva", "Notion AI", "ChatGPT"],
    "tool2":      ["GitHub Actions", "Gemini API", "Google Trends", "Canva"],
    "method":     ["Threads自動投稿", "アフィリエイト×SNS", "AI記事生成", "自動リサーチ"],
    "topic":      ["SNS自動化", "AI副業", "アフィリエイト", "コンテンツ量産"],
    "task":       ["投稿生成", "トレンドリサーチ", "ハッシュタグ選定", "コンテンツ作成"],
    "period":     ["1週間", "2週間", "1ヶ月"],
    "time":       ["2時間", "30分", "1時間"],
    "short_time": ["5分", "10分", "15分"],
    "amount":     ["3万円", "5万円", "10万円"],
    "n":          ["3", "4", "5"],
}

# ── CTA プール ────────────────────────────────────────────────────────────────

CTA_POOL = [
    "同じように試してる人いる？",
    "うまくいったら報告します。",
    "もっといい方法あったら教えてほしい。",
    "これ知ってた人いたらもっと早く教えてほしかった。",
    "失敗した人いたら一緒に考えたい。",
    "やり方間違えてたら遠慮なく突っ込んでください。",
    "同じとこで詰まった人いたら教えて。",
    "続きはまた報告する。",
]

# ── フォールバック投稿 ────────────────────────────────────────────────────────

FALLBACK_POSTS = [
    "AIツール使い始めて気づいたこと。学習コストより、とりあえず動かすコストの方が低い。完璧に理解してから使おうとすると永遠に始まらない。#AI活用 #副業",
    "自動化の仕組みを1個作ると、次が作りやすくなる感覚がある。スキルじゃなくて思考回路が変わる感じ。同じ感覚の人いる？#AI副業 #生産性向上",
    "ChatGPTとClaude、用途で使い分けてる。コード書かせるならClaude、壁打ちにはどっちでも。正解はまだわからん。#AI #副業",
    "ビジネス系の情報、発信者が成功者すぎて参考にならないことがある。自分はまだ途中なので、途中の話をする。#副業 #リアル",
]


# ── フック組み立て ────────────────────────────────────────────────────────────

def _build_hook(slot: str) -> str:
    config = SLOT_CONFIG.get(slot, SLOT_CONFIG["evening"])
    template = random.choice(config["hooks"])
    try:
        filled = template.format(**{k: random.choice(v) for k, v in HOOK_VARS.items()})
    except KeyError:
        filled = template
    return filled


# ── プロンプト組み立て ────────────────────────────────────────────────────────

def _build_prompt(slot: str, hook: str, cta: str) -> str:
    config = SLOT_CONFIG.get(slot, SLOT_CONFIG["evening"])
    return f"""\
あなたは「AIで副業を始めたばかりの普通の人間」として発信しています。
まだ大きな成果は出ていないけど、毎日試行錯誤している等身大のキャラクターです。

【この投稿の役割】{config["role"]}
【トーン】{config["tone"]}

【絶対にやってはいけないこと】
・成功者ぶる（「月〇〇万達成」のような断言はしない）
・抽象的なアドバイス（「行動が大事です」は禁止）
・上から目線（「〜すべき」「〜しなさい」は禁止）
・嘘の数字（実際に試したことだけを書く）

【必ず含めること】
・具体的なツール名、数字、または手順を1つ以上
・読んだ人が「自分もやってみようかな」と思える一歩

【文体ルール】
・話し言葉に近い自然な文体
・絵文字は0〜1個まで
・150〜280文字（ハッシュタグ含めない）

1行目（そのまま使う）:
{hook}

末尾（そのまま使う）:
{cta}

投稿テキストのみ出力してください。前置き・説明・括りは一切不要です。"""


# ── メイン関数 ────────────────────────────────────────────────────────────────

def generate_post(
    slot: str,
    api_key: Optional[str] = None,
) -> Optional[str]:
    """
    Groq API でビジネス・AI副業系の投稿テキストを生成する。

    Args:
        slot:    "morning" | "noon" | "evening"
        api_key: Groq API キー（省略時は GROQ_API_KEY 環境変数）

    Returns:
        生成された投稿テキスト。失敗時は None。
    """
    try:
        from groq import Groq
    except ImportError:
        log.error("groq 未インストール: pip install groq")
        return None

    key = api_key or os.environ.get("GROQ_API_KEY", "")
    if not key:
        log.error("GROQ_API_KEY が設定されていません")
        return None

    hook   = _build_hook(slot)
    cta    = random.choice(CTA_POOL)
    prompt = _build_prompt(slot, hook, cta)

    try:
        client   = Groq(api_key=key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.choices[0].message.content.strip()
        log.info(f"Groq生成完了: {len(text)}文字 / slot={slot}")
        return text
    except Exception as e:
        log.error(f"Groq API エラー: {e}")
        return None
