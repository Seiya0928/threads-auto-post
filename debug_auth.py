"""
debug_auth.py — Threads API 認証診断スクリプト

GitHub Actions の workflow_dispatch で実行してトークンの状態を確認する。
トークンの値は絶対にログに出力しない。
"""

import os
import sys
import json
import requests

API = "https://graph.threads.net/v1.0"


def check(label, ok):
    mark = "✅" if ok else "❌"
    print(f"  {mark} {label}")
    return ok


def main():
    token = os.environ.get("THREADS_ACCESS_TOKEN", "")

    print("=" * 50)
    print("Threads API 認証診断")
    print("=" * 50)

    # 1. トークンの存在確認
    if not token:
        check("THREADS_ACCESS_TOKEN が設定されている", False)
        print("\n→ GitHub Secrets に THREADS_ACCESS_TOKEN を登録してください")
        sys.exit(1)

    token_len = len(token)
    token_prefix = token[:4]
    check(f"THREADS_ACCESS_TOKEN が設定されている (長さ={token_len}, 先頭={token_prefix}...)", True)

    # 2. /me エンドポイント呼び出し
    print("\n--- /me エンドポイントテスト ---")
    resp = requests.get(
        f"{API}/me",
        params={"fields": "id,username,threads_profile_picture_url", "access_token": token},
        timeout=15,
    )

    print(f"  HTTPステータス: {resp.status_code}")

    if resp.status_code == 200:
        data = resp.json()
        check("/me 呼び出し成功", True)
        print(f"\n  ✅ USER_ID   = {data.get('id')}")
        print(f"  ✅ USERNAME  = @{data.get('username')}")
        print(f"\n→ GitHub Secrets に登録する値:")
        print(f"     THREADS_USER_ID = {data.get('id')}")
    else:
        error = resp.json().get("error", {})
        check("/me 呼び出し失敗", False)
        print(f"\n  エラーコード  : {error.get('code')}")
        print(f"  エラー種別    : {error.get('type')}")
        print(f"  エラーメッセージ: {error.get('message')}")

        code = error.get("code")
        if code == 190:
            msg = error.get("message", "")
            if "Cannot parse" in msg:
                print("\n【原因】トークンの形式が正しくありません")
                print("【対処】Threads API Explorer でトークンを再生成してください")
                print("        URL: https://developers.facebook.com/tools/explorer/")
                print("        ※ 通常の Graph API Explorer ではなく「Threads API」専用のトークンが必要")
            elif "expired" in msg.lower():
                print("\n【原因】トークンの有効期限が切れています")
                print("【対処】長期トークン（Long-lived Token）を再生成してください")
            else:
                print(f"\n【原因】OAuth認証エラー: {msg}")
        elif code == 200:
            print("\n【原因】threads_basic 権限がありません")
            print("【対処】アプリのタイプを確認してください（Threadsアプリである必要があります）")
        sys.exit(1)

    # 3. 投稿権限の確認
    print("\n--- 投稿権限テスト (コンテナ作成のみ・実際には投稿しない) ---")
    uid = resp.json().get("id")
    test_resp = requests.post(
        f"{API}/{uid}/threads",
        params={
            "media_type": "TEXT",
            "text": "【テスト】権限確認用（このコンテナは公開しません）",
            "access_token": token,
        },
        timeout=15,
    )

    if test_resp.status_code == 200:
        container_id = test_resp.json().get("id")
        check(f"threads_content_publish 権限あり (container_id={container_id})", True)
        print("\n✅ すべての確認が完了しました。投稿可能な状態です。")
    else:
        err = test_resp.json().get("error", {})
        check("threads_content_publish 権限テスト失敗", False)
        print(f"  エラー: {err.get('message')}")
        print("\n【対処】アプリに threads_content_publish 権限を追加してください")

    print("=" * 50)


if __name__ == "__main__":
    main()
