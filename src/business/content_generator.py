"""
business/content_generator.py — @claude_1706 収益化版コンテンツ生成

投稿スケジュール: 1日3回（8:00 / 12:00 / 22:00 JST）
アフィリ振り分け:
  - 月曜8時 / 金曜8時   → ココナラ（E）
  - 水曜22時 / 日曜22時  → Midworks（F）
  - それ以外             → 情報提供 A/B/C/D/G からランダム（連続防止）

投稿タイプ:
  A = result       数字つき成果投稿
  B = howto        具体手順投稿
  C = failure      失敗談・やって無駄だったこと
  D = tool_review  AIツール比較・使用感
  G = prompt_share コピペできるプロンプト共有
  E = coconala     ココナラアフィリ
  F = midworks     Midworksアフィリ

品質ルール:
  - 1行目は数字または具体的な結果から始める
  - 抽象語・汎用AI文禁止
  - 80〜280文字（本文）
  - ハッシュタグは最大3個
"""

import json
import logging
import os
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

# 投稿タイプ定義
POST_TYPES = ["result", "howto", "failure", "tool_review", "prompt_share"]
INFO_PATTERNS = ["A", "B", "C", "D", "G"]

# 禁止汎用文
BANNED_PHRASES = [
    "AIを活用しましょう",
    "副業におすすめ",
    "効率化できます",
    "これからの時代",
    "誰でも簡単",
    "ぜひ活用",
    "革命的",
    "大注目",
]


# ── 曜日＋時刻でパターン決定 ─────────────────────────────────────────────────

def _get_pattern_for(hour: int, weekday: int) -> str:
    """weekday: 月=0 火=1 水=2 木=3 金=4 土=5 日=6"""
    if weekday in (0, 4) and hour == 8:
        return "E"
    elif weekday in (2, 6) and hour == 22:
        return "F"
    else:
        last = _load_last_info_pattern()
        choices = [p for p in INFO_PATTERNS if p != last]
        pattern = random.choice(choices)
        _save_last_info_pattern(pattern)
        return pattern

def _get_next_pattern() -> str:
    now = datetime.now(JST)
    return _get_pattern_for(now.hour, now.weekday())

def pattern_to_post_type(pattern: str) -> str:
    return {
        "A": "result",
        "B": "howto",
        "C": "failure",
        "D": "tool_review",
        "G": "prompt_share",
        "E": "coconala",
        "F": "midworks",
    }.get(pattern, "result")


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


# ── ハッシュタグ（最大2〜3個、連続防止） ──────────────────────────────────────

HASHTAG_SETS = [
    "#AI活用 #副業",
    "#個人開発 #AI活用",
    "#副業 #個人開発",
    "#AI活用 #フリーランス",
    "#副業 #自動化",
    "#個人開発 #副業収入",
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

def _count_hashtags(text: str) -> int:
    return len(re.findall(r'#\S+', text))


# ── 品質チェック関数 ─────────────────────────────────────────────────────────

def _quality_check(text: str) -> tuple:
    """Returns: (ok: bool, reason: str)"""
    if not text or not text.strip():
        return False, "空テキスト"

    body = text.strip()
    body_no_tags = re.sub(r'\n?#\S+', '', body).strip()
    char_count = len(body_no_tags)

    if char_count < 80:
        return False, f"文字数不足: {char_count}文字"
    if char_count > 280:
        return False, f"文字数超過: {char_count}文字"

    tag_count = _count_hashtags(body)
    if tag_count > 3:
        return False, f"ハッシュタグ過多: {tag_count}個"

    for phrase in BANNED_PHRASES:
        if phrase in body:
            return False, f"禁止汎用文: 「{phrase}」"

    return True, "OK"


# ── アフィリ訴求文テンプレート ────────────────────────────────────────────────

COCONALA_TEMPLATES = [
    "Claude Codeで作ったシステム、売れるか試してる\n\nココナラで「AI自動化」「プロンプト設計」系の出品見たら\n個人でもちゃんと売れてる。登録無料で出品もできる\n\nまずは案件眺めるだけでも相場感つかめる\n👉 {COCONALA_AFFILIATE_URL}\n\n#副業 #AI活用",
    "副業でAIスキルを売るって、現実的だなと思った\n\nココナラで「ChatGPT活用」「Claude」で検索すると\n個人がちゃんと稼いでる。登録と出品は完全無料\n\n自分のスキルの値付け参考にもなる\n👉 {COCONALA_AFFILIATE_URL}\n\n#副業収入 #AI活用",
]

MIDWORKS_TEMPLATES = [
    "AIエンジニア、本気で足りてないらしい\n\nMidworksの案件一覧見たら\nPython × LLM案件で月80万〜普通にある\nClaude API使える人材、超需要ある\n\n経験浅くても登録だけしておくと相場感わかる\n👉 {MIDWORKS_AFFILIATE_URL}\n\n#フリーランス #AI活用",
    "フリーランスエンジニアの単価、思ったより高い\n\nMidworks見てたら\nAI・機械学習案件で月単価80万超がゴロゴロ\n正社員やってるの馬鹿らしくなる水準\n\n独立検討してる人は見る価値あり\n👉 {MIDWORKS_AFFILIATE_URL}\n\n#フリーランス #個人開発",
]


# ── フォールバック投稿（品質条件クリア済み） ─────────────────────────────────

FALLBACK_INFO = {
    "A": "3日で小さいWebアプリを1本作って分かったこと\n\n最初にやるべきなのは機能追加じゃなく、誰に売るかを決めること\n作る前に1人へDMするだけで、無駄な開発がかなり減る\n\n今週試してみる価値はある",

    "B": "AI投稿を自動化した手順、3ステップで書く\n\n1. Groq APIで文章生成（無料枠あり）\n2. GitHub Actionsで定時実行（無料）\n3. Threads Graph APIで投稿\n\n全部無料で動いてる。サーバーコストゼロ",

    "C": "1ヶ月やって分かった、やらなくてよかったこと\n\nChatGPTとClaudeを同時に使い比べるのは無駄だった\n切り替えのコストが思ったより大きくて、どっちも中途半端になった\n\n1つに絞った方が同じ時間で3倍進む",

    "D": "Groq APIを使い始めて1週間\n\n良い点：レスポンスが速い、無料枠が現実的\n弱点：長文が途中で切れることがある、日本語精度がClaude比で落ちる\n\n短文生成には十分使える。長文はClaudeの方が安定してる",

    "G": "コピペで使えるプロンプト\n\n「以下の文章をThreads向けに120文字以内で書き直してください。1行目は数字か具体的な結果から始めること。ハッシュタグは不要」\n\nこれだけで汎用AI文がかなりマシになる",
}


# ── プロンプト定義 ─────────────────────────────────────────────────────────────

PATTERN_PROMPTS = {
    "A": """\
以下の条件でThreads投稿を書いてください。

投稿タイプ: result（数字つき成果投稿）

必須ルール:
・1行目は必ず数字または具体的な結果から始める（例:「3日で」「月¥0→¥12,000」「1日3投稿」）
・金額、時間、件数などの数字を必ず1つ入れる
・体験談として書く（一人称は「自分」か主語省略）
・読者が今日すぐできる行動を1つだけ最後に入れる
・120〜180文字（ハッシュタグ除く）
・「AIを活用しましょう」「副業におすすめ」などの汎用文禁止
・煽りすぎない、等身大で
・ハッシュタグは書かない（別途付与します）
・投稿テキストのみ出力してください""",

    "B": """\
以下の条件でThreads投稿を書いてください。

投稿タイプ: howto（具体手順投稿）

必須ルール:
・1行目は具体的な結果または数字から始める
・手順を2〜3ステップで書く（番号付き箇条書き）
・再現性を重視する（ツール名・サービス名を具体的に書く）
・読者が今日すぐ試せる内容にする
・120〜180文字（ハッシュタグ除く）
・「簡単にできます」「AIで効率化」のような汎用文禁止
・ハッシュタグは書かない（別途付与します）
・投稿テキストのみ出力してください""",

    "C": """\
以下の条件でThreads投稿を書いてください。

投稿タイプ: failure（失敗談・やって無駄だったこと）

必須ルール:
・1行目に「やらなくてよかったこと」「無駄だった」「失敗した」などの結果から入る
・具体的に何をやって、何が無駄だったかを書く
・失敗から得た学びで終わらせる（前向きな着地）
・強がらない。ただし自虐的になりすぎない
・120〜180文字（ハッシュタグ除く）
・ハッシュタグは書かない（別途付与します）
・投稿テキストのみ出力してください""",

    "D": """\
以下の条件でThreads投稿を書いてください。

投稿タイプ: tool_review（AIツール比較・使用感）

必須ルール:
・1行目にツール名と具体的な評価から始める
・ツール名を1つだけ出す（Groq, Claude, ChatGPT, Cursor, Perplexity等）
・良い点を1つ、弱点を1つ必ず入れる
・自分の使用体験として書く
・「おすすめです」「便利です」のような汎用評価禁止
・120〜180文字（ハッシュタグ除く）
・ハッシュタグは書かない（別途付与します）
・投稿テキストのみ出力してください""",

    "G": """\
以下の条件でThreads投稿を書いてください。

投稿タイプ: prompt_share（コピペできるプロンプト共有）

必須ルール:
・1行目に「コピペで使えるプロンプト」「保存推奨」など保存されやすい文言を入れる
・短いプロンプト例を本文に入れる（引用符または改行で分かりやすく）
・そのプロンプトで何ができるか1行で説明する
・120〜180文字（ハッシュタグ除く）
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


# ── メイン生成関数 ────────────────────────────────────────────────────────────

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
    post_type = pattern_to_post_type(pattern)
    log.info(f"投稿パターン: {pattern} / タイプ: {post_type} (JST {now.strftime('%a %H:%M')})")

    prompt = _replace_urls(PATTERN_PROMPTS[pattern])
    hashtags = _get_hashtags()

    # 最大3回リトライ（品質チェック失敗時）
    for attempt in range(3):
        try:
            client = Groq(api_key=key)
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
            )
            body = response.choices[0].message.content.strip()
            body = _replace_urls(body)
            text = f"{body}\n\n{hashtags}"

            ok, reason = _quality_check(text)
            if ok:
                log.info(f"Groq生成完了 (attempt {attempt+1}): {len(text)}文字 / タイプ: {post_type}")
                return text
            else:
                log.warning(f"品質チェックNG (attempt {attempt+1}): {reason}")
        except Exception as e:
            log.error(f"Groq API エラー (attempt {attempt+1}): {e}")
            break

    log.warning("全attempt失敗 → fallbackを使用")
    return None


def get_fallback_post() -> str:
    now = datetime.now(JST)
    pattern = _get_pattern_for(now.hour, now.weekday())

    if pattern == "E":
        return _replace_urls(random.choice(COCONALA_TEMPLATES))
    elif pattern == "F":
        return _replace_urls(random.choice(MIDWORKS_TEMPLATES))
    else:
        body = FALLBACK_INFO[pattern]
        hashtags = _get_hashtags()
        return _replace_urls(f"{body}\n\n{hashtags}")


# ── ローカルテスト ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    os.environ.setdefault("COCONALA_AFFILIATE_URL", "https://coconala.example.com/?ref=test")
    os.environ.setdefault("MIDWORKS_AFFILIATE_URL", "https://midworks.example.com/?ref=test")

    print("=" * 50)
    print("【1. パターン振り分けテスト】")
    CASES = [
        ("月曜8時",  0, 8,  "E",    "ココナラ"),
        ("金曜8時",  4, 8,  "E",    "ココナラ"),
        ("水曜22時", 2, 22, "F",    "Midworks"),
        ("日曜22時", 6, 22, "F",    "Midworks"),
        ("火曜12時", 1, 12, "info", "情報提供"),
        ("土曜8時",  5, 8,  "info", "情報提供"),
    ]
    all_ok = True
    for label, wd, hr, expected_type, expected_label in CASES:
        pattern = _get_pattern_for(hr, wd)
        ok = (pattern == expected_type) if expected_type in ("E", "F") else (pattern in INFO_PATTERNS)
        mark = "✅" if ok else "❌"
        if not ok:
            all_ok = False
        print(f"{mark} {label} → {pattern} ({pattern_to_post_type(pattern)}) ／ 期待:{expected_label}")
    print("✅ 全振り分けOK" if all_ok else "❌ 振り分けNG")

    print()
    print("=" * 50)
    print("【2. 全タイプ fallback 品質チェック】")
    for p in INFO_PATTERNS:
        body = FALLBACK_INFO[p]
        hashtags = _get_hashtags()
        text = f"{body}\n\n{hashtags}"
        ok, reason = _quality_check(text)
        tag_count = _count_hashtags(text)
        body_len = len(re.sub(r'\n?#\S+', '', text).strip())
        mark = "✅" if ok else "❌"
        print(f"{mark} {p} ({pattern_to_post_type(p)}): {body_len}文字 タグ{tag_count}個 → {reason}")

    print()
    print("=" * 50)
    print("【3. fallback 投稿プレビュー（全5タイプ）】")
    for p in INFO_PATTERNS:
        body = FALLBACK_INFO[p]
        hashtags = _get_hashtags()
        text = f"{body}\n\n{hashtags}"
        print(f"\n--- {p} ({pattern_to_post_type(p)}) ---")
        print(text)
