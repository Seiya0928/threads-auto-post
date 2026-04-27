"""
main_business.py — Threads ビジネス自動投稿 v2

フロー:
  1. data/business_post_log.csv から投稿履歴を読み込み
  2. 6投稿サイクルで次の投稿タイプを決定
  3. JST 時刻からスロット（morning/noon/evening）を判定
  4. Groq API で投稿タイプ別プロンプトを使って本文を生成（最大3回リトライ）
  5. 品質チェック通過後、Threads API に投稿
  6. data/business_post_log.csv に結果を記録（成功・失敗とも）

使い方:
  通常実行 : python main_business.py
  DRY RUN  : python main_business.py --dry-run
"""

import argparse
import csv
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

# ── 投稿サイクル（6投稿で1周） ─────────────────────────────────────────────
POST_CYCLE = [
    {"type": "story",          "affiliate": False},
    {"type": "insight",        "affiliate": False},
    {"type": "failure",        "affiliate": False},
    {"type": "howto",          "affiliate": False},
    {"type": "affiliate_soft", "affiliate": True},
    {"type": "affiliate_hard", "affiliate": True},
]

# ── パス ───────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent
DATA_DIR      = BASE_DIR / "data"
CONFIG_DIR    = BASE_DIR / "config"
CSV_PATH      = DATA_DIR / "business_post_log.csv"
PROMPTS_PATH  = CONFIG_DIR / "business_prompts.json"

CSV_FIELDS = [
    "timestamp_jst", "date_jst", "time_jst",
    "post_type", "has_affiliate", "affiliate_url_used", "cta_type",
    "posted_text", "success", "error",
]

# ── 禁止ワード ─────────────────────────────────────────────────────────────
BANNED_PHRASES = [
    "絶対稼げる", "誰でも簡単", "詳しくはこちら", "今すぐクリック",
    "放置で稼げる", "誰でも稼げる", "簡単に稼げる", "今すぐ登録",
    "革命的", "大注目", "爆発的に稼",
]

# ── デフォルトプロンプト設定（config JSON が読めない場合） ─────────────────
DEFAULT_PROMPTS_CONFIG: dict = {
    "story":          {"hashtags": "#AI副業 #個人開発"},
    "failure":        {"hashtags": "#AI副業 #個人開発"},
    "insight":        {"hashtags": "#AI活用 #副業"},
    "howto":          {"hashtags": "#AI活用 #個人開発"},
    "affiliate_soft": {"hashtags": "#副業 #AI活用"},
    "affiliate_hard": {"hashtags": "#副業収入 #AI副業"},
}

# ── フォールバック本文（API失敗時） ───────────────────────────────────────
FALLBACK_TEXTS: dict[str, str] = {
    "story": (
        "Threads自動投稿の仕組みを作り始めて2週間。"
        "思ったより速くできたが、投稿の品質を保つ方が難しかった。"
        "AIで生成→品質チェック→投稿を自動化すると、毎日の更新コストがほぼゼロになる。"
    ),
    "failure": (
        "自動化を作っても、売れる導線がなければ収益にはならない。"
        "ここを勘違いすると、作業量だけ増える。"
        "まず「誰に何を売るか」を決めてから自動化するのが正しい順番だと思った。"
    ),
    "insight": (
        "AIで副業を作るなら、最初に必要なのは完璧なアイデアより、"
        "毎日動く小さな仕組みだと思う。\n"
        "大きく考えて小さく始める、ではなく、"
        "小さく始めて動かし続けることが結果につながる。"
    ),
    "howto": (
        "GitHub ActionsとGroq APIで投稿を自動化する手順。\n"
        "1. Groq APIキーを取得（無料）\n"
        "2. main.pyで投稿文を生成\n"
        "3. GitHub Actionsで定時実行\n"
        "サーバーコストゼロで動く。"
    ),
    "affiliate_soft": (
        "最近は、AIツールを単体で使うより、"
        "投稿・LP・決済まで一つの流れにする方が重要だと感じている。\n"
        "ツール選びより、どう組み合わせるかで差がつく。"
        "使っている構成はプロフィール側にまとめています。"
    ),
    "affiliate_hard": (
        "AI副業の第一歩として、まずクラウドソーシングで相場観を掴むのが早い。\n"
        "AI系・自動化系の案件は増えていて、単価も思ったより幅がある。"
        "登録・応募は無料なので、見るだけでも価値がある。"
        "必要な人はプロフィールにまとめています。"
    ),
}


# ── プロンプト設定の読み込み ───────────────────────────────────────────────

def load_prompts_config() -> dict:
    try:
        if PROMPTS_PATH.exists():
            data = json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))
            log.info(f"プロンプト設定読み込み: {PROMPTS_PATH.name}")
            return data
    except Exception as e:
        log.warning(f"プロンプト設定読み込み失敗 → デフォルト使用: {e}")
    return DEFAULT_PROMPTS_CONFIG


# ── CSV ログ管理 ───────────────────────────────────────────────────────────

def load_csv_log() -> list[dict]:
    if not CSV_PATH.exists():
        return []
    try:
        with CSV_PATH.open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))
    except Exception as e:
        log.warning(f"CSVログ読み込み失敗: {e}")
        return []


def append_csv_log(row: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    write_header = not CSV_PATH.exists()
    try:
        with CSV_PATH.open("a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
            if write_header:
                writer.writeheader()
            writer.writerow(row)
        log.info(f"CSVログ追記: {CSV_PATH.name}")
    except Exception as e:
        log.warning(f"CSVログ書き込み失敗: {e}")


# ── 投稿タイプ決定（6投稿サイクル） ──────────────────────────────────────

def determine_post_type(csv_log: list[dict]) -> dict:
    success_count = sum(1 for r in csv_log if r.get("success") == "true")
    idx = success_count % len(POST_CYCLE)
    entry = POST_CYCLE[idx]
    log.info(
        f"投稿サイクル: 成功済み{success_count}件 → "
        f"index={idx} / type={entry['type']} / affiliate={entry['affiliate']}"
    )
    return entry


# ── スロット判定 ───────────────────────────────────────────────────────────

def get_slot() -> str:
    h = datetime.now(JST).hour
    if 5 <= h < 11:
        return "morning"
    elif 11 <= h < 17:
        return "noon"
    return "evening"


# ── プロンプト構築 ─────────────────────────────────────────────────────────

_BASE_RULES = """\
共通ルール:
・投稿テキストのみ出力（前置き・説明・括弧書き不要）
・ハッシュタグは書かない（別途付与します）
・「絶対稼げる」「誰でも簡単」「詳しくはこちら」「今すぐクリック」などの過剰な売り込み文言は禁止
・本文（ハッシュタグ除く）は必ず80文字以上500文字以下"""

_SLOT_CONTEXT = {
    "morning": "トーン: 朝向け（軽い気づき・共感・前向きな内容）",
    "noon":    "トーン: 昼向け（実用的・ノウハウ寄り）",
    "evening": "トーン: 夜向け（ストーリー・内省・少し深い内容）",
}


def build_prompt(post_type: str, slot: str, affiliate_url: str) -> str:
    slot_line = _SLOT_CONTEXT.get(slot, "")

    if post_type == "story":
        return f"""以下の条件でThreads投稿を書いてください。
投稿タイプ: story（AI副業・開発・収益化の実体験）
{slot_line}

構成:
・1行目は数字または具体的な状況から始める（例:「3日で」「1週間で」「月¥0→¥12,000」）
・AI副業、アプリ開発、自動化、収益化のリアルな体験を書く
・少し内省的で読者が共感できる内容
・売り込みなし、URLなし、120〜250文字（ハッシュタグ除く）
{_BASE_RULES}"""

    if post_type == "failure":
        return f"""以下の条件でThreads投稿を書いてください。
投稿タイプ: failure（失敗談・詰まった点・反省）
{slot_line}

構成:
・1行目は「やらなくてよかった」「失敗した」「無駄だった」など結果から入る
・具体的に何が失敗だったかを書く
・最後は学びや気づきで締める（前向きな着地）
・売り込みなし、URLなし、120〜250文字（ハッシュタグ除く）
{_BASE_RULES}"""

    if post_type == "insight":
        return f"""以下の条件でThreads投稿を書いてください。
投稿タイプ: insight（AI副業・自動化・個人開発の気づき）
{slot_line}

構成:
・AI副業、自動化、SNS運用、個人開発に関する鋭い気づきを書く
・短く、保存したくなる内容
・具体例か数字を1つ入れる
・売り込みなし、URLなし
・必ず80文字以上180文字以下（ハッシュタグ除く）
{_BASE_RULES}"""

    if post_type == "howto":
        return f"""以下の条件でThreads投稿を書いてください。
投稿タイプ: howto（初心者向け実用ノウハウ）
{slot_line}

構成:
・1行目は具体的な結果または数字から始める
・手順を2〜4ステップで番号付き箇条書きで書く
・ツール名・サービス名を具体的に入れる（Groq, GitHub Actions, Claude等）
・今日すぐ試せる内容、売り込みなし、URLなし
・120〜280文字（ハッシュタグ除く）
{_BASE_RULES}"""

    if post_type == "affiliate_soft":
        if affiliate_url:
            link_rule = (
                f"・投稿末尾にアフィリエイトリンクを「👉 {affiliate_url}」の形式で自然に入れる\n"
                "・リンクへの誘導は体験談の流れで（「気になった人はこちら」等、押し付けない）"
            )
        else:
            link_rule = (
                "・URLは入れない\n"
                "・「使っている構成はプロフィールにまとめています」"
                "「必要な人はプロフィールから確認できます」のような自然なCTAで締める"
            )
        return f"""以下の条件でThreads投稿を書いてください。
投稿タイプ: affiliate_soft（体験談ベースの自然なサービス紹介）
{slot_line}

構成:
・1行目は自分の体験や課題から始める
・ツールやサービスを使った体験談として書く（売り込み感を最小化）
・使ってよかった点を1〜2つ具体的に書く
{link_rule}
・120〜280文字（ハッシュタグ除く）
{_BASE_RULES}"""

    if post_type == "affiliate_hard":
        if affiliate_url:
            link_rule = (
                f"・投稿末尾に「👉 {affiliate_url}」を入れる\n"
                "・明確におすすめするが、誇大表現は使わない"
            )
        else:
            link_rule = (
                "・URLは入れない\n"
                "・「必要な人向けにプロフィールにまとめています」のようなCTAで締める"
            )
        return f"""以下の条件でThreads投稿を書いてください。
投稿タイプ: affiliate_hard（明確なおすすめ・サービス紹介）
{slot_line}

構成:
・1行目は数字またはベネフィットから始める
・具体的なサービス名・ツール名を出す
・ベネフィットを端的に1〜2つ書く
{link_rule}
・煽りすぎない、等身大で
・120〜280文字（ハッシュタグ除く）
{_BASE_RULES}"""

    return f"投稿タイプ「{post_type}」でThreads投稿を1つ書いてください。本文のみ出力してください。"


# ── 品質チェック ───────────────────────────────────────────────────────────

def quality_check(
    text: str,
    post_type: str,
    is_affiliate: bool,
    affiliate_urls: list[str],
    recent_texts: list[str],
) -> tuple[bool, str]:
    if not text or not text.strip():
        return False, "空テキスト"

    body = re.sub(r'\n?#\S+', '', text).strip()
    char_count = len(body)

    if char_count < 80:
        return False, f"文字数不足: {char_count}文字（最低80文字）"
    if char_count > 500:
        return False, f"文字数超過: {char_count}文字（最大500文字）"

    tag_count = len(re.findall(r'#\S+', text))
    if tag_count > 5:
        return False, f"ハッシュタグ過多: {tag_count}個"

    # リンクなし投稿にURLが混ざっていないか
    if not is_affiliate and re.search(r'https?://', text):
        return False, "リンクなし投稿にURLが含まれている"

    # affiliate_soft/hard 以外でアフィリURLが混入していないか
    if not is_affiliate:
        for url in affiliate_urls:
            if url and url in text:
                return False, "アフィリエイトURLがリンクなし投稿に含まれている"

    # 禁止ワード
    for phrase in BANNED_PHRASES:
        if phrase in text:
            return False, f"禁止ワード: 「{phrase}」"

    # 完全重複（直近20件）
    if text.strip() in [t.strip() for t in recent_texts]:
        return False, "完全重複投稿"

    return True, "OK"


# ── Groq API で投稿生成 ────────────────────────────────────────────────────

def generate_post(
    post_type: str,
    slot: str,
    is_affiliate: bool,
    affiliate_url: str,
    crowdworks_url: str,
    midworks_url: str,
    groq_key: str,
    recent_texts: list[str],
    hashtags: str,
) -> Optional[str]:
    if not groq_key:
        log.warning("GROQ_API_KEY 未設定 → fallback を使用")
        return None
    try:
        from groq import Groq
    except ImportError:
        log.error("groq 未インストール: pip install groq")
        return None

    prompt = build_prompt(post_type, slot, affiliate_url)
    client = Groq(api_key=groq_key)
    all_affiliate_urls = [u for u in [crowdworks_url, midworks_url] if u]

    for attempt in range(1, 4):
        try:
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
            )
            body = resp.choices[0].message.content.strip()
            text = f"{body}\n\n{hashtags}"
            ok, reason = quality_check(text, post_type, is_affiliate, all_affiliate_urls, recent_texts)
            if ok:
                log.info(f"Groq生成成功 (attempt {attempt}): {len(body)}文字 / {post_type}")
                return text
            log.warning(f"品質チェックNG (attempt {attempt}): {reason}")
        except Exception as e:
            log.error(f"Groq APIエラー (attempt {attempt}): {e}")
            break

    log.warning("全attempt失敗 → fallback使用")
    return None


# ── フォールバック本文 ─────────────────────────────────────────────────────

def get_fallback_text(
    post_type: str,
    is_affiliate: bool,
    affiliate_url: str,
    hashtags: str,
) -> str:
    body = FALLBACK_TEXTS.get(post_type, FALLBACK_TEXTS["story"])
    if is_affiliate and affiliate_url and "👉" not in body and "http" not in body:
        body = body.rstrip("。") + f"\n👉 {affiliate_url}"
    return f"{body}\n\n{hashtags}"


# ── ハッシュタグ取得 ───────────────────────────────────────────────────────

def get_hashtags(post_type: str, prompts_cfg: dict) -> str:
    cfg = prompts_cfg.get(post_type, {})
    return cfg.get("hashtags", DEFAULT_PROMPTS_CONFIG.get(post_type, {}).get("hashtags", "#AI副業 #個人開発"))


# ── ログ記録 ───────────────────────────────────────────────────────────────

def log_result(
    success: bool,
    post_type: str,
    is_affiliate: bool,
    affiliate_url_used: str,
    cta_type: str,
    posted_text: str,
    error: str,
) -> None:
    now_jst = datetime.now(JST)
    row = {
        "timestamp_jst":      now_jst.isoformat(),
        "date_jst":           now_jst.strftime("%Y-%m-%d"),
        "time_jst":           now_jst.strftime("%H:%M:%S"),
        "post_type":          post_type,
        "has_affiliate":      str(is_affiliate).lower(),
        "affiliate_url_used": affiliate_url_used,
        "cta_type":           cta_type,
        "posted_text":        posted_text.replace("\n", "\\n"),
        "success":            str(success).lower(),
        "error":              error,
    }
    append_csv_log(row)


# ── メイン ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Threads ビジネス自動投稿")
    parser.add_argument("--dry-run", action="store_true", help="投稿せずに内容を確認する")
    args = parser.parse_args()
    dry_run = args.dry_run

    if dry_run:
        log.info("=== DRY RUN モード（実投稿なし） ===")

    # 環境変数
    token = os.environ.get("BUSINESS_THREADS_ACCESS_TOKEN", "")
    groq_key = os.environ.get("GROQ_API_KEY", "")
    crowdworks_url = os.environ.get("CROWDWORKS_AFFILIATE_URL", "").strip()
    midworks_url   = os.environ.get("MIDWORKS_AFFILIATE_URL", "").strip()

    if not token and not dry_run:
        log.error("BUSINESS_THREADS_ACCESS_TOKEN が設定されていません")
        sys.exit(1)

    # 設定・ログ読み込み
    prompts_cfg = load_prompts_config()
    csv_log = load_csv_log()
    recent_texts = [r.get("posted_text", "").replace("\\n", "\n") for r in csv_log[-20:]]

    # 投稿タイプ決定
    cycle_entry  = determine_post_type(csv_log)
    post_type    = cycle_entry["type"]
    is_affiliate = cycle_entry["affiliate"]

    # スロット・時刻
    slot    = get_slot()
    now_jst = datetime.now(JST)
    log.info(f"スロット: {slot} (JST {now_jst.strftime('%H:%M')})")
    log.info(f"投稿タイプ: {post_type} / アフィリ: {is_affiliate}")
    # タイプ別アフィリエイトURL（soft=クラウドワークス / hard=Midworks）
    affiliate_url = crowdworks_url if post_type == "affiliate_soft" else midworks_url
    if is_affiliate:
        log.info(f"アフィリURL ({post_type}): {'設定あり' if affiliate_url else '未設定（CTAフォールバック）'}")

    # ハッシュタグ
    hashtags = get_hashtags(post_type, prompts_cfg)

    # テキスト生成
    full_text = generate_post(
        post_type, slot, is_affiliate, affiliate_url,
        crowdworks_url, midworks_url,
        groq_key, recent_texts, hashtags,
    )
    used_fallback = full_text is None
    if used_fallback:
        full_text = get_fallback_text(post_type, is_affiliate, affiliate_url, hashtags)
        log.info(f"fallback使用: {post_type}")

    # CTA 種別
    cta_type = "none"
    if post_type == "affiliate_hard":
        cta_type = "hard"
    elif post_type == "affiliate_soft":
        cta_type = "soft"
    elif "プロフィール" in full_text or "保存" in full_text:
        cta_type = "profile"

    affiliate_url_used = (
        affiliate_url
        if (is_affiliate and affiliate_url and affiliate_url in full_text)
        else ""
    )

    log.info(f"投稿テキスト ({len(full_text)}文字):\n{full_text}")

    # DRY RUN 出力
    if dry_run:
        all_urls = [u for u in [crowdworks_url, midworks_url] if u]
        ok, reason = quality_check(full_text, post_type, is_affiliate, all_urls, recent_texts)
        print("\n" + "=" * 60)
        print(f"[DRY RUN] 投稿タイプ   : {post_type}")
        print(f"[DRY RUN] アフィリ有無 : {is_affiliate}")
        print(f"[DRY RUN] CTA種別      : {cta_type}")
        print(f"[DRY RUN] URL使用      : {affiliate_url_used or 'なし'}")
        print(f"[DRY RUN] fallback使用 : {used_fallback}")
        print(f"[DRY RUN] 文字数       : {len(full_text)}文字")
        print(f"[DRY RUN] 品質チェック : {'OK' if ok else f'NG ({reason})'}")
        print(f"[DRY RUN] ログ予定     : success=true, type={post_type}")
        print("-" * 60)
        print(full_text)
        print("=" * 60)
        return

    # Threads クライアント
    sys.path.insert(0, str(BASE_DIR))
    from src.threads_client import ThreadsClient
    client = ThreadsClient(token)

    try:
        uid = client.user_id
        log.info(f"認証OK: user_id={uid}")
    except Exception as e:
        log.error(f"認証失敗: {e}")
        log_result(False, post_type, is_affiliate, affiliate_url_used, cta_type, full_text, str(e))
        sys.exit(1)

    # 冪等性チェック
    if client.was_recently_posted(within_hours=2):
        log.warning("直近2時間以内に投稿済みのためスキップ")
        sys.exit(0)

    # 投稿
    success   = False
    error_msg = ""
    try:
        thread_id = client.post_text(full_text)
        log.info(f"投稿成功: thread_id={thread_id}")
        success = True
    except Exception as e:
        error_msg = str(e)
        log.error(f"投稿失敗: {e}")

    # CSV ログ記録
    log_result(success, post_type, is_affiliate, affiliate_url_used, cta_type, full_text, error_msg)

    if not success:
        sys.exit(1)

    log.info(
        f"完了: type={post_type} / "
        f"{'fallback' if used_fallback else 'API生成'} / "
        f"{len(full_text)}文字"
    )


if __name__ == "__main__":
    main()
