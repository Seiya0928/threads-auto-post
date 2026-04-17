"""
generate_x_drafts.py — GitHub Actions から呼び出す X 投稿下書き生成スクリプト

フロー:
  1. Gemini API で X用投稿下書きを 3〜5 本生成
  2. x_drafts/YYYY-MM-DD.txt に保存
  3. GitHub Actions が git commit & push
"""

import logging
import os
import random
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

JST        = timezone(timedelta(hours=9))
DRAFTS_DIR = Path(__file__).parent / "x_drafts"


def format_drafts(drafts: list) -> str:
    total = len(drafts)
    parts = []
    for i, draft in enumerate(drafts, 1):
        parts.append(f"[{i}/{total}] {draft['label']}")
        parts.append(draft["text"])
        parts.append("---")
    return "\n".join(parts)


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        log.error("ANTHROPIC_API_KEY が設定されていません")
        sys.exit(1)

    sys.path.insert(0, os.path.dirname(__file__))
    from src.x_draft_generator import generate_drafts

    count = random.randint(3, 5)
    log.info(f"X投稿下書きを {count} 本生成します")

    drafts = generate_drafts(count=count, api_key=api_key)
    if not drafts:
        log.error("下書き生成に失敗しました")
        sys.exit(1)

    DRAFTS_DIR.mkdir(exist_ok=True)
    today     = datetime.now(JST).strftime("%Y-%m-%d")
    save_path = DRAFTS_DIR / f"{today}.txt"

    content = format_drafts(drafts)
    save_path.write_text(content, encoding="utf-8")
    log.info(f"保存完了: {save_path} ({len(drafts)}本)")
    log.info(f"\n{content}")


if __name__ == "__main__":
    main()
