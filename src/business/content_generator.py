"""
business/content_generator.py — @claude_1706 収益化版コンテンツ生成

投稿スケジュール: 1日3回（8:00 / 12:00 / 22:00 JST）
アフィリ振り分け:
  - 月曜8時 / 金曜8時   → ココナラ（E）
  - 水曜22時 / 日曜22時  → Midworks（F）
  - それ以外             → 情報提供 A/B/C/D からランダム

シャドウバン回避:
  - ハッシュタグは3つまで、同じ組み合わせ連続禁止
  - 誇大表現・上から目線禁止
"""

import json
import logging
import os
import random
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")


# ── 曜日＋時刻でパターン決定 ─────────────────────────────────────────────────

def _get_pattern_for(hour: int, weekday: int) -> str:
    """
    曜日＋時刻でパターンを決定。
    weekday: 月=0, 火=1, 水=2, 木=3, 金=4, 土=5, 日=6
    """
    # ココナラ：月曜8時 / 金曜8時
    if weekday in (0, 4) and hour == 8:
        return "E"
    # Midworks：水曜22時 / 日曜22時
    elif weekday in (2, 6) and hour == 22:
        return "F"
    # それ以外：情報提供 A/B/C/D
    else:
        last = _load_last_info_pattern()
        choices = [p for p in ["A", "B", "C", "D"] if p != last]
        pattern = random.choice(choices)
        _save_last_info_pattern(pattern)
        return pattern

def _get_next_pattern() -> str:
    now = datetime.now(JST)
    return _get_pattern_for(now.hour, now.weekday())


# ── 情報投稿の直前パターン管理（連続防止） ────────────────────────────────────

_LAST_INFO_FILE = Path(__file__).parent.parent.parent / "data" / "business_last_info.json"

def _load_last_info_pattern() -> str:
    if _LAST_INFO_FILE.exists():
        try:
            return json.loads(_LAST_INFO_FILE.read_text()).get("last", "")
        except Exception:
            pass
    return ""

def _save_last_info_pattern(pattern: str) -> None:
    _LAST_INFO_FILE.parent.mkdir(exist_ok=True)
    _LAST_INFO_FILE.write_text(json.dumps({"last": pattern}, ensure_ascii=False))


# ── ハッシュタグ ──────────────────────────────────────────────────────────────

HASHTAG_SETS = [
    "#副業 #AI活用 #朝活",
    "#副業収入 #自動化 #AI副業",
    "#フリーランス #在宅ワーク #副業",
    "#AI活用 #副業 #自動化",
    "#エンジニア #AI副業 #副業収入",
    "#朝活 #副業 #AI活用",
]

_LAST_HASHTAG_FILE = Path(__file__).parent.parent.parent / "data" / "business_last_hashtag.json"

def _get_hashtags() -> str:
    last = ""
    if _LAST_HASHTAG_FILE.exists():
        try:
            last = json.loads(_LAST_HASHTAG_FILE.read_text()).get("last", "")
        except Exception:
            pass
    choices = [h for h in HASHTAG_SETS if h != last]
    chosen = random.choice(choices)
    _LAST_HASHTAG_FILE.parent.mkdir(exist_ok=True)
    _LAST_HASHTAG_FILE.write_text(json.dumps({"last": chosen}, ensure_ascii=False))
    return chosen


# ── アフィリ訴求文テンプレート ────────────────────────────────────────────────

COCONALA_TEMPLATES = [
    "Claude Codeで作ったシステム、売れるか試してる\n\nココナラで「AI自動化」「プロンプト設計」系の出品見たら\n個人でもちゃんと売れてる。登録無料で出品もできる\n\nまずは案件眺めるだけでも相場感つかめる\n👉 {COCONALA_AFFILIATE_URL}\n\n#副業 #AI活用 #在宅ワーク",
    "副業でAIスキルを売るって、現実的だなと思った\n\nココナラで「ChatGPT活用」「Claude」で検索すると\n個人がちゃんと稼いでる。登録と出品は完全無料\n\n自分のスキルの値付け参考にもなる\n👉 {COCONALA_AFFILIATE_URL}\n\n#副業収入 #AI活用 #スキル販売",
]

MIDWORKS_TEMPLATES = [
    "AIエンジニア、本気で足りてないらしい\n\nMidworksの案件一覧見たら\nPython × LLM案件で月80万〜普通にある\nClaude API使える人材、超需要ある\n\n経験浅くても登録だけしておくと\n相場感わかって副業の値付けにも使える\n👉 {MIDWORKS_AFFILIATE_URL}\n\n#フリーランス #AI副業 #エンジニア",
    "フリーランスエンジニアの単価、思ったより高い\n\nMidworks見てたら\nAI・機械学習案件で月単価80万超がゴロゴロ\n正社員やってるの馬鹿らしくなる水準\n\n安心保証もあるらしいから、独立検討してる人は見る価値あり\n👉 {MIDWORKS_AFFILIATE_URL}\n\n#フリーランス #エンジニア副業 #独立",
]


# ── 情報提供フォールバック ─────────────────────────────────────────────────────

FALLBACK_INFO = {
    "A": "Claude Codeで知って衝撃だったやつ\n\n/compact コマンドで会話を要約してくれる\n長いセッションでもコンテキスト溢れない\n\n最初これ知らなくて、毎回新規セッション立ち上げて\n同じこと説明してた時間返してほしい",
    "B": "AI副業始めて気づいたこと\n\n「Claude Codeが全部やってくれる」は嘘\n正確には「Claude Codeに的確に指示できる人が勝つ」\n\n最初の3週間、指示がぼんやりすぎて\n何回もやり直しさせてた。これ自分の問題だった",
    "C": "Threads自動投稿、無料で動いてる構成\n\n・Groq API（llama-3.3-70b）で本文生成\n・GitHub Actionsで定時実行\n・Threads Graph APIで投稿\n\nGemini無料枠429エラーで詰んで\nGroqに逃げたらむしろ速くて安定した",
    "D": "AI副業8週間経過の正直なとこ\n\n・収益：まだ0円\n・作ったもの：Webアプリ2つ、自動投稿システム2つ\n・スキル：明らかに上がってる\n・焦り：ある\n\n「稼げる」の前に「作れる」を先に積んでる感覚\nここが抜けると続かない気がしてる",
}


# ── プロンプト定義 ─────────────────────────────────────────────────────────────

PATTERN_PROMPTS = {
    "A": """\
「Claude Codeで知って衝撃だったやつ」という書き出しで始めて、
具体的なClaude Codeのコマンドや機能を1つ取り上げ、
知らなかった頃の自分の失敗談と組み合わせて投稿を書いてください。

ルール:
・一人称は「自分」か主語省略
・上から目線NG。等身大で。
・具体的な機能名・コマンドを必ず含める
・150〜280文字（ハッシュタグ除く）
・ハッシュタグは書かない（別途付与します）
・投稿テキストのみ出力してください""",

    "B": """\
「AI副業始めて気づいたこと」という書き出しで始めて、
逆張り気味の気づきと等身大の失敗談で共感を誘う投稿を書いてください。

ルール:
・一人称は「自分」か主語省略
・「絶対稼げる」「簡単に」などの誇大表現禁止
・失敗を隠さない。ただし前向きな着地
・150〜280文字（ハッシュタグ除く）
・ハッシュタグは書かない（別途付与します）
・投稿テキストのみ出力してください""",

    "C": """\
具体的なAI自動化の構成やスタックを紹介する投稿を書いてください。

構成例（参考）:
・使ったツール名を箇条書き
・つまずいたポイント
・結果どうなったか

ルール:
・一人称は「自分」か主語省略
・実在するツール名（GitHub Actions, Groq, Threads API等）を使う
・150〜280文字（ハッシュタグ除く）
・ハッシュタグは書かない（別途付与します）
・投稿テキストのみ出力してください""",

    "D": """\
「AI副業X週間経過の正直なとこ」という形式で、
数字で現在地を晒す進捗報告投稿を書いてください。

含める要素:
・収益（0円でも正直に）
・作ったもの（具体的に）
・スキルの変化
・正直な感情

ルール:
・強がらない。ただし前向き
・150〜280文字（ハッシュタグ除く）
・ハッシュタグは書かない（別途付与します）
・投稿テキストのみ出力してください""",

    "E": """\
ココナラでAI・自動化系のスキル販売を眺めた体験談から、
自然にココナラへの登録を勧める投稿を書いてください。

ルール:
・自分の行動起点から始める（「試してる」「眺めてみた」など）
・「個人でも売れてる」という発見の形式
・登録と出品が無料という事実を含める
・ソフトな誘導（押しつけない）
・末尾に「👉 {COCONALA_AFFILIATE_URL}」を含める
・200〜350文字（ハッシュタグ除く）
・ハッシュタグは書かない（別途付与します）
・投稿テキストのみ出力してください""",

    "F": """\
AIエンジニア・LLM活用人材の需要が高いという市場情報から、
自然にMidworksへの登録を勧める投稿を書いてください。

含める要素:
・Python × LLM案件の具体的な月収目安（月80万〜など）
・「登録だけでも相場感がわかる」という実利
・末尾に「👉 {MIDWORKS_AFFILIATE_URL}」を含める

ルール:
・市場の事実として伝える（成功保証しない）
・200〜350文字（ハッシュタグ除く）
・ハッシュタグは書かない（別途付与します）
・投稿テキストのみ出力してください""",
}


# ── URL置換ヘルパー ───────────────────────────────────────────────────────────

def _replace_urls(text: str) -> str:
    coconala_url = os.environ.get("COCONALA_AFFILIATE_URL", "[ココナラはプロフィールリンクから]")
    midworks_url = os.environ.get("MIDWORKS_AFFILIATE_URL", "[Midworksはプロフィールリンクから]")
    return text.replace("{COCONALA_AFFILIATE_URL}", coconala_url).replace("{MIDWORKS_AFFILIATE_URL}", midworks_url)


# ── メイン関数 ────────────────────────────────────────────────────────────────

def generate_post(
    slot: str,
    api_key: Optional[str] = None,
    affiliate_url: Optional[str] = None,
) -> Optional[str]:
    try:
        from groq import Groq
    except ImportError:
        log.error("groq 未インストール: pip install groq")
        return None

    key = api_key or os.environ.get("GROQ_API_KEY", "")
    if not key:
        log.error("GROQ_API_KEY が設定されていません")
        return None

    now = datetime.now(JST)
    pattern = _get_pattern_for(now.hour, now.weekday())
    log.info(f"投稿パターン: {pattern} (JST {now.strftime('%a %H:%M')})")

    prompt = _replace_urls(PATTERN_PROMPTS[pattern])
    hashtags = _get_hashtags()

    # アフィリ（E/F）はGroq生成 + ハッシュタグ付与
    # 情報提供（A-D）も同様
    try:
        client = Groq(api_key=key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
        )
        body = response.choices[0].message.content.strip()
        # E/FはURLを展開済みのプロンプトから生成されるが、念のため置換
        body = _replace_urls(body)
        # E/Fはハッシュタグ内蔵テンプレートなのでGroq出力にはハッシュタグなし → 付与
        text = f"{body}\n\n{hashtags}"
        log.info(f"Groq生成完了: {len(text)}文字 / slot={slot} / pattern={pattern}")
        return text
    except Exception as e:
        log.error(f"Groq API エラー: {e}")
        return None


def get_fallback_post() -> str:
    now = datetime.now(JST)
    pattern = _get_pattern_for(now.hour, now.weekday())

    if pattern == "E":
        body = random.choice(COCONALA_TEMPLATES)
    elif pattern == "F":
        body = random.choice(MIDWORKS_TEMPLATES)
    else:
        body = FALLBACK_INFO[pattern]
        hashtags = _get_hashtags()
        return _replace_urls(f"{body}\n\n{hashtags}")

    return _replace_urls(body)


# ── ローカルテスト ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.environ.setdefault("COCONALA_AFFILIATE_URL", "https://coconala.example.com/?ref=test")
    os.environ.setdefault("MIDWORKS_AFFILIATE_URL", "https://midworks.example.com/?ref=test")

    CASES = [
        ("月曜8時",   0, 8,  "E", "ココナラ"),
        ("金曜8時",   4, 8,  "E", "ココナラ"),
        ("水曜22時",  2, 22, "F", "Midworks"),
        ("日曜22時",  6, 22, "F", "Midworks"),
        ("火曜12時",  1, 12, "info", "情報提供"),
        ("土曜8時",   5, 8,  "info", "情報提供"),
    ]

    all_ok = True
    for label, wd, hr, expected_type, expected_label in CASES:
        pattern = _get_pattern_for(hr, wd)
        if expected_type == "E":
            ok = pattern == "E"
        elif expected_type == "F":
            ok = pattern == "F"
        else:
            ok = pattern in ("A", "B", "C", "D")

        mark = "✅" if ok else "❌"
        if not ok:
            all_ok = False
        print(f"{mark} {label} → パターン:{pattern} （期待:{expected_label}）")

        # 投稿内容プレビュー
        if pattern == "E":
            body = random.choice(COCONALA_TEMPLATES)
        elif pattern == "F":
            body = random.choice(MIDWORKS_TEMPLATES)
        else:
            body = FALLBACK_INFO[pattern]
        print(_replace_urls(body))
        print()

    print("=" * 40)
    print("✅ 全ケースOK" if all_ok else "❌ 一部NG")
