"""
threads_client.py — Threads API (graph.threads.net) のラッパー

投稿フロー:
  1. コンテナ作成  POST /{user_id}/threads
  2. 公開          POST /{user_id}/threads_publish
"""

import logging
import time
from pathlib import Path
from typing import Optional

import requests

log = logging.getLogger(__name__)

THREADS_API = "https://graph.threads.net/v1.0"


class ThreadsClient:
    def __init__(self, access_token: str):
        self.token = access_token
        self._user_id: Optional[str] = None

    # ------------------------------------------------------------------
    # ユーザー情報
    # ------------------------------------------------------------------

    @property
    def user_id(self) -> str:
        if self._user_id is None:
            resp = requests.get(
                f"{THREADS_API}/me",
                params={"fields": "id,username", "access_token": self.token},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            self._user_id = data["id"]
            log.info(f"Threads ユーザー: @{data.get('username')} (id={self._user_id})")
        return self._user_id

    # ------------------------------------------------------------------
    # コンテナ作成
    # ------------------------------------------------------------------

    def _create_container(self, payload: dict) -> str:
        payload["access_token"] = self.token
        resp = requests.post(
            f"{THREADS_API}/{self.user_id}/threads",
            params=payload,
            timeout=15,
        )
        if not resp.ok:
            log.error(f"コンテナ作成エラー {resp.status_code}: {resp.text}")
        resp.raise_for_status()
        container_id = resp.json()["id"]
        log.info(f"コンテナ作成: {container_id}")
        return container_id

    def create_text_container(self, text: str) -> str:
        return self._create_container({"media_type": "TEXT", "text": text})

    def create_image_container(self, image_url: str, text: str) -> str:
        return self._create_container({
            "media_type": "IMAGE",
            "image_url": image_url,
            "text": text,
        })

    # ------------------------------------------------------------------
    # 公開
    # ------------------------------------------------------------------

    def publish(self, container_id: str, wait_sec: int = 5, max_retries: int = 3) -> str:
        """コンテナを公開してスレッドIDを返す。500系の一時エラーはリトライする。"""
        time.sleep(wait_sec)
        for attempt in range(1, max_retries + 1):
            resp = requests.post(
                f"{THREADS_API}/{self.user_id}/threads_publish",
                params={"creation_id": container_id, "access_token": self.token},
                timeout=15,
            )
            if resp.ok:
                thread_id = resp.json()["id"]
                log.info(f"公開成功: thread_id={thread_id}")
                return thread_id

            is_transient = resp.json().get("error", {}).get("is_transient", False)
            log.error(f"公開エラー {resp.status_code} (attempt {attempt}): {resp.text}")
            if is_transient and attempt < max_retries:
                wait = 10 * attempt  # 10s → 20s
                log.info(f"一時エラーのためリトライ待機 {wait}s...")
                time.sleep(wait)
            else:
                resp.raise_for_status()

    # ------------------------------------------------------------------
    # 便利メソッド
    # ------------------------------------------------------------------

    def post_text(self, text: str) -> str:
        container_id = self.create_text_container(text)
        return self.publish(container_id)

    def post_image(self, image_url: str, text: str) -> str:
        container_id = self.create_image_container(image_url, text)
        return self.publish(container_id)

    # ------------------------------------------------------------------
    # 冪等性チェック
    # ------------------------------------------------------------------

    def get_post_metrics(self, thread_id: str) -> dict:
        """投稿のviews/likes/repliesを取得する。失敗時は空dict。"""
        try:
            resp = requests.get(
                f"{THREADS_API}/{thread_id}/insights",
                params={
                    "metric": "views,likes,replies,reposts,quotes",
                    "access_token": self.token,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
            return {item["name"]: item.get("values", [{}])[-1].get("value", 0) for item in data}
        except Exception as e:
            log.warning(f"メトリクス取得失敗 thread_id={thread_id}: {e}")
            return {}

    def was_recently_posted(self, within_hours: int = 2) -> bool:
        """指定時間内に投稿済みかどうかを確認する。確認失敗時は安全側（False）を返す。"""
        try:
            resp = requests.get(
                f"{THREADS_API}/{self.user_id}/threads",
                params={
                    "fields": "id,timestamp",
                    "limit": 5,
                    "access_token": self.token,
                },
                timeout=15,
            )
            resp.raise_for_status()
            posts = resp.json().get("data", [])
            if not posts:
                return False
            cutoff = time.time() - within_hours * 3600
            for post in posts:
                ts = post.get("timestamp", "")
                if ts:
                    import datetime
                    post_time = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if post_time.timestamp() > cutoff:
                        log.info(f"直近{within_hours}時間以内の投稿を検出: id={post['id']} at {ts}")
                        return True
            return False
        except Exception as e:
            log.warning(f"直近投稿チェック失敗（スキップ判定せず続行）: {e}")
            return False
