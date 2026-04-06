# skin-journal / x-ai-poster

スキンケア美容アカウント用の自動投稿・下書き生成システム。

---

## 機能

### 1. Threads 自動投稿（個人アカウント）
- **スケジュール**: 毎日 07:30 JST・21:30 JST
- **内容**: スキンケア・美容系テキスト投稿（Gemini AI生成）
- **特徴**: A/Bテスト（list vs paragraph形式）、Googleトレンド活用
- **ワークフロー**: `.github/workflows/post.yml`
- **エントリーポイント**: `post_once.py`

### 2. Threads 自動投稿（ビジネスアカウント）
- **スケジュール**: 毎日 08:00 JST・22:00 JST
- **内容**: AI副業・自動化テーマの投稿
- **ワークフロー**: `.github/workflows/post_business.yml`
- **エントリーポイント**: `main_business.py`

### 3. X 投稿下書き自動生成
- **スケジュール**: 毎日 22:00 JST（UTC 13:00）
- **内容**: スキンケア・美容テーマの下書きを 3〜5 本生成してファイル保存
- **自動投稿はしない**（手動投稿用の下書き）
- **保存先**: `x_drafts/YYYY-MM-DD.txt`
- **ワークフロー**: `.github/workflows/generate_x_drafts.yml`
- **エントリーポイント**: `generate_x_drafts.py`

---

## X 下書き生成の詳細

### アカウント設定
- テーマ: スキンケア・美容（トレチノイン×ハイドロキノン療法がコア）
- 言語: 日英ミックス
- トーン: ゆるい・等身大の人間っぽい

### 投稿タイプ比率
| タイプ | 比率 | 内容 |
|--------|------|------|
| 知識系 | 40% | スキンケアtips・成分解説（日英ミックス） |
| 体験系 | 25% | 施術・変化の記録（日本語中心） |
| 共感系 | 20% | あるある・独り言（短め・英語OK） |
| 反応系 | 15% | ミームへのコメント（カジュアル） |

### 出力フォーマット（`x_drafts/2026-04-07.txt`）
```
[1/4] 知識系
トレチノインを使い始めて最初の2週間、肌が荒れるのは正常。これ知らなくて辞める人が多すぎる。
The "purging phase" is real — give it 4-6 weeks before judging results.
---
[2/4] 体験系
レーザー4回目終わった。シミが薄くなってきてるのは確かだけど、ダウンタイムの赤みがしんどい。美容は我慢と投資だなと毎回思う。
---
```

### 必要なシークレット
- `GEMINI_API_KEY`（Threadsと共用）

---

## セットアップ

### GitHub Secrets
| シークレット名 | 用途 |
|----------------|------|
| `THREADS_ACCESS_TOKEN` | 個人Threadsアカウントのトークン |
| `THREADS_USER_ID` | 個人ThreadsユーザーID |
| `BUSINESS_THREADS_ACCESS_TOKEN` | ビジネスアカウントのトークン |
| `BUSINESS_THREADS_USER_ID` | ビジネスアカウントのユーザーID |
| `GEMINI_API_KEY` | Google Gemini APIキー |
| `AFFILIATE_URL` | アフィリエイトリンク（任意） |

### ローカル開発
```bash
# 依存インストール
pip install -r requirements.txt

# X下書きを手動生成（テスト）
GEMINI_API_KEY=your_key python generate_x_drafts.py

# Threads投稿テスト
THREADS_ACCESS_TOKEN=your_token GEMINI_API_KEY=your_key python post_once.py

# トークン取得
python get_token.py

# トークン診断
python debug_auth.py
```
