"""
src/video/generator.py — ショート動画生成コア

処理フロー:
  1. 入力動画を読み込み、max_duration にトリミング
  2. 最初のフレームからぼかし拡大背景を生成
  3. 元動画を 9:16 内にフィットさせて中央配置
  4. フック / 補足 / CTA テキストを時間指定でオーバーレイ
  5. 1080x1920 / H.264 で書き出し

依存: moviepy>=1.0.3,<2.0  ffmpeg（moviepy が自動利用）
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

log = logging.getLogger(__name__)

# ── 日本語フォント候補リスト ────────────────────────────────────────────────
_FONT_CANDIDATES = [
    # macOS
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    # Linux (Noto CJK)
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    # Windows
    "C:/Windows/Fonts/msgothic.ttc",
    "C:/Windows/Fonts/YuGothic.ttf",
]


def find_font(hint: Optional[str] = None) -> Optional[str]:
    """日本語対応フォントパスを返す。見つからない場合は None。"""
    # プロジェクト内 fonts/ ディレクトリを優先
    project_fonts = Path(__file__).parent.parent.parent / "fonts"
    if project_fonts.exists():
        for f in project_fonts.glob("*.tt[fc]"):
            log.info(f"プロジェクト内フォント使用: {f}")
            return str(f)

    if hint and Path(hint).exists():
        return hint

    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            log.info(f"フォント発見: {path}")
            return path

    # fc-match で探す（Linux）
    try:
        result = subprocess.run(
            ["fc-match", ":lang=ja", "--format=%{file}"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            fp = result.stdout.strip()
            if fp and Path(fp).exists():
                log.info(f"fc-match フォント: {fp}")
                return fp
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    log.warning("日本語フォントが見つかりません。テキストが正しく表示されない場合があります。")
    return None


def _load_font(path: Optional[str], size: int) -> ImageFont.FreeTypeFont:
    """フォントを読み込む。失敗時は PIL デフォルト。"""
    if path:
        for idx in (0, 1, None):
            try:
                kwargs = {"index": idx} if idx is not None else {}
                return ImageFont.truetype(path, size, **kwargs)
            except Exception:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """テキストを max_width px 以内で折り返す（日本語対応）。"""
    dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines, current = [], ""
    for ch in text:
        test = current + ch
        w = dummy.textbbox((0, 0), test, font=font)[2]
        if w > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = test
    if current:
        lines.append(current)
    return lines or [text]


def _text_overlay(
    text: str,
    w: int,
    h: int,
    font_path: Optional[str],
    font_size: int,
    y_ratio: float,
    outline: int = 4,
) -> np.ndarray:
    """
    テキストオーバーレイ用 RGBA numpy 配列を返す。
    y_ratio: テキスト中央の縦位置（0.0=上端, 1.0=下端）
    """
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _load_font(font_path, font_size)

    lines = _wrap_text(text, font, w - 100)
    lh = int(font_size * 1.25)
    total_h = len(lines) * lh - int(font_size * 0.25)
    y = int(h * y_ratio) - total_h // 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        x = (w - lw) // 2
        # 黒縁取り
        for dx in range(-outline, outline + 1):
            for dy in range(-outline, outline + 1):
                if dx or dy:
                    draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0, 220))
        # 白文字
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += lh

    return np.array(img)


def _cta_overlay(
    text: str,
    w: int,
    h: int,
    font_path: Optional[str],
    font_size: int,
    y_ratio: float = 0.87,
) -> np.ndarray:
    """
    CTA 用オーバーレイ。半透明黒背景 + 白文字。
    """
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _load_font(font_path, font_size)

    lines = _wrap_text(text, font, w - 120)
    lh = int(font_size * 1.25)
    total_h = len(lines) * lh - int(font_size * 0.25)

    pad_x, pad_y = 50, 28
    bg_w = min(w - 80, max(line_bbox(draw, l, font) for l in lines) + pad_x * 2)
    bg_h = total_h + pad_y * 2
    bg_x = (w - bg_w) // 2
    bg_y = int(h * y_ratio) - bg_h // 2

    # 半透明背景（rounded_rectangle は Pillow 8.2+）
    try:
        draw.rounded_rectangle(
            [bg_x, bg_y, bg_x + bg_w, bg_y + bg_h],
            radius=20, fill=(15, 15, 15, 210),
        )
    except AttributeError:
        draw.rectangle([bg_x, bg_y, bg_x + bg_w, bg_y + bg_h], fill=(15, 15, 15, 210))

    y = bg_y + pad_y
    for line in lines:
        bw = line_bbox(draw, line, font)
        x = (w - bw) // 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += lh

    return np.array(img)


def line_bbox(draw: ImageDraw.Draw, text: str, font) -> int:
    """テキスト幅を返すヘルパー。"""
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]


def _blurred_bg(frame: np.ndarray, out_w: int, out_h: int) -> np.ndarray:
    """フレームをぼかして out_w x out_h の背景画像を生成する。"""
    img = Image.fromarray(frame)
    iw, ih = img.size
    scale = max(out_w / iw, out_h / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    # cover crop
    l = (nw - out_w) // 2
    t = (nh - out_h) // 2
    img = img.crop((l, t, l + out_w, t + out_h))
    img = img.filter(ImageFilter.GaussianBlur(radius=30))
    img = img.point(lambda p: int(p * 0.55))  # 暗め
    return np.array(img)


def _make_text_clip(arr: np.ndarray, start: float, end: float):
    """RGBA numpy 配列から moviepy ImageClip（マスク付き）を生成する。"""
    from moviepy.editor import ImageClip
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3].astype(float) / 255.0
    clip = (
        ImageClip(rgb)
        .set_mask(ImageClip(alpha, ismask=True))
        .set_duration(end - start)
        .set_start(start)
    )
    return clip


def generate_short_video(
    input_path: str,
    output_path: str,
    template: dict,
    font_path: Optional[str] = None,
    fps: int = 30,
    keep_audio: bool = False,
) -> None:
    """
    ショート動画を生成してファイルに書き出す。

    Args:
        input_path:  入力 mp4 パス
        output_path: 出力 mp4 パス
        template:    テンプレート設定辞書
        font_path:   フォントパス（None=自動検出）
        fps:         出力 FPS
        keep_audio:  入力音声を保持するか
    """
    try:
        from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
    except ImportError:
        raise RuntimeError(
            "moviepy がインストールされていません。\n"
            "  pip install 'moviepy>=1.0.3,<2.0'\n"
            "また ffmpeg も必要です（brew install ffmpeg）。"
        )

    input_path  = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(f"入力ファイルが見つかりません: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if font_path is None:
        font_path = find_font()

    out_w     = template.get("output_width",  1080)
    out_h     = template.get("output_height", 1920)
    max_dur   = template.get("max_duration",  15)
    hook_txt  = template.get("hook_text",     "")
    mid_txt   = template.get("middle_text",   "")
    cta_txt   = template.get("cta_text",      "")
    fs_hook   = template.get("font_size_hook",   72)
    fs_mid    = template.get("font_size_middle", 56)
    fs_cta    = template.get("font_size_cta",    60)

    log.info(f"読み込み: {input_path}")
    clip = VideoFileClip(str(input_path))

    duration = min(clip.duration, max_dur)
    if clip.duration > max_dur:
        log.info(f"トリミング: {clip.duration:.1f}s → {max_dur}s")
        clip = clip.subclip(0, max_dur)

    # ── 背景（ぼかし静止画） ────────────────────────────────────────────────
    bg_arr  = _blurred_bg(clip.get_frame(0), out_w, out_h)
    bg_clip = ImageClip(bg_arr).set_duration(duration)

    # ── 前景動画（アスペクト比維持でフィット） ────────────────────────────
    cw, ch  = clip.size
    scale   = min(out_w / cw, out_h / ch)
    fg_clip = clip.resize((int(cw * scale), int(ch * scale))).set_position("center")

    # ── テキストタイミング ────────────────────────────────────────────────
    if duration <= 4.0:
        t_hook  = (0,              duration * 0.45)
        t_mid   = (duration * 0.35, duration * 0.70)
        t_cta   = (duration * 0.65, duration)
    else:
        t_hook  = (0,              2.2)
        t_mid   = (2.0,            duration - 1.8)
        t_cta   = (duration - 1.8, duration)

    # ── テキストクリップ ──────────────────────────────────────────────────
    clips = [bg_clip, fg_clip]

    if hook_txt:
        arr = _text_overlay(hook_txt, out_w, out_h, font_path, fs_hook, 0.18)
        clips.append(_make_text_clip(arr, *t_hook))

    if mid_txt and (t_mid[1] - t_mid[0]) > 0.3:
        arr = _text_overlay(mid_txt, out_w, out_h, font_path, fs_mid, 0.62)
        clips.append(_make_text_clip(arr, *t_mid))

    if cta_txt:
        arr = _cta_overlay(cta_txt, out_w, out_h, font_path, fs_cta)
        clips.append(_make_text_clip(arr, *t_cta))

    # ── コンポジット & 書き出し ──────────────────────────────────────────
    final = CompositeVideoClip(clips, size=(out_w, out_h)).set_duration(duration)

    write_kw: dict = dict(
        codec="libx264",
        fps=fps,
        threads=4,
        ffmpeg_params=["-crf", "23", "-pix_fmt", "yuv420p", "-profile:v", "main"],
    )
    if keep_audio and clip.audio is not None:
        write_kw["audio_codec"] = "aac"
    else:
        write_kw["audio"] = False

    # moviepy バージョンによって logger パラメータ有無が異なる
    try:
        final.write_videofile(str(output_path), logger=None, **write_kw)
    except TypeError:
        final.write_videofile(str(output_path), **write_kw)

    clip.close()
    final.close()
    log.info(f"完成: {output_path}")
