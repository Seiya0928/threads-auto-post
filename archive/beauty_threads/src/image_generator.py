"""
image_generator.py — Pollinations.ai (完全無料・登録不要) でAI美容画像を生成する
APIキー不要、商用利用可
"""

import logging
import time
import urllib.parse
from pathlib import Path
from typing import Optional, List

import requests
from PIL import Image
from io import BytesIO

log = logging.getLogger(__name__)

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"

# スキンケア・美容系のデフォルトスタイル
DEFAULT_STYLE = (
    "beautiful japanese woman, skincare beauty portrait, "
    "flawless skin, soft natural lighting, clean minimal background, "
    "high quality, 4k, professional photo"
)

SKINCARE_PROMPTS = [
    f"{DEFAULT_STYLE}, applying face cream, morning routine",
    f"{DEFAULT_STYLE}, fresh glowing skin, serum bottle, elegant",
    f"{DEFAULT_STYLE}, sheet mask, relaxing spa atmosphere",
    f"{DEFAULT_STYLE}, natural makeup, botanical skincare products",
    f"{DEFAULT_STYLE}, sunlit window, healthy radiant complexion",
]


def generate_image(
    prompt: str,
    save_path: Path,
    width: int = 1024,
    height: int = 1024,
    seed: Optional[int] = None,
) -> Optional[Path]:
    """
    Pollinations.ai でプロンプトから画像を生成してファイルに保存する。
    タイムアウト・429 に対してリトライ（最大3回）。
    """
    encoded_prompt = urllib.parse.quote(prompt)
    params = f"?width={width}&height={height}&nologo=true"
    if seed is not None:
        params += f"&seed={seed}"

    url = POLLINATIONS_URL.format(prompt=encoded_prompt) + params

    for attempt in range(3):
        try:
            log.info(f"画像生成中 (試行{attempt + 1}/3): {prompt[:60]}...")
            response = requests.get(url, timeout=120)
            response.raise_for_status()

            img = Image.open(BytesIO(response.content))
            img.save(save_path)
            log.info(f"画像保存: {save_path}")
            return save_path

        except requests.exceptions.Timeout:
            wait = 30 * (attempt + 1)
            log.warning(f"タイムアウト。{wait}秒待機して再試行...")
            time.sleep(wait)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                wait = 60 * (attempt + 1)
                log.warning(f"レートリミット(429)。{wait}秒待機して再試行...")
                time.sleep(wait)
            else:
                log.error(f"HTTPエラー: {e}")
                return None
        except requests.RequestException as e:
            log.error(f"画像生成失敗: {e}")
            return None

    log.error(f"3回リトライ失敗: {prompt[:60]}")
    return None


def generate_batch(
    prompts: List[str],
    output_folder: Path,
    interval_sec: int = 30,
) -> List[Path]:
    """複数プロンプトをまとめて生成する。"""
    output_folder.mkdir(parents=True, exist_ok=True)
    results = []

    for i, prompt in enumerate(prompts):
        filename = f"skincare_{int(time.time())}_{i:03d}.jpg"
        save_path = output_folder / filename
        result = generate_image(prompt, save_path)
        if result:
            results.append(result)
        if i < len(prompts) - 1:
            time.sleep(interval_sec)

    log.info(f"バッチ完了: {len(results)}/{len(prompts)}枚生成")
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    out = Path(__file__).parent.parent / "images"
    generate_batch(SKINCARE_PROMPTS[:2], out)
