"""
business/content_generator.py — @claude_1706 収益化版コンテンツ生成

投稿スケジュール: 1日3回（09:00 / 15:00 / 21:00 JST）
アフィリ振り分け（比率ベース）:
  - 同日すでにアフィリ投稿済み → 必ず情報投稿
  - 直近4投稿にアフィリが含まれる → 情報投稿
  - 上記に該当しない場合、20%（5本に1本）の確率でアフィリ投稿
  - アフィリ種別はランダム（ococonala / midworks）

投稿タイプ:
  A = result       数字つき成果投稿
  B = howto        具体手順投稿
  C = failure      失敗談・やって無駄だったこと
  D = tool_review  AIツール比較・使用感
  G = prompt_share コピペできるプロンプト共有
  E = crowdworks   クラウドワークスアフィリ（体験→課題→解決→自然な紹介）
  F = midworks     Midworksアフィリ（体験→課題→解決→自然な紹介）

品質ルール:
  - 1行目は数字または具体的な結果から始める
  - 抽象語・汎用AI文禁止
  - 80〜280文字（本文）
  - ハッシュタグは最大2個
  - リンクのみの投稿禁止
  - 誇大表現禁止（絶対稼げる・誰でも簡単・放置で稼げる 等）
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

# 禁止汎用文（情報投稿 + アフィリ共通）
BANNED_PHRASES = [
    "AIを活用しましょう",
    "副業におすすめ",
    "効率化できます",
    "これからの時代",
    "誰でも簡単",
    "ぜひ活用",
    "革命的",
    "大注目",
    "絶対稼げる",
    "放置で稼げる",
    "誰でも稼げる",
    "簡単に稼げる",
]


# ── アフィリ比率チェック ───────────────────────────────────────────────────────

def _affiliate_allowed(log_entries: list) -> tuple:
    """
    Returns: (allowed: bool, service: 'coconala'|'midworks'|'')
    ルール:
    1. 同日すでにアフィリ投稿済み → 不可
    2. 直近4投稿にアフィリが含まれる → 不可
    3. 上記クリアで 20%（5本に1本）の確率で許可
    """
    today_str = datetime.now(JST).strftime("%Y-%m-%d")

    today_posts = [
        e for e in log_entries
        if e.get("posted_at", "")[:10] == today_str
    ]
    if any(e.get("is_affiliate", False) for e in today_posts):
        log.debug("アフィリ不可: 本日すでに投稿済み")
        return False, ""

    recent = log_entries[-4:] if len(log_entries) >= 4 else log_entries
    if any(e.get("is_affiliate", False) for e in recent):
        log.debug("アフィリ不可: 直近4投稿にアフィリあり")
        return False, ""

    if random.random() < 0.2:
        service = random.choice(["crowdworks", "midworks"])
        log.info(f"アフィリ投稿を選択: {service}")
        return True, service

    return False, ""


# ── パターン決定（比率ベース） ────────────────────────────────────────────────

def decide_post_pattern(log_entries: list) -> str:
    """
    ログを参照してアフィリ比率を守りながら次のパターンを返す。
    E = coconala / F = midworks / A B C D G = 情報投稿
    """
    allowed, service = _affiliate_allowed(log_entries)
    if allowed:
        return "E" if service == "crowdworks" else "F"

    last = _load_last_info_pattern()
    choices = [p for p in INFO_PATTERNS if p != last]
    pattern = random.choice(choices)
    _save_last_info_pattern(pattern)
    return pattern


# 後方互換（main_business.pyから呼ばれる場合のシム）
def _get_pattern_for(hour: int, weekday: int) -> str:
    """後方互換シム。decide_post_pattern を使うことを推奨。"""
    return decide_post_pattern([])

def pattern_to_post_type(pattern: str) -> str:
    return {
        "A": "result",
        "B": "howto",
        "C": "failure",
        "D": "tool_review",
        "G": "prompt_share",
        "E": "crowdworks",
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

CROWDWORKS_TEMPLATES = [
    "AI系の副業、最初の1件が一番難しかった\n\nクラウドワークスで「ChatGPT」「プロンプト」で検索したら\nAI系の案件が想像より多くて驚いた\n登録も応募も無料なので、まず相場を見るだけでも価値ある\n👉 {CROWDWORKS_AFFILIATE_URL}\n\n#副業 #AI活用",
    "スキルを売る前に、相場を知るのが先だと思った\n\nクラウドワークスでAI・自動化系の案件を眺めてみたら\n単価の幅が広くて、自分のレベルに合う仕事が見つかりやすい\n登録無料なので見るだけでも損はない\n👉 {CROWDWORKS_AFFILIATE_URL}\n\n#副業収入 #AI活用",
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

構成（この順番で書く）:
1行目: 「コピペで使えるプロンプト」「保存推奨」など保存を促す文言
2〜4行目: プロンプト本文（引用符またはかぎかっこで囲む、30〜60文字程度）
最後の1〜2行: そのプロンプトで何ができるか・使うとどう変わるかを具体的に説明

必須ルール:
・本文（ハッシュタグ除く）は必ず120文字以上180文字以下にすること
・プロンプト例だけで終わらず、使い方・効果の説明を必ず加える
・ツール名（ChatGPT・Claude・Gemini等）を1つ具体的に入れる
・「おすすめです」「便利です」などの汎用文禁止
・ハッシュタグは書かない（別途付与します）
・投稿テキストのみ出力してください""",

    "E": """\
以下の構成でThreads投稿を書いてください。

投稿タイプ: クラウドワークス紹介（体験→課題→解決→自然な紹介）

構成:
1行目: 数字または具体的な悩みから始める（例:「副業を始めて最初の1ヶ月、何から手をつけるか分からなかった」）
本文前半: 自分が抱えていた課題（AI副業の始め方・相場感がつかめない等）
本文後半: クラウドワークスでAI系案件を調べて分かった発見（案件数・単価・応募しやすさ等）
末尾: 自然に紹介し「👉 {CROWDWORKS_AFFILIATE_URL}」を含める

厳守ルール:
・「絶対稼げる」「誰でも簡単」「放置で稼げる」などの誇大表現は禁止
・リンクのみの投稿は禁止
・押しつけない、等身大で
・登録と応募が無料という事実を含める
・120〜200文字（ハッシュタグ除く）
・ハッシュタグは書かない（別途付与します）
・投稿テキストのみ出力してください""",

    "F": """\
以下の構成でThreads投稿を書いてください。

投稿タイプ: Midworks紹介（体験→課題→解決→自然な紹介）

構成:
1行目: 数字または具体的な悩みから始める（例:「正社員のまま副業、限界を感じた」）
本文前半: 自分が感じていた課題（収入の天井・スキルを活かせていない等）
本文後半: Midworksで案件相場を調べた体験・発見（Python×LLM案件の月単価など）
末尾: 「登録だけでも相場感がわかる」として自然に紹介し「👉 {MIDWORKS_AFFILIATE_URL}」を含める

厳守ルール:
・成功保証・誇大表現は禁止（「絶対稼げる」「誰でも」等）
・リンクのみの投稿は禁止
・市場の事実として伝える
・120〜200文字（ハッシュタグ除く）
・ハッシュタグは書かない（別途付与します）
・投稿テキストのみ出力してください""",
}


# ── URL置換ヘルパー ───────────────────────────────────────────────────────────

def _replace_urls(text: str) -> str:
    crowdworks_url = os.environ.get("CROWDWORKS_AFFILIATE_URL", "[クラウドワークスはプロフィールリンクから]")
    midworks_url = os.environ.get("MIDWORKS_AFFILIATE_URL", "[Midworksはプロフィールリンクから]")
    return (
        text
        .replace("{CROWDWORKS_AFFILIATE_URL}", crowdworks_url)
        .replace("{MIDWORKS_AFFILIATE_URL}", midworks_url)
    )


# ── メイン生成関数 ────────────────────────────────────────────────────────────

def generate_post(
    slot: str,
    api_key: Optional[str] = None,
    pattern: Optional[str] = None,
) -> Optional[str]:
    """
    pattern: 外部から渡す場合は decide_post_pattern() で決定したものを渡す。
             None の場合はログなしでパターンを内部決定する（後方互換）。
    GROQ_API_KEY が未設定の場合は None を返す（エラーで止まらない）。
    """
    key = api_key or os.environ.get("GROQ_API_KEY", "")
    if not key:
        log.warning("GROQ_API_KEY 未設定 → fallback を使用します")
        return None

    try:
        from groq import Groq
    except ImportError:
        log.error("groq 未インストール: pip install groq")
        return None

    if pattern is None:
        pattern = decide_post_pattern([])

    post_type = pattern_to_post_type(pattern)
    log.info(f"投稿パターン: {pattern} / タイプ: {post_type}")

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


def get_fallback_post(pattern: Optional[str] = None) -> str:
    """
    pattern: 外部から渡す場合は decide_post_pattern() で決定したものを渡す。
             None の場合はログなしでパターンを内部決定する（後方互換）。
    """
    if pattern is None:
        pattern = decide_post_pattern([])

    if pattern == "E":
        return _replace_urls(random.choice(CROWDWORKS_TEMPLATES))
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
