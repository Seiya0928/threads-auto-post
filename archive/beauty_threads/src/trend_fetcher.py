"""
trend_fetcher.py — Google Trends から美容系トレンドキーワードを取得する

pytrends（非公式・無料・APIキー不要）を使用。
取得失敗時はフォールバックキーワードを返す。
"""

import logging
import random
from datetime import datetime
from typing import List

log = logging.getLogger(__name__)

FALLBACK_KEYWORDS = [
    ["セラミド", "バリア機能", "インナードライ"],
    ["レチノール", "エイジングケア", "ターンオーバー"],
    ["ナイアシンアミド", "毛穴", "美白"],
    ["日焼け止め", "UV", "紫外線対策"],
    ["クレンジング", "毛穴洗浄", "皮脂"],
    ["化粧水", "浸透", "重ね付け"],
]

BEAUTY_SEEDS = ["スキンケア", "美容液", "日焼け止め", "保湿クリーム"]


def fetch_beauty_trends() -> List[str]:
    """
    Google Trends から美容系トレンドキーワードを取得する。
    失敗時はフォールバックキーワードを返す。
    """
    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="ja-JP", tz=540, timeout=(10, 25))
        pytrends.build_payload(
            kw_list=BEAUTY_SEEDS[:3],
            timeframe="now 1-d",
            geo="JP",
        )
        related = pytrends.related_queries()

        keywords = []
        for kw_data in related.values():
            top = kw_data.get("top")
            if top is not None and not top.empty:
                keywords.extend(top["query"].tolist()[:3])

        if keywords:
            log.info(f"トレンド取得成功: {keywords[:6]}")
            return keywords[:6]
        else:
            raise ValueError("トレンドデータが空")

    except Exception as e:
        log.warning(f"Googleトレンド取得失敗 → フォールバック使用: {e}")
        return random.choice(FALLBACK_KEYWORDS)


def get_slot_from_jst_hour(jst_hour: int) -> str:
    """JST時刻から投稿スロットを判定する"""
    if 5 <= jst_hour < 11:
        return "morning"
    elif 11 <= jst_hour < 17:
        return "noon"
    else:
        return "evening"


HASHTAG_SETS = {
    "morning": "#スキンケア #朝活 #美肌ルーティン #skincare #美容男子",
    "noon":    "#美容の嘘 #スキンケア #コスパ最強 #skincare #美肌",
    "evening": "#夜スキンケア #美容液 #エイジングケア #skincare #保湿",
}


def build_post_text(base_hashtags: str = "") -> str:
    """後方互換用: スロットに合わせたハッシュタグのみ返す（旧poster.py呼び出し用）"""
    now = datetime.now()
    jst_hour = (now.hour + 9) % 24
    slot = get_slot_from_jst_hour(jst_hour)
    return base_hashtags or HASHTAG_SETS.get(slot, HASHTAG_SETS["evening"])
