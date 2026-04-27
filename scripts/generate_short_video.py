#!/usr/bin/env python3
"""
scripts/generate_short_video.py — ショート動画単体生成 CLI

使用例:
  python scripts/generate_short_video.py \\
    --input input/recordings/demo.mp4 \\
    --template shock \\
    --output output/videos/demo_shock.mp4
"""

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# プロジェクトルートを sys.path に追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.video.templates import load, list_names
from src.video.generator import generate_short_video, find_font


def main() -> None:
    parser = argparse.ArgumentParser(
        description="サブスク帳ショート動画生成ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input",    required=True,  help="入力動画パス (mp4)")
    parser.add_argument("--template", required=True,  help=f"テンプレート名 ({', '.join(list_names())})")
    parser.add_argument("--output",   default=None,   help="出力パス（省略時は自動生成）")
    parser.add_argument("--font",     default=None,   help="日本語フォントパス（省略時は自動検出）")
    parser.add_argument("--fps",      type=int, default=30, help="出力FPS（デフォルト: 30）")
    parser.add_argument("--keep-audio", action="store_true", help="入力音声を保持する")
    args = parser.parse_args()

    # 入力チェック
    input_path = Path(args.input)
    if not input_path.exists():
        log.error(f"入力ファイルが見つかりません: {input_path}")
        sys.exit(1)

    # 出力パス自動生成
    if args.output:
        output_path = Path(args.output)
    else:
        stem = input_path.stem
        output_path = Path("output/videos") / f"{stem}_{args.template}.mp4"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # テンプレート読み込み（存在しない場合は候補表示して終了）
    template = load(args.template)
    font_path = args.font or find_font()

    log.info(f"テンプレート: {args.template}")
    log.info(f"入力: {input_path}")
    log.info(f"出力: {output_path}")
    if font_path:
        log.info(f"フォント: {font_path}")
    else:
        log.warning("日本語フォントが見つかりません（テキストが文字化けする可能性あり）")

    try:
        generate_short_video(
            input_path=str(input_path),
            output_path=str(output_path),
            template=template,
            font_path=font_path,
            fps=args.fps,
            keep_audio=args.keep_audio,
        )
    except RuntimeError as e:
        log.error(str(e))
        sys.exit(1)
    except Exception as e:
        log.error(f"生成中にエラーが発生しました: {e}")
        sys.exit(1)

    print(f"\n生成完了: {output_path.resolve()}")


if __name__ == "__main__":
    main()
