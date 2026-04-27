"""
src/video/templates.py — テンプレート設定の読み込み・バリデーション
"""
import json
import sys
from pathlib import Path

TEMPLATES_PATH = Path(__file__).parent.parent.parent / "config" / "video_templates.json"

# テンプレートのデフォルト値
DEFAULTS = {
    "max_duration": 15,
    "output_width": 1080,
    "output_height": 1920,
    "font_size_hook": 72,
    "font_size_middle": 56,
    "font_size_cta": 60,
    "hook_text": "",
    "middle_text": "",
    "cta_text": "",
}


def load_all() -> dict:
    """全テンプレートを読み込む。"""
    try:
        data = json.loads(TEMPLATES_PATH.read_text(encoding="utf-8"))
        return data
    except FileNotFoundError:
        print(f"[ERROR] テンプレート設定が見つかりません: {TEMPLATES_PATH}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[ERROR] テンプレートJSONのパースに失敗: {e}", file=sys.stderr)
        sys.exit(1)


def load(name: str) -> dict:
    """指定名のテンプレートを読み込む。存在しない場合は候補を表示して終了。"""
    all_templates = load_all()
    if name not in all_templates:
        available = ", ".join(sorted(all_templates.keys()))
        print(f"[ERROR] テンプレート '{name}' が見つかりません。", file=sys.stderr)
        print(f"  利用可能: {available}", file=sys.stderr)
        sys.exit(1)
    # デフォルト値をマージ
    merged = {**DEFAULTS, **all_templates[name]}
    return merged


def list_names() -> list[str]:
    """テンプレート名一覧を返す。"""
    return sorted(load_all().keys())
