"""
get_token.py — Threads API 用の長期トークンを取得するヘルパー

【使い方】
  1. python get_token.py
  2. 表示されたURLをブラウザで開く
  3. Threads でログイン・許可する
  4. リダイレクト先のURL（localhost）をコピーしてターミナルに貼り付ける
  5. 長期トークンと USER_ID が表示される → GitHub Secrets に登録する
"""

import sys
import urllib.parse
import requests

# ── ここに入力 ────────────────────────────────────────
APP_ID     = input("App ID を入力してください（数字のみ）: ").strip()
APP_SECRET = input("App Secret を入力してください: ").strip()
REDIRECT   = "https://localhost"
# ─────────────────────────────────────────────────────

# 入力値の検証
if not APP_ID:
    print("❌ App ID が空です。数字のみのIDを入力してください。")
    sys.exit(1)

if not APP_ID.isdigit():
    print(f"❌ App ID に数字以外が含まれています: '{APP_ID}'")
    print("   スペース・改行・記号が混入していないか確認してください。")
    sys.exit(1)

print(f"\n✅ App ID 確認: {APP_ID} (長さ={len(APP_ID)}文字)")

SCOPES = "threads_basic,threads_content_publish"

auth_url = (
    "https://www.threads.net/oauth/authorize"
    f"?client_id={APP_ID}"
    f"&redirect_uri={urllib.parse.quote(REDIRECT, safe='')}"
    f"&scope={SCOPES}"
    "&response_type=code"
)

print("\n" + "=" * 60)
print("Step 1: 以下のURLをブラウザで開いてください")
print("=" * 60)
print(auth_url)
print()
print(f"※ URLに client_id={APP_ID} が含まれていることを確認してください")
print()

redirected = input("ログイン・許可後にリダイレクトされたURL全体を貼り付けてください:\n> ").strip()

# code を取り出す
parsed = urllib.parse.urlparse(redirected)
params = urllib.parse.parse_qs(parsed.query)
code = params.get("code", [""])[0].split("#")[0]  # "#_" を除去

if not code:
    print("❌ code が取得できませんでした。URLを確認してください。")
    sys.exit(1)

print(f"\ncode 取得: {code[:20]}...")

# ── 短期トークン取得 ──────────────────────────────────
print("\nStep 2: 短期トークンを取得中...")
r = requests.post(
    "https://graph.threads.net/oauth/access_token",
    data={
        "client_id":     APP_ID,
        "client_secret": APP_SECRET,
        "grant_type":    "authorization_code",
        "redirect_uri":  REDIRECT,
        "code":          code,
    },
    timeout=15,
)

if not r.ok:
    print(f"❌ 短期トークン取得失敗: {r.json()}")
    sys.exit(1)

short_token = r.json()["access_token"]
user_id     = r.json()["user_id"]
print(f"✅ 短期トークン取得成功  (USER_ID = {user_id})")

# ── 長期トークン取得（60日間有効）────────────────────
print("\nStep 3: 長期トークン（60日）に交換中...")
r2 = requests.get(
    "https://graph.threads.net/access_token",
    params={
        "grant_type":    "th_exchange_token",
        "client_secret": APP_SECRET,
        "access_token":  short_token,
    },
    timeout=15,
)

if not r2.ok:
    print(f"❌ 長期トークン取得失敗: {r2.json()}")
    sys.exit(1)

long_token  = r2.json()["access_token"]
expires_in  = r2.json().get("expires_in", 0)
expires_days = expires_in // 86400

print(f"✅ 長期トークン取得成功（有効期限: 約{expires_days}日）")

print("\n" + "=" * 60)
print("GitHub Secrets に登録する値")
print("=" * 60)
print(f"THREADS_ACCESS_TOKEN = {long_token}")
print(f"THREADS_USER_ID      = {user_id}")
print("=" * 60)
print("\n※ このトークンは約60日で失効します。期限が近づいたら再実行してください。")
