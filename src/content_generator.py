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

import json
import logging
import os
import random
from pathlib import Path
from typing import List, Optional

log = logging.getLogger(__name__)

# 直近何件のフックを重複チェックするか
RECENT_HOOKS_LIMIT = 30
_USED_HOOKS_FILE = Path(__file__).parent.parent / "data" / "used_hooks.json"


def _load_used_hooks() -> list:
    if _USED_HOOKS_FILE.exists():
        try:
            return json.loads(_USED_HOOKS_FILE.read_text())
        except Exception:
            return []
    return []


def _save_used_hook(hook: str) -> None:
    hooks = _load_used_hooks()
    hooks.append(hook)
    hooks = hooks[-RECENT_HOOKS_LIMIT:]
    _USED_HOOKS_FILE.write_text(json.dumps(hooks, ensure_ascii=False, indent=2))

# ── フック定義（型 × テンプレート）────────────────────────────────────────────

HOOK_BANK = {
    "expose": [
        "実はNGなスキンケア習慣{n}選、全部やってた",
        "【やめて】肌を悪化させてる洗顔の間違い{n}つ",
        "皮膚科医が「意味ない」と言うスキンケア{n}選",
        "「肌に良い」と信じてたのに逆効果だったもの",
        "スキンケアで絶対やってはいけないこと{n}つ",
        "美容オタクが「二度と使わない」と言った成分",
        "肌科学的にNGな習慣、まだやってる人いる？",
        "肌荒れの原因、実は洗顔の回数だった話",
        "「保湿すれば治る」が間違いだった理由",
        "毛穴ケアで絶対やってはいけないこと{n}つ",
    ],
    "cospa": [
        "{price}円以下で買えた、肌が変わった話",
        "高いコスメより効いた、コスパ最強の{ingredient}",
        "ドラッグストアで買える、皮膚科処方レベルの成分",
        "月{price}円のスキンケアで肌質が変わった理由",
        "{price}円のクリームで十分だと気づいた話",
        "デパコスをやめてドラコスに変えた結果",
        "コスパで選ぶなら{ingredient}一択な理由",
        "スキンケアに月{price}円以上かけてた俺が気づいたこと",
        "安くて本当に効く成分、正直に教える",
        "プチプラで揃えた今の方が肌がいい理由",
    ],
    "reverse": [
        "{item}をやめたら肌が良くなった話",
        "毎日やってた{habit}を止めた結果",
        "「丁寧なスキンケア」が肌を悪化させていた",
        "引き算スキンケアに変えてから肌が安定した",
        "スキンケアを減らしたら肌トラブルがなくなった",
        "毎日洗顔をやめたらどうなったか報告する",
        "化粧水をやめて{n}ヶ月、肌の変化を正直に話す",
        "スキンケアのステップを{n}つに減らした結果",
        "やることを絞ったら肌が安定してきた話",
        "丁寧にやればやるほど荒れた、その理由",
    ],
    "comparison": [
        "{A}と{B}、{n}ヶ月使い続けて正直な差を報告する",
        "【成分比較】{A}と{B}、どっちが本当に効く",
        "{A} vs {B}、肌への負担が少ないのはどっち",
        "{A}と{B}、朝と夜どっちに使うべきか",
        "プチプラとデパコス、{ingredient}の濃度を比べた",
        "{A}配合と{B}配合、実際に{n}ヶ月試した差",
        "洗顔料の成分{A}と{B}、どっちが毛穴に効く",
        "{A}クリームと{B}クリーム、乾燥肌にはどっちか",
    ],
    "number": [
        "{n}日で実感した、{ingredient}の本当の効果",
        "トレチノインを{n}週間使った肌の変化を記録する",
        "{n}ヶ月続けてわかった、スキンケアの優先順位",
        "{n}年間スキンケアを続けて残った習慣はこれだけ",
        "週{n}回だけ使って毛穴が変わった方法",
        "{n}千円以下で揃えたスキンケアが最強だった",
        "{n}ヶ月で肌質が変わった、唯一変えたこと",
        "朝{n}分のルーティンで肌の調子が安定した話",
        "1日{n}回の〇〇で肌荒れが激減した",
        "{n}個に絞ったスキンケアが正解だった理由",
    ],
    "ranking": [
        "実際に使って良かった保湿アイテム TOP{n}",
        "肌が変わったと感じた瞬間 ベスト{n}",
        "買って後悔したスキンケア{n}選、正直に言う",
        "コスパ最強だと思うスキンケア成分 TOP{n}",
        "男性が使いやすいスキンケアアイテム{n}選",
        "皮膚科に行って正解だったと思う理由{n}つ",
        "肌荒れが治らない人に試してほしいこと{n}つ",
        "ニキビ跡に効いたと思うケア方法{n}選",
        "美容初心者が最初に買うべきもの{n}選",
        "スキンケアで一番コスパがいいと思う習慣{n}つ",
    ],
    "empathy": [
        "これやってる人、今すぐやめた方がいい",
        "スキンケアに{price}円以上かけてる人に言いたいこと",
        "肌荒れが治らない人、原因これじゃないですか",
        "毛穴が気になってた俺が、一番効いたと感じたこと",
        "敏感肌って言ってる人、実はそれバリア破壊してるだけかも",
        "ニキビが繰り返す人に聞いてほしいこと",
        "洗顔後すぐ化粧水つけてる人、ちょっと待って",
        "乾燥するからって重ねづけしてる人へ",
        "「高いから効く」って思ってる人に知ってほしいこと",
        "肌のために頑張ってるのに結果が出ない人へ",
        "スキンケアで消耗してる人、やること多すぎない？",
    ],
    "experience": [
        "{item}を試して{n}ヶ月、正直な結果を報告する",
        "ずっと悩んでた{concern}が変わった話",
        "クリニックで処方された{item}、使ってみた感想",
        "皮膚科に相談して変わったスキンケアの話",
        "{concern}に悩んで試したこと、全部話す",
        "肌荒れが続いて皮膚科に行った話",
        "{item}を使い続けて気づいたこと",
        "成分を調べ始めてからスキンケアが変わった",
        "ニキビ跡に{n}ヶ月向き合った正直な記録",
        "肌に向き合い始めてから変わったこと{n}つ",
    ],
    "question": [
        "結局、スキンケアで一番大事なことって何だと思う？",
        "朝のスキンケア、みんな何分かけてる？",
        "{ingredient}使ってる人、効果あった？",
        "肌荒れの原因、食事と睡眠どっちが大きいと思う？",
        "スキンケアを始めたきっかけって何だった？",
        "ニキビと毛穴、どっちの方が気になる？",
        "化粧水と美容液、どちらを重視してる？",
        "男性のスキンケアって何から始めればいいと思う？",
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
        "hook_types": ["expose", "reverse", "empathy", "question"],
        "hashtags":   "#スキンケア #朝活 #美肌ルーティン #skincare #美容男子",
    },
    "noon": {
        "label":      "昼の暴露・コスパ・ランキング系投稿",
        "tone":       "美容業界の嘘・盲点・コスパ最悪な習慣を毒舌で暴露する",
        "hook_types": ["expose", "cospa", "ranking", "comparison", "question"],
        "hashtags":   "#美容の嘘 #スキンケア #コスパ最強 #skincare #美肌",
    },
    "evening": {
        "label":      "夜のゴールデンタイム向け体験・数字・比較投稿",
        "tone":       "夜のスキンケアに役立つ具体的な成分・製品情報をガチ勢目線で解説",
        "hook_types": ["number", "experience", "comparison", "reverse", "empathy"],
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
・測定不可能な数値（「毛穴が0.5mm細くなった」「明るさが4%向上」などNG）
・カタカナ英語の混在（「Apply」「Retinol」など。日本語に統一）
・不自然な日本語表現（「透明な水」「むらさき色の肌」など）

【数値の使い方】
・期間・回数・価格・濃度のみ使う（「3週間」「1日2回」「0.05%」「1000円」など）
・自分で体感できる変化のみ書く（「肌が明るくなった気がする」レベルの主観でOK）
・一人の人間が書いたような口語体で書く

【参考キーワード（自然に1〜2個盛り込む）】
{keywords}
・キーワードをそのまま文中に使わず、自然な文脈に溶け込ませること

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
    config = SLOT_CONFIG.get(slot, SLOT_CONFIG["evening"])
    used_hooks = _load_used_hooks()

    for attempt in range(10):
        hook_type = random.choice(config["hook_types"])
        templates = HOOK_BANK.get(hook_type, HOOK_BANK["expose"])
        template  = random.choice(templates)
        try:
            hook = template.format(**{k: random.choice(v) for k, v in HOOK_VARS.items()})
        except KeyError:
            hook = template

        if hook not in used_hooks:
            return hook

        log.warning(f"重複フック検出（試行{attempt + 1}回目）: {hook[:30]}...")

    log.warning("10回試行しても重複回避できず、最後のフックをそのまま使用")
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
        from groq import Groq
    except ImportError:
        log.error("groq 未インストール: pip install groq")
        return None

    key = api_key or os.environ.get("GROQ_API_KEY", "")
    if not key:
        log.error("GROQ_API_KEY が設定されていません")
        return None

    config       = SLOT_CONFIG.get(slot, SLOT_CONFIG["evening"])
    keywords     = trend_keywords or []
    keywords_str = "、".join(keywords[:6]) if keywords else "特になし"
    hook         = _build_hook(slot)
    _save_used_hook(hook)
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
        client   = Groq(api_key=key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.choices[0].message.content.strip()
        log.info(f"Groq生成完了: {len(text)}文字 / slot={slot} / style={style}")
        return text
    except Exception as e:
        log.error(f"Groq API エラー: {e}")
        return None
