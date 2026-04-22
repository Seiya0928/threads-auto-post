"""
business/content_generator.py — @claude_1706 収益化版コンテンツ生成

投稿比率: 情報提供4本 : アフィリ1本（5投稿サイクル）
パターン:
  A: Claude Code Tips系
  B: 失敗談・リアル系
  C: 具体的な自動化手順系
  D: 等身大の感想系
  E: アフィリ（クラウドソーシング系）
  F: アフィリ（フリーランスエージェント系）

シャドウバン回避:
  - アフィリリンクは5投稿に1本のみ
  - ハッシュタグは3つまで、同じ組み合わせ連続禁止
  - 誇大表現・上から目線禁止
"""

import json
import logging
import os
import random
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ── 投稿サイクル管理 ─────────────────────────────────────────────────────────

_CYCLE_FILE = Path(__file__).parent.parent.parent / "data" / "business_cycle.json"

def _load_cycle() -> dict:
    if _CYCLE_FILE.exists():
        try:
            return json.loads(_CYCLE_FILE.read_text())
        except Exception:
            pass
    return {"count": 0, "last_pattern": ""}

def _save_cycle(data: dict) -> None:
    _CYCLE_FILE.parent.mkdir(exist_ok=True)
    _CYCLE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def _get_next_pattern() -> str:
    """5投稿サイクルでパターンを決定。5本目のみアフィリ（E or F）。"""
    cycle = _load_cycle()
    count = cycle.get("count", 0)
    pos = count % 5  # 0〜3: 情報提供、4: アフィリ

    if pos == 4:
        pattern = random.choice(["E", "F"])
    else:
        # A/B/C/Dを均等ローテ（連続しないように）
        last = cycle.get("last_pattern", "")
        choices = [p for p in ["A", "B", "C", "D"] if p != last]
        pattern = random.choice(choices)

    cycle["count"] = count + 1
    cycle["last_pattern"] = pattern
    _save_cycle(cycle)
    return pattern

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

# ── フォールバック投稿 ────────────────────────────────────────────────────────

FALLBACK_POSTS = {
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
クラウドワークスでAI・自動化系の案件を探したという体験談から、
自然にクラウドワークスへの登録を勧める投稿を書いてください。

ルール:
・自分の行動起点から始める
・「案件があった」という発見の形式
・ソフトな誘導（押しつけない）
・末尾に「👉 {AFFILIATE_URL}」を含める
・200〜350文字（ハッシュタグ除く）
・ハッシュタグは書かない（別途付与します）
・投稿テキストのみ出力してください""",

    "F": """\
AIエンジニア・LLM活用人材の需要が高いという市場情報から、
自然にレバテックフリーランスへの登録を勧める投稿を書いてください。

含める要素:
・具体的な月収目安（月60〜80万など）
・「登録だけでも相場感がわかる」という実利
・末尾に「👉 {AFFILIATE_URL}」を含める

ルール:
・市場の事実として伝える（成功保証しない）
・200〜350文字（ハッシュタグ除く）
・ハッシュタグは書かない（別途付与します）
・投稿テキストのみ出力してください""",
}

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

    pattern = _get_next_pattern()
    log.info(f"投稿パターン: {pattern}")

    prompt = PATTERN_PROMPTS[pattern]
    aff_url = affiliate_url or os.environ.get("BUSINESS_AFFILIATE_URL", "[プロフィールリンクから]")
    prompt = prompt.replace("{AFFILIATE_URL}", aff_url)

    hashtags = _get_hashtags()

    try:
        client = Groq(api_key=key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
        )
        body = response.choices[0].message.content.strip()
        text = f"{body}\n\n{hashtags}"
        log.info(f"Groq生成完了: {len(text)}文字 / slot={slot} / pattern={pattern}")
        return text
    except Exception as e:
        log.error(f"Groq API エラー: {e}")
        return None


def get_fallback_post() -> str:
    pattern = random.choice(list(FALLBACK_POSTS.keys()))
    hashtags = _get_hashtags()
    return f"{FALLBACK_POSTS[pattern]}\n\n{hashtags}"
