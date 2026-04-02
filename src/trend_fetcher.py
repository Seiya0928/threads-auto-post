"""
trend_fetcher.py — スキンケア・美容系の投稿テキストを生成する

Threads APIにはトレンド取得機能がないため、
季節・曜日に合わせたスキンケアコンテンツを自動選択する。
"""

import random
from datetime import datetime


SKINCARE_CONTENT = {
    "morning": [
        "朝のスキンケアルーティン🌿 洗顔→化粧水→美容液→乳液の順番が大切。\n\n今日も丁寧に肌と向き合う朝。",
        "紫外線対策は365日。曇りの日でもUVケアを忘れずに🌤️",
        "朝の保湿が一日の肌コンディションを決める。水分補給をしっかり✨",
    ],
    "evening": [
        "夜のスキンケアは肌の再生タイム🌙 クレンジングは優しく丁寧に。",
        "今夜はスペシャルケアの日。シートマスクでしっかり保湿💆‍♀️",
        "肌の修復は睡眠中に行われる。良質な睡眠と保湿でエイジングケア🌛",
    ],
    "weekly": [
        "週に1〜2回のスクラブケアで毛穴の汚れをオフ🫧 つるつる肌を目指して。",
        "週末は集中保湿ケアの日✨ パックをしながらゆっくりリラックス。",
        "定期的なフェイスマッサージで血行促進💆‍♀️ むくみ顔にサヨナラ。",
    ],
    "seasonal": [
        "季節の変わり目は肌荒れしやすい時期。バリア機能を高めるセラミド成分を意識して🍃",
        "乾燥が気になる季節は重ね付け保湿がカギ🌿 化粧水を手で優しく押さえ込んで。",
        "湿度が高い季節はさっぱり系スキンケアで毛穴ケアを忘れずに☀️",
    ],
}

HASHTAG_SETS = [
    "#スキンケア #美容 #skincare #美肌 #保湿",
    "#美容 #スキンケア #美肌ケア #エイジングケア #毛穴ケア",
    "#skincare #beautytips #スキンケア #肌活 #美容好き",
    "#日本のスキンケア #スキンケア好き #美肌 #保湿ケア #美容routine",
]


def build_post_text(base_hashtags: str = "") -> str:
    """
    時間帯・曜日に合わせたスキンケアテキストとハッシュタグを組み合わせて返す。
    """
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()  # 0=月曜 〜 6=日曜

    if weekday >= 5:  # 土日
        category = "weekly"
    elif 5 <= hour < 12:
        category = "morning"
    elif 17 <= hour:
        category = "evening"
    else:
        category = "seasonal"

    body = random.choice(SKINCARE_CONTENT[category])
    hashtags = base_hashtags or random.choice(HASHTAG_SETS)

    text = f"{body}\n\n{hashtags}"

    if len(text) > 500:
        text = text[:497] + "..."

    return text


if __name__ == "__main__":
    for _ in range(3):
        print(build_post_text())
        print("---")
