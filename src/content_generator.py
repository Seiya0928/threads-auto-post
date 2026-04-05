"""
content_generator.py — Gemini API でバズる美容投稿を動的生成する

バズる型:
  - 暴露型   : 「実はNGな〇〇」「やめた方がいい〇〇」
  - コスパ型  : 「〇〇円以下で肌が変わった」
  - 逆説型   : 「〇〇をやめたら肌が良くなった話」
  - 比較型   : 「〇〇 vs 〇〇、本当に効くのはどっち」
  - 数字型   : 「〇〇日で実感した〇〇」
  - ランキング型: 「実際に使って良かった〇〇 TOP3」
  - 共感型   : 「〇〇してる人、全員やめて」
  - 体験型   : 「〇〇を試して3ヶ月、正直な結果を報告する」

A/Bテスト: list（保存されやすい）vs paragraph（共感・拡散されやすい）
"""

import logging
import os
import random
from typing import List, Optional

log = logging.getLogger(__name__)

# ── フック定義（型 × テンプレート）────────────────────────────────────────────

HOOK_BANK = {
    "expose": [
        "実はNGなスキンケア習慣{n}選、全部やってた",
        "【やめて】肌を悪化させてる洗顔の間違い{n}つ",
        "皮膚科医が「意味ない」と言うスキンケア{n}選",
        "「肌に良い」と信じてたのに逆効果だったもの",
    ],
    "cospa": [
        "{price}円以下で買えた、肌が変わった話",
        "高いコスメより効いた、コスパ最強の{ingredient}",
        "ドラッグストアで買える、皮膚科処方レベルの成分",
        "月{price}円のスキンケアで肌質が変わった理由",
    ],
    "reverse": [
        "{item}をやめたら肌が良くなった話",
        "毎日やってた{habit}を止めた結果",
        "「丁寧なスキンケア」が肌を悪化させていた",
        "引き算スキンケアに変えてから肌が安定した",
    ],
    "comparison": [
        "{A}と{B}、{n}ヶ月使い続けて正直な差を報告する",
        "【成分比較】{A}と{B}、どっちが本当に効く",
        "{A} vs {B}、肌への負担が少ないのはどっち",
    ],
    "number": [
        "{n}日で実感した、{ingredient}の本当の効果",
        "トレチノインを{n}週間使った肌の変化を記録する",
        "{n}ヶ月続けてわかった、スキンケアの優先順位",
    ],
    "ranking": [
        "実際に使って良かった保湿アイテム TOP{n}",
        "肌が変わったと感じた瞬間 ベスト{n}",
        "買って後悔したスキンケア{n}選、正直に言う",
    ],
    "empathy": [
        "これやってる人、今すぐやめた方がいい",
        "スキンケアに{price}円以上かけてる人に言いたいこと",
        "肌荒れが治らない人、原因これじゃないですか",
        "毛穴が気になってた俺が、一番効いたと感じたこと",
    ],
    "experience": [
        "{item}を試して{n}ヶ月、正直な結果を報告する",
        "ずっと悩んでた{concern}が変わった話",
        "クリニックで処方された{item}、使ってみた感想",
    ],
}

# ── フック変数プール ──────────────────────────────────────────────────────────

HOOK_VARS = {
    "n":          ["3", "4", "5", "2", "3"],
    "price":      ["1000", "2000", "3000", "500", "1500"],
    "ingredient": ["セラミド", "ナイアシンアミド", "レチノール", "ビタミンC誘導体", "トレチノイン"],
    "item":       ["トレチノイン", "ハイドロキノン", "ナイアシンアミド美容液", "セラミドクリーム"],
    "habit":      ["ゴシゴシ洗顔", "タオルで拭く習慣", "高いクレンジング", "毎日パック"],
    "concern":    ["シミ", "毛穴", "くすみ", "肌荒れ", "乾燥"],
    "A":          ["セラミド", "ナイアシンアミド", "レチノール", "ヒアルロン酸"],
    "B":          ["ヒアルロン酸", "コラーゲン", "プラセンタ", "ビタミンC"],
}

# ── CTA プール ─────────────────────────────────────────────────────────────────

CTA_POOL = [
    "これ知らなかった人いたら保存しておいて。",
    "同じ悩みの人いたら教えて。",
    "みんなの推し成分、何？",
    "あなたの推し保湿クリームは何？",
    "乳液派？クリーム派？どっち？",
    "これ使ったことある人いる？",
    "洗顔何使ってる？教えて。",
    "朝のスキンケア、何分かけてる？",
    "やめて良かったスキンケア、何かある？",
    "毛穴ケアで実感した方法、教えてほしい。",
]

# ── スロット別設定 ─────────────────────────────────────────────────────────────

SLOT_CONFIG = {
    "morning": {
        "label":      "朝の習慣・時短スキンケアに刺さる投稿",
        "tone":       "今日から変えられる朝のスキンケアの小さな改善点",
        "hook_types": ["expose", "reverse", "empathy"],
        "hashtags":   "#スキンケア #朝活 #美肌ルーティン #skincare #美容男子",
    },
    "noon": {
        "label":      "昼の暴露・コスパ・ランキング系投稿",
        "tone":       "美容業界の嘘・盲点・コスパ最悪な習慣を毒舌で暴露する",
        "hook_types": ["expose", "cospa", "ranking", "comparison"],
        "hashtags":   "#美容の嘘 #スキンケア #コスパ最強 #skincare #美肌",
    },
    "evening": {
        "label":      "夜のゴールデンタイム向け体験・数字・比較投稿",
        "tone":       "夜のスキンケアに役立つ具体的な成分・製品情報をガチ勢目線で解説",
        "hook_types": ["number", "experience", "comparison", "reverse"],
        "hashtags":   "#夜スキンケア #美容液 #エイジングケア #skincare #保湿",
    },
}

# ── プロンプトテンプレート ─────────────────────────────────────────────────────

_RULES = """\
【絶対ルール】
・断言口調（「〜だと思います」禁止。「〜だ」「〜しろ」「〜して」で断言）
・絵文字は0〜1個まで（多いと信頼感が下がる）
・200〜280文字（ハッシュタグ・URLは含めない）
・具体的な成分名・数値・価格を必ず1つ以上含める
・「なんとなく」「〜らしい」禁止

【禁止ワード】
・「〜かもしれません」「〜と言われています」「〜ではないでしょうか」
・「ぜひ」「〜してみてください」「〜しましょう」（上から目線になる）
・根拠のない断言（成分名・数値・製品名で根拠を示す）

【参考キーワード（自然に1〜2個盛り込む）】
{keywords}

投稿テキストのみ出力してください。前置き・説明・「」の括りは一切不要です。"""

PROMPT_LIST = """\
あなたは美容の裏事情を知っている、少し毒舌な男性スキンケアアカウントです。

【ターゲット読者】美意識が高い男性。スクロールを止めて「保存したくなる」情報を求めている人。

【この投稿の役割】{label}
【トーン】{tone}

【構成（厳守）】
1行目（そのまま使う）:
{hook}

中盤: 箇条書き（・）または番号リスト（1. 2. 3.）で3〜5項目
・各項目に成分名・数値・価格・使用期間のいずれかを必ず含める
・読んだ後に「保存しておこう」と思わせる情報密度にする

末尾CTA（そのまま使う）:
{cta}

""" + _RULES

PROMPT_PARAGRAPH = """\
あなたは美容の裏事情を知っている、少し毒舌な男性スキンケアアカウントです。

【ターゲット読者】美意識が高い男性。「これ俺じゃん」と共感して拡散したくなる人。

【この投稿の役割】{label}
【トーン】{tone}

【構成（厳守）】
1行目（そのまま使う）:
{hook}

中盤: 体験談・本音口調のストーリーで語る
・「知らなかった」と感じる具体的な情報（成分名・数値・価格を必ず含める）
・共感を生む失敗談か、意外性のある事実を入れる
・「なるほど」と思わせて最後まで読ませる

末尾CTA（そのまま使う）:
{cta}

""" + _RULES


# ── ヘルパー ───────────────────────────────────────────────────────────────────

def _build_hook(slot: str) -> str:
    config     = SLOT_CONFIG.get(slot, SLOT_CONFIG["evening"])
    hook_type  = random.choice(config["hook_types"])
    templates  = HOOK_BANK.get(hook_type, HOOK_BANK["expose"])
    template   = random.choice(templates)
    try:
        hook = template.format(**{k: random.choice(v) for k, v in HOOK_VARS.items()})
    except KeyError:
        hook = template
    return hook


# ── メイン関数 ────────────────────────────────────────────────────────────────

def generate_post(
    slot: str,
    trend_keywords: Optional[List[str]] = None,
    api_key: Optional[str] = None,
    style: str = "list",
) -> Optional[str]:
    """
    Gemini API でスロットに合わせた美容投稿テキストを生成する。

    Args:
        slot:           "morning" | "noon" | "evening"
        trend_keywords: Googleトレンドから取得したキーワードのリスト
        api_key:        Gemini API キー（省略時は GEMINI_API_KEY 環境変数）
        style:          "list" | "paragraph"（A/Bテスト用）

    Returns:
        生成された投稿テキスト。失敗時は None。
    """
    try:
        import google.generativeai as genai
    except ImportError:
        log.error("google-generativeai 未インストール: pip install google-generativeai")
        return None

    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        log.error("GEMINI_API_KEY が設定されていません")
        return None

    config       = SLOT_CONFIG.get(slot, SLOT_CONFIG["evening"])
    keywords     = trend_keywords or []
    keywords_str = "、".join(keywords[:6]) if keywords else "特になし"
    hook         = _build_hook(slot)
    cta          = random.choice(CTA_POOL)

    template = PROMPT_LIST if style == "list" else PROMPT_PARAGRAPH
    prompt = template.format(
        label=config["label"],
        tone=config["tone"],
        hook=hook,
        cta=cta,
        keywords=keywords_str,
    )

    try:
        genai.configure(api_key=key)
        model    = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        text     = response.text.strip()
        log.info(f"Gemini生成完了: {len(text)}文字 / slot={slot} / style={style}")
        return text
    except Exception as e:
        log.error(f"Gemini API エラー: {e}")
        return None
