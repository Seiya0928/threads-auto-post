"""
imgur_uploader.py — 画像ファイルを Imgur にアップロードして公開URLを返す

Threads API は画像の直接アップロード非対応のため、
Imgur で公開URLを取得してから投稿する。

Imgur Client ID の取得:
  https://api.imgur.com/oauth2/addclient
  → "OAuth 2 authorization without a callback URL" を選択（無料・メールのみ）
"""

import logging
from pathlib import Path

import requests

log = logging.getLogger(__name__)

IMGUR_UPLOAD_URL = "https://api.imgur.com/3/image"


def upload_image(image_path: Path, client_id: str) -> str:
    """
    画像ファイルを Imgur にアップロードして公開URLを返す。

    Args:
        image_path: アップロードする画像ファイルのパス
        client_id:  Imgur の Client ID

    Returns:
        公開URL (例: https://i.imgur.com/xxxxxxx.jpg)

    Raises:
        requests.HTTPError: アップロード失敗時
    """
    with open(image_path, "rb") as f:
        resp = requests.post(
            IMGUR_UPLOAD_URL,
            headers={"Authorization": f"Client-ID {client_id}"},
            files={"image": f},
            timeout=30,
        )

    resp.raise_for_status()
    url = resp.json()["data"]["link"]
    log.info(f"Imgur アップロード完了: {url}")
    return url
