"""
tests/test_video_templates.py — テンプレート読み込みの基本テスト
（動画ファイル不要。moviepy 不要）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_templates_load():
    from src.video.templates import load_all, list_names
    templates = load_all()
    assert isinstance(templates, dict), "テンプレートは辞書でなければならない"
    assert len(templates) >= 3, "テンプレートが3種類以上必要"


def test_template_names():
    from src.video.templates import list_names
    names = list_names()
    assert "shock"   in names
    assert "cleanup" in names
    assert "ai_user" in names


def test_template_required_keys():
    from src.video.templates import load
    for name in ["shock", "cleanup", "ai_user"]:
        t = load(name)
        for key in ["hook_text", "middle_text", "cta_text",
                    "max_duration", "output_width", "output_height",
                    "font_size_hook", "font_size_middle", "font_size_cta"]:
            assert key in t, f"テンプレート '{name}' に '{key}' がない"


def test_template_dimensions():
    from src.video.templates import load
    for name in ["shock", "cleanup", "ai_user"]:
        t = load(name)
        assert t["output_width"]  == 1080
        assert t["output_height"] == 1920


def test_template_invalid_name():
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, '.'); from src.video.templates import load; load('nonexistent')"],
        capture_output=True,
    )
    assert result.returncode != 0, "存在しないテンプレートでは終了コード非0を返すべき"


def test_font_finder_returns_path_or_none():
    from src.video.generator import find_font
    result = find_font()
    assert result is None or Path(result).exists(), "フォントパスが存在しないパスを返してはならない"


def test_text_overlay_shape():
    from src.video.generator import _text_overlay
    arr = _text_overlay("テスト", 1080, 1920, None, 60, 0.5)
    assert arr.shape == (1920, 1080, 4), f"shape mismatch: {arr.shape}"


def test_blurred_bg_shape():
    import numpy as np
    from src.video.generator import _blurred_bg
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    result = _blurred_bg(frame, 1080, 1920)
    assert result.shape == (1920, 1080, 3), f"shape mismatch: {result.shape}"


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS {fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL {fn.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
