#!/usr/bin/env python3
"""
scripts/batch_generate_short_videos.py — ショート動画一括生成 CLI

使用例:
  python scripts/batch_generate_short_videos.py \\
    --input-dir input/recordings \\
    --templates shock cleanup ai_user
"""

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video.templates import load, list_names
from src.video.generator import generate_short_video, find_font


def main() -> None:
    all_templates = list_names()

    parser = argparse.ArgumentParser(
        description="サブスク帳ショート動画一括生成ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input-dir",  default="input/recordings", help="入力ディレクトリ")
    parser.add_argument("--output-dir", default="output/videos",    help="出力ディレクトリ")
    parser.add_argument(
        "--templates", nargs="+",
        default=all_templates,
        help=f"適用するテンプレート（複数指定可）。省略時は全テンプレート: {all_templates}",
    )
    parser.add_argument("--font",        default=None, help="日本語フォントパス")
    parser.add_argument("--fps",         type=int, default=30, help="出力FPS")
    parser.add_argument("--keep-audio",  action="store_true", help="入力音声を保持する")
    args = parser.parse_args()

    input_dir  = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not input_dir.exists():
        log.error(f"入力ディレクトリが見つかりません: {input_dir}")
        sys.exit(1)

    mp4_files = sorted(input_dir.glob("*.mp4"))
    if not mp4_files:
        log.error(f"mp4 ファイルが見つかりません: {input_dir}")
        sys.exit(1)

    # テンプレート検証
    invalid = [t for t in args.templates if t not in list_names()]
    if invalid:
        log.error(f"存在しないテンプレート: {invalid}")
        log.error(f"利用可能: {list_names()}")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    font_path = args.font or find_font()

    if font_path:
        log.info(f"フォント: {font_path}")
    else:
        log.warning("日本語フォントが見つかりません")

    total   = len(mp4_files) * len(args.templates)
    done    = 0
    failed  = 0
    outputs = []

    log.info(f"対象動画: {len(mp4_files)}本 / テンプレート: {len(args.templates)}種 / 合計: {total}本")

    for mp4 in mp4_files:
        for tmpl_name in args.templates:
            out_path = output_dir / f"{mp4.stem}_{tmpl_name}.mp4"
            template = load(tmpl_name)
            log.info(f"[{done + 1}/{total}] {mp4.name} x {tmpl_name} -> {out_path.name}")
            try:
                generate_short_video(
                    input_path=str(mp4),
                    output_path=str(out_path),
                    template=template,
                    font_path=font_path,
                    fps=args.fps,
                    keep_audio=args.keep_audio,
                )
                outputs.append(out_path)
                done += 1
            except Exception as e:
                log.error(f"  失敗: {e}")
                failed += 1

    print(f"\n{'='*50}")
    print(f"完了: {done}/{total} 本生成")
    if failed:
        print(f"失敗: {failed} 本")
    print("\n出力ファイル:")
    for p in outputs:
        print(f"  {p.resolve()}")


if __name__ == "__main__":
    main()
