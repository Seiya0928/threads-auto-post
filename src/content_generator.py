"""
content_generator.py — Gemini API でバズる美容投稿を動的生成する

無料枠: gemini-1.5-flash
  - 15 requests/minute
  - 1,500 requests/day
"""

import os
import logging
from typing import Optional, List

log = logging.getLogger(__name__)

SLOT_CONFIG = {
    "morning": {
        "label": "朝のルーティン投稿",
        "tone": "朝の忙しい時間に刺さる、すぐ実践できる時短スキンケアtips",
        "hook": "「今日の肌の出来は朝で決まる」という切り口で惹きつける",
    },
    "noon": {
        "label": "昼の毒舌暴露投稿",
        "tone": "美容業界の嘘・盲点・コスパ最悪な習慣を毒舌で暴露する",
        "hook": "「それ、騙されてますよ」という切り口で惹きつける",
    },
    "evening": {
        "label": "夜のガチ解説投稿",
        "tone": "夜のゴールデンタイムに行うべき本格スキンケアをガチ勢目線で解説",
        "hook": "「寝る前のこれで差がつく」という切り口で惹きつける",
    },
}

PROMPT_TEMPLATE = """\
あなたはスキンケアの裏事情を知っている、少し毒舌なビューティーインフルエンサーです。

【ターゲット読者】
- 美意識が高い男性（夜職・モデル・芸能関係者含む）
- 本気で肌質改善したい人
- 一般論ではなくリアルな情報を求めている人

【この投稿の役割】{label}
【トーン】{tone}

【構成ルール（厳守）】
・1行目: {hook}
・中盤: 読者が「知らなかった」と感じる具体的な有益情報（数値・成分名・体験談を含める）
・最後: 「わかる」「これ俺じゃん」と思わせる共感フレーズで締める

【文体ルール】
・断言口調（「〜だと思います」禁止。「〜だった」「〜です」「〜しろ」で断言）
・体験談・本音口調
・絵文字は1〜2個まで
・200〜280文字（Threadsの最適文字数）
・ハッシュタグ不要（後で自動付与するため含めない）
・URLは含めない

【参考トレンドキーワード（自然に盛り込む）】
{keywords}

投稿テキストのみ出力してください。前置き・説明・「」の括りは一切不要です。\
"""


def generate_post(
    slot: str,
    trend_keywords: Optional[List[str]] = None,
    api_key: Optional[str] = None,
) -> Optional[str]:
    """
    Gemini API でスロットに合わせた投稿テキストを生成する。

    Args:
        slot: "morning" | "noon" | "evening"
        trend_keywords: Googleトレンドから取得したキーワードのリスト
        api_key: Gemini API キー（省略時は GEMINI_API_KEY 環境変数）

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

    config = SLOT_CONFIG.get(slot, SLOT_CONFIG["evening"])
    keywords_str = "、".join(trend_keywords[:6]) if trend_keywords else "特になし"

    prompt = PROMPT_TEMPLATE.format(
        label=config["label"],
        tone=config["tone"],
        hook=config["hook"],
        keywords=keywords_str,
    )

    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        text = response.text.strip()
        log.info(f"Gemini生成完了: {len(text)}文字 / slot={slot}")
        return text
    except Exception as e:
        log.error(f"Gemini API エラー: {e}")
        return None
