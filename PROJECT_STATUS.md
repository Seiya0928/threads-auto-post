# PROJECT_STATUS

今後AIエージェントがこのリポジトリで作業する場合、まずこの PROJECT_STATUS.md を読み、archive/ 配下は明示指示がない限り読まない・編集しないこと。

## 現在稼働中の仕組み

### 1. ビジネスアカウント Threads 自動投稿
- workflow: [.github/workflows/post_business.yml](/Users/apple/threads-auto-post/.github/workflows/post_business.yml)
- entrypoint: [main_business.py](/Users/apple/threads-auto-post/main_business.py)
- prompts: [config/business_prompts.json](/Users/apple/threads-auto-post/config/business_prompts.json)
- generator: [src/business/content_generator.py](/Users/apple/threads-auto-post/src/business/content_generator.py)
- logs:
  - [data/business_post_log.csv](/Users/apple/threads-auto-post/data/business_post_log.csv)
  - [data/post_log_business.json](/Users/apple/threads-auto-post/data/post_log_business.json)
  - [data/business_last_info.json](/Users/apple/threads-auto-post/data/business_last_info.json)
  - [data/business_last_hashtag.json](/Users/apple/threads-auto-post/data/business_last_hashtag.json)

### 2. 楽天アフィリエイト用 Threads 投稿レーン
- workflow: [.github/workflows/post_rakuten.yml](/Users/apple/threads-auto-post/.github/workflows/post_rakuten.yml)
- entrypoint: [main_rakuten.py](/Users/apple/threads-auto-post/main_rakuten.py)
- prompts: [config/rakuten_prompts.json](/Users/apple/threads-auto-post/config/rakuten_prompts.json)
- generator: [src/rakuten/content_generator.py](/Users/apple/threads-auto-post/src/rakuten/content_generator.py)
- log: [data/post_log_rakuten.json](/Users/apple/threads-auto-post/data/post_log_rakuten.json)

### 3. 共通・保守
- Threads API client: [src/threads_client.py](/Users/apple/threads-auto-post/src/threads_client.py)
- token helpers:
  - [get_token.py](/Users/apple/threads-auto-post/get_token.py)
  - [refresh_token.py](/Users/apple/threads-auto-post/refresh_token.py)
  - [debug_auth.py](/Users/apple/threads-auto-post/debug_auth.py)

## 停止中の仕組み

### 1. 旧 Threads 美容レーン
- 旧 workflow: `post.yml`
- 旧 entrypoint: `main.py`, `post_once.py`
- 旧 generator / scheduler / posting helpers 一式
- 現在は停止済み。現役レーンはビジネス/楽天のみ

### 2. X 下書き自動生成
- 旧 workflow: `generate_x_drafts.yml`
- 旧 script: `generate_x_drafts.py`
- 旧 module: `src/x_draft_generator.py`
- 生成物: `x_drafts/`
- 現在は停止済み

### 3. Instagram キャプション生成・メール送信
- 旧 workflow: `generate_instagram_captions.yml`
- 旧 script: `generate_instagram_captions.py`
- もとの生成先ディレクトリは repo 直下に存在せず、運用継続の痕跡も薄い
- 現在は停止扱い

### 4. 認証診断 workflow
- 旧 workflow: `debug.yml`
- スクリプト自体の [debug_auth.py](/Users/apple/threads-auto-post/debug_auth.py) は残す
- GitHub Actions 経由の定期/手動診断 workflow は archive へ退避

## archive に移したもの

### archive/beauty_threads/
- `main.py`
- `post_once.py`
- `src/content_generator.py`
- `src/trend_fetcher.py`
- `src/scheduler.py`
- `src/poster.py`
- `src/image_generator.py`
- `src/imgur_uploader.py`
- `data/post_log.json`
- `data/used_hooks.json`

### archive/xposter/
- `generate_x_drafts.py`
- `src/x_draft_generator.py`
- `x_drafts/`

### archive/beauty_instagram/
- `generate_instagram_captions.py`

### archive/inactive_workflows/
- `post.yml`
- `debug.yml`
- `generate_x_drafts.yml`
- `generate_instagram_captions.yml`

### archive/old_prompts/
- 該当なし。現時点では移動対象の旧 prompt ファイルなし

## 今後触ってよい主要ファイル

- [main_business.py](/Users/apple/threads-auto-post/main_business.py)
- [main_rakuten.py](/Users/apple/threads-auto-post/main_rakuten.py)
- [src/business/content_generator.py](/Users/apple/threads-auto-post/src/business/content_generator.py)
- [src/rakuten/content_generator.py](/Users/apple/threads-auto-post/src/rakuten/content_generator.py)
- [src/threads_client.py](/Users/apple/threads-auto-post/src/threads_client.py)
- [.github/workflows/post_business.yml](/Users/apple/threads-auto-post/.github/workflows/post_business.yml)
- [.github/workflows/post_rakuten.yml](/Users/apple/threads-auto-post/.github/workflows/post_rakuten.yml)
- [config/business_prompts.json](/Users/apple/threads-auto-post/config/business_prompts.json)
- [config/rakuten_prompts.json](/Users/apple/threads-auto-post/config/rakuten_prompts.json)
- [README.md](/Users/apple/threads-auto-post/README.md)
- [PROJECT_STATUS.md](/Users/apple/threads-auto-post/PROJECT_STATUS.md)

## Codex/Claude が原則読まなくてよいファイル

- `archive/` 配下すべて
- 停止済み workflow の内容
- 旧美容 Threads レーンの generator / scheduler / poster 一式
- X 下書き生成の旧成果物
- Beauty Instagram 用の旧キャプション生成

## 再開条件

- 旧美容 Threads レーン:
  - 対象アカウントの復旧
  - Secrets の有効化
  - 運用再開の明示指示
- X 下書き生成:
  - X 運用再開の明示指示
  - `ANTHROPIC_API_KEY` とメール送信先の再確認
- Instagram キャプション生成:
  - 実運用の再定義
  - 生成先ディレクトリと送信導線の再確認

## 削除候補

すぐ削除しない。次の条件を満たしたら削除候補にできる。

- `archive/beauty_threads/`
  - 旧美容 Threads レーンを今後使わないと確定した場合
- `archive/xposter/`
  - X 下書き運用を今後再開しないと確定した場合
- `archive/beauty_instagram/`
  - Instagram キャプション生成を完全終了すると決めた場合
- `archive/inactive_workflows/`
  - archive 対象コードの削除と同時

## チェック / 動作確認

この整理では、現役レーンに限定して静的チェックを行う。

- `python3 -m py_compile main_business.py main_rakuten.py src/business/content_generator.py src/rakuten/content_generator.py src/threads_client.py`

今回確認した点:
- `package.json` は存在しない
- `tests/` ディレクトリは存在しない
- そのため `npm test` / `pytest` は未実行
- 自動テストの代わりに、現役 Python ファイルの構文チェックのみ実施

補足:
- この repo には今回の整理とは別に、既存の `video` 関連削除差分と `get_token.py` / `README.md` の変更がすでに入っていた
- それらは今回の archive 整理とは切り分けて扱う
