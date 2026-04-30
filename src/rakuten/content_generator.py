"""
rakuten/content_generator.py — 楽天アフィリエイト用 Threads 投稿生成

方針:
  - 20代後半男性の無駄遣いを減らす買い物メモ
  - 信用形成を優先し、リンクなし投稿を多めにする
  - アフィリエイトリンク付き投稿は全体の20〜30%程度
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = BASE_DIR / "config" / "rakuten_prompts.json"
AFFILIATE_DISCLOSURE = "PR｜楽天アフィリエイトリンクを含みます"

BANNED_PHRASES = [
    "絶対",
    "必ず",
    "誰でも",
    "劇的に変わる",
    "これだけで稼げる",
    "劇的",
    "完全無料で稼げる",
]

BANNED_MEDICAL_TERMS = [
    "トレチノイン",
    "ハイドロキノン",
    "治療",
    "シミ改善",
    "ニキビ改善",
    "毛穴治療",
    "医薬品",
]

FALLBACK_BY_CATEGORY = {
    "buy_good": "買ってよかったのは、机の上に置ける小さい電源タップ。充電場所が固定されるだけで、ケーブルを探す時間がかなり減った。派手さはないけど、毎日ちょっと楽になる道具はコスパが高い。",
    "waste_cut": "無駄遣いを減らすなら、安いから買うをやめるのが先だった。同じ用途のものを何個も持つと結局使わない。買う前に代用品が家にないか見るだけで、出費がかなり落ち着くし、物も増えにくい。",
    "saving_item": "節約目的で買って残ったのは、詰め替えやすいボトルと消耗品の定位置。安い物を探すより、無駄に増やさない仕組みを作る方がラクだった。一人暮らしは収納が節約に直結する。",
    "solo_living": "一人暮らしで地味に効いたのは、折りたためる収納ボックス。床に物を置かなくなるだけで部屋が散らかりにくい。見た目が整うと、余計な買い足しも減ってくるし、掃除の面倒も減った。",
    "beauty_small": "美容小物で続いたのは、見た目が派手なものより毎日手が伸びるものだった。清潔感は高級品より習慣で決まるので、洗いやすい道具や置き場所の方が意外と大事。続けやすさはかなり効く。",
    "gadget_desk": "デスク周りで満足度が高かったのは、PCスタンドみたいな姿勢が変わる系。作業時間が長い日は、スペックより疲れにくさの方が効く。派手なガジェットより先に整えると、地味に毎日ラクになる。",
    "failure_learn": "失敗した買い物で多いのは、レビューだけで勢い買いしたもの。最初は便利でも置き場所が決まらないと使わなくなる。今は買う前に、どこに置くかまで決めてから選ぶようにしてる。",
    "affiliate": f"最近よかったのは、毎日使う物を楽天でまとめて見直すやり方。高い物を探すより、使う頻度が高い物を整える方が満足度が高い。{AFFILIATE_DISCLOSURE} 👉 {{affiliate_url}}",
}


@dataclass
class RakutenPost:
    category: str
    is_affiliate: bool
    text: str
    used_fallback: bool
    reason: str


def load_prompts_config(path: Path = CONFIG_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_log(log_path: Path) -> list[dict]:
    if not log_path.exists():
        return []
    try:
        return json.loads(log_path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning(f"楽天ログ読み込み失敗: {exc}")
        return []


def save_log(log_path: Path, entries: list[dict]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def affiliate_allowed(entries: list[dict]) -> bool:
    recent = entries[-4:]
    if any(e.get("is_affiliate") for e in recent):
        return False
    affiliate_count = sum(1 for e in entries if e.get("is_affiliate"))
    if not entries:
        return False
    ratio = affiliate_count / max(len(entries), 1)
    if ratio >= 0.3:
        return False
    return random.random() < 0.25


def choose_category(entries: list[dict], config: dict, is_affiliate: bool) -> str:
    if is_affiliate:
        return "affiliate"
    categories = [name for name in config["categories"].keys() if name != "affiliate"]
    last = entries[-1]["category"] if entries else ""
    choices = [c for c in categories if c != last] or categories
    return random.choice(choices)


def build_prompt(category: str, is_affiliate: bool, affiliate_url: str, config: dict) -> str:
    category_cfg = config["categories"][category]
    pr_rule = (
        f"・本文に必ず「{AFFILIATE_DISCLOSURE}」をそのまま入れる\n"
        f"・リンクは「👉 {affiliate_url}」の形式で入れる"
        if is_affiliate and affiliate_url
        else "・リンクは入れない"
    )
    return f"""以下の条件でThreads投稿を1つ作成してください。

テーマ: 20代後半男性の、無駄遣いを減らす買い物メモ
カテゴリ: {category}
意図: {category_cfg['description']}
トーン: {category_cfg['tone']}

必須条件:
・Threads向けの自然な短文
・80〜220字程度
・広告臭を抑える
・楽天で買える日用品、節約グッズ、時短グッズ、美容小物、ガジェット、デスク周り、一人暮らし用品、生活改善アイテムの文脈にする
・「絶対」「必ず」「誰でも」「劇的に変わる」「これだけで稼げる」は使わない
・医療・薬機法に寄る表現は禁止
・トレチノイン、ハイドロキノン、治療、シミ改善、ニキビ改善は書かない
・美容小物は「清潔感」「身だしなみ」「続けやすい」程度に留める
{pr_rule}

投稿テキストのみ出力してください。
"""


def quality_check(text: str, is_affiliate: bool) -> tuple[bool, str]:
    body = text.strip()
    if not body:
        return False, "空テキスト"
    length = len(body)
    if length < 80:
        return False, f"文字数不足: {length}"
    if length > 220:
        return False, f"文字数超過: {length}"
    for phrase in BANNED_PHRASES:
        if phrase in body:
            return False, f"禁止表現: {phrase}"
    for term in BANNED_MEDICAL_TERMS:
        if term in body:
            return False, f"禁止語: {term}"
    if is_affiliate:
        if AFFILIATE_DISCLOSURE not in body:
            return False, "PR表記不足"
        if "http://" not in body and "https://" not in body and "👉" not in body:
            return False, "リンク導線不足"
    return True, "OK"


def generate_with_groq(prompt: str, api_key: str) -> Optional[str]:
    if not api_key:
        return None
    try:
        from groq import Groq
    except ImportError:
        log.warning("groq 未インストール")
        return None

    try:
        client = Groq(api_key=api_key)
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        log.warning(f"Groq生成失敗: {exc}")
        return None


def fallback_text(category: str, affiliate_url: str) -> str:
    text = FALLBACK_BY_CATEGORY[category]
    if "{affiliate_url}" in text:
        return text.format(affiliate_url=affiliate_url or "[楽天リンク]")
    return text


def generate_post(entries: list[dict], affiliate_url: str, api_key: str = "", config: Optional[dict] = None) -> RakutenPost:
    config = config or load_prompts_config()
    is_affiliate = affiliate_allowed(entries)
    category = choose_category(entries, config, is_affiliate)
    prompt = build_prompt(category, is_affiliate, affiliate_url, config)
    text = generate_with_groq(prompt, api_key)
    used_fallback = False
    if not text:
        text = fallback_text(category, affiliate_url)
        used_fallback = True

    ok, reason = quality_check(text, is_affiliate)
    if not ok:
        text = fallback_text(category, affiliate_url)
        used_fallback = True
        ok, reason = quality_check(text, is_affiliate)
    if not ok:
        raise ValueError(f"楽天投稿の品質チェック失敗: {reason}")

    return RakutenPost(
        category=category,
        is_affiliate=is_affiliate,
        text=text,
        used_fallback=used_fallback,
        reason=reason,
    )
