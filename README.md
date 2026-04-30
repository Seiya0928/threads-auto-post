# threads-auto-post

Threads 自動投稿リポジトリです。現在の主用途は次の 2 レーンです。

- ビジネスアカウント向け Threads 自動投稿
- 楽天アフィリエイト用 Threads 投稿レーン

停止中・実験中・旧運用のコードは `archive/` に退避しています。作業前に必ず [PROJECT_STATUS.md](/Users/apple/threads-auto-post/PROJECT_STATUS.md) を確認してください。

## 現在の主要ファイル

### ビジネスアカウント
- workflow: [.github/workflows/post_business.yml](/Users/apple/threads-auto-post/.github/workflows/post_business.yml)
- entrypoint: [main_business.py](/Users/apple/threads-auto-post/main_business.py)
- prompts: [config/business_prompts.json](/Users/apple/threads-auto-post/config/business_prompts.json)
- generator: [src/business/content_generator.py](/Users/apple/threads-auto-post/src/business/content_generator.py)

### 楽天アフィリエイト用
- workflow: [.github/workflows/post_rakuten.yml](/Users/apple/threads-auto-post/.github/workflows/post_rakuten.yml)
- entrypoint: [main_rakuten.py](/Users/apple/threads-auto-post/main_rakuten.py)
- prompts: [config/rakuten_prompts.json](/Users/apple/threads-auto-post/config/rakuten_prompts.json)
- generator: [src/rakuten/content_generator.py](/Users/apple/threads-auto-post/src/rakuten/content_generator.py)

### 共通
- Threads client: [src/threads_client.py](/Users/apple/threads-auto-post/src/threads_client.py)
- token helpers:
  - [get_token.py](/Users/apple/threads-auto-post/get_token.py)
  - [refresh_token.py](/Users/apple/threads-auto-post/refresh_token.py)
  - [debug_auth.py](/Users/apple/threads-auto-post/debug_auth.py)

## セットアップ

```bash
pip install -r requirements.txt
```

## 楽天レーンの手動テスト

```bash
python3 -m py_compile main_rakuten.py src/rakuten/content_generator.py
DRY_RUN=true python3 main_rakuten.py
```

必要な環境変数:
- `RAKUTEN_THREADS_ACCESS_TOKEN`
- `RAKUTEN_THREADS_USER_ID`
- `RAKUTEN_AFFILIATE_URL`
- `GROQ_API_KEY`

楽天アフィリエイトリンク付き投稿では、本文に毎回 `PR｜楽天アフィリエイトリンクを含みます` を入れる設計です。

## ビジネスレーン

現在の稼働レーンです。変更前に必ず `post_business.yml` / `main_business.py` / `config/business_prompts.json` / `src/business/` を確認してください。

## Threads API トークン取得

```bash
python get_token.py
python debug_auth.py
```

`get_token.py` の redirect URI は `https://oauth.pstmn.io/v1/callback` を使います。

## 停止中コードについて

- 停止中の旧 Threads 美容レーン
- X 下書き生成
- Instagram キャプション生成
- 停止済み workflow

これらは `archive/` に隔離しています。詳細は [PROJECT_STATUS.md](/Users/apple/threads-auto-post/PROJECT_STATUS.md) を参照してください。
