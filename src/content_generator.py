"""
content_generator.py — Gemini API でバズる美容投稿を動的生成する

スタイル:
  - 'list'      : 箇条書き・番号リスト（保存されやすい）
  - 'paragraph' : 文章体（共感・ストーリー）

A/Bテストで両スタイルのパフォーマンスを計測し、勝ちスタイルを優先する。
"""

import logging
import os
import random
from typing import List, Optional

log = logging.getLogger(__name__)

# ── 1行目テンプレート（結論ファースト）─────────────────────────────────────

HOOK_TEMPLATES = {
    "comparison": "【成分比較】{A}と{B}、どっちが{metric}",
    "myth":       "【意外な事実】実はNGなスキンケア習慣{n}選",
    "timesave":   "【時短美容】忙しい{timing}にこれだけはやっておけ",
}

COMPARISON_METRICS = ["コスパ良い？", "効果高い？", "肌に優しい？"]

# ── CTA候補 ──────────────────────────────────────────────────────────────────

CTA_POOL = [
    "これ使ったことある人いる？",
    "みんなの推し保湿クリームは何？",
    "洗顔何使ってる？教えて。",
    "朝のスキンケア、何分かけてる？",
    "同じ悩みの人いたら教えて。",
    "あなたの推し成分、何？",
    "乳液派？クリーム派？どっち？",
]

# ── スロット別設定 ────────────────────────────────────────────────────────────

SLOT_CONFIG = {
    "morning": {
        "label": "朝の準備時間（7〜8時台）向け投稿",
        "tone":  "朝の忙しい時間に刺さる、今日からできる時短スキンケアtips",
        "hook_type": "timesave",
        "timing": "朝",
    },
    "noon": {
        "label": "昼の毒舌暴露投稿",
        "tone":  "美容業界の嘘・盲点・コスパ最悪な習慣を毒舌で暴露する",
        "hook_type": "myth",
        "timing": "昼",
    },
    "evening": {
        "label": "夜のゴールデンタイム（21〜23時台）向け投稿",
        "tone":  "夜のゴールデンタイムに行うべき本格スキンケアをガチ勢目線で解説",
        "hook_type": "comparison",
        "timing": "夜",
    },
}

# ── プロンプトテンプレート ────────────────────────────────────────────────────

_COMMON_RULES = """\
【文体ルール】
・断言口調（「〜だと思います」禁止。「〜だ」「〜しろ」で断言）
・絵文字は1〜2個まで
・200〜300文字（ハッシュタグ・URLは含めない）

【参考トレンドキーワード（自然に盛り込む）】
{keywords}

投稿テキストのみ出力してください。前置き・説明・「」の括りは一切不要です。"""

PROMPT_LIST = """\
あなたはスキンケアの裏事情を知っている、少し毒舌なビューティーインフルエンサーです。

【ターゲット読者】美意識が高い男性。保存して後で見返したい人。

【この投稿の役割】{label}
【トーン】{tone}

【必須構成（厳守）】
1行目（そのまま使う）:
{hook}

中盤: 以下のどちらかで情報を構造化する
  ・箇条書き（・）で3〜5項目
  または
  1. 2. 3. の番号リストで3〜4項目
各項目に成分名（セラミド・ナイアシンアミド・レチノール・ビタミンCなど）や
数値（濃度%・価格・使用日数・温度など）を必ず1つ以上含める。

末尾CTA（そのまま使う）:
{cta}

""" + _COMMON_RULES

PROMPT_PARAGRAPH = """\
あなたはスキンケアの裏事情を知っている、少し毒舌なビューティーインフルエンサーです。

【ターゲット読者】美意識が高い男性。「これ俺じゃん」と共感して保存したくなる人。

【この投稿の役割】{label}
【トーン】{tone}

【必須構成（厳守）】
1行目（そのまま使う）:
{hook}

中盤: 体験談・本音口調のストーリーで語る
・「知らなかった」と感じる具体的な情報（成分名・数値・価格を必ず含める）
・「なんとなく」禁止。根拠を示す。

末尾CTA（そのまま使う）:
{cta}

""" + _COMMON_RULES


# ── ヘルパー ──────────────────────────────────────────────────────────────────

def _build_hook(config: dict, keywords: List[str]) -> str:
    hook_type = config.get("hook_type", "myth")
    timing    = config.get("timing", "朝")
    kw1 = keywords[0] if keywords else "セラミド"
    kw2 = keywords[1] if len(keywords) > 1 else "ナイアシンアミド"

    if hook_type == "timesave":
        return HOOK_TEMPLATES["timesave"].format(timing=timing)
    elif hook_type == "comparison":
        return HOOK_TEMPLATES["comparison"].format(
            A=kw1, B=kw2, metric=random.choice(COMPARISON_METRICS)
        )
    else:
        return HOOK_TEMPLATES["myth"].format(n=random.choice([3, 4, 5]))


# ── メイン関数 ────────────────────────────────────────────────────────────────

def generate_post(
    slot: str,
    trend_keywords: Optional[List[str]] = None,
    api_key: Optional[str] = None,
    style: str = "list",
) -> Optional[str]:
    """
    Gemini API でスロットに合わせた投稿テキストを生成する。

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
    hook         = _build_hook(config, keywords)
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
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        text = response.text.strip()
        log.info(f"Gemini生成完了: {len(text)}文字 / slot={slot} / style={style}")
        return text
    except Exception as e:
        log.error(f"Gemini API エラー: {e}")
        return None
