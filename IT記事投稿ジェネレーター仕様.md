# IT記事投稿ジェネレーター仕様

更新日: 2026-06-14  
リポジトリ: `https://github.com/naokoni24/post-generator.git`  
ブランチ: `master`  
対象ファイル: `it_post_generator_rss.py`

## 概要

IT記事投稿ジェネレーターは、RSS / Atom、GitHub Releases、公式Blog / Docs更新、必要に応じて公式X検索を統合し、X投稿用の記事候補を取得する単一ファイルのPython製Webアプリです。

取得した候補は日本語で選びやすい表示に変換し、記事本文の取得とClaude APIによる投稿文生成を行います。

## 基本構成

- 実行方式: Python標準ライブラリの `HTTPServer`
- メインファイル: `it_post_generator_rss.py`
- ローカル起動: `python3 it_post_generator_rss.py`
- デフォルトURL: `http://localhost:8765`
- 外部ライブラリ: なし
- 文章生成 / 翻訳API: Anthropic Claude API
- 使用モデル: `claude-haiku-4-5`

## 環境変数

| 変数 | 必須 | 内容 |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | 投稿生成・翻訳には必須 | Claude APIキー |
| `PORT` | 任意 | Webサーバーのポート。未指定時は `8765` |
| `BASIC_USER` | 任意 | ログイン用ユーザー名 |
| `BASIC_PASS` | 任意 | ログイン用パスワード |
| `COOKIE_SECRET` | 任意 | ログインCookie署名用の秘密文字列 |

`BASIC_USER` と `BASIC_PASS` が未設定の場合、ログイン認証は無効化されます。

## 画面仕様

### 初期状態

- デフォルトカテゴリ: `AI・機械学習`
- デフォルト取得先: `海外`
- デフォルト期間: `今日`
- 公式X: オフ
- 表示件数: 初期20件

### 入力項目

- キーワード検索ボックス
- カテゴリ選択
- 取得先選択
  - `国内`
  - `海外`
- `公式Xも見る` チェックボックス
- 期間選択
  - 今日
  - 1日以内
  - 3日以内
  - 1週間以内
- 感想スタイル
  - 一言感想
  - 問いかけ
  - 実務目線
  - 懸念・考察

### 候補表示

候補カードには以下を表示します。

- 順位
- 日本語タイトル
- 日本語概要
- ソース名
- 公開日
- ソース種別
- 信頼度
- 参照URLを開くボタン

候補取得後の表示例:

```text
20件取得 / AI・機械学習 / 海外 / 今日 / 3日以内で補完 / 追加取得あり / 検索:「Claude」
```

## カテゴリ

現在のカテゴリは以下です。

- AI・機械学習
- クラウド・AWS
- セキュリティ
- 開発
- スタートアップ
- 便利ツール・Tips
- ガジェット・ハードウェア
- ビジネス・DX

## 取得ソース

### RSSニュース

各カテゴリに国内・海外のRSS / Atomフィードを設定しています。

主な国内ソース:

- ITmedia
- CNET Japan
- Publickey
- はてなブックマーク IT
- AINOW
- INTERNET Watch
- PC Watch
- CodeZine
- Zenn
- Qiita 人気記事
- BRIDGE
- 日経XTECH
- Lifehacker Japan
- Gizmodo Japan

主な海外ソース:

- OpenAI Blog
- Google DeepMind Blog
- Hugging Face Blog
- Google AI Blog
- Meta Engineering Blog
- TechCrunch
- VentureBeat
- WIRED
- MIT Technology Review
- Ars Technica
- AWS Blog
- ZDNet
- The New Stack
- Hacker News
- The Hacker News
- Krebs on Security
- Dark Reading
- GitHub Blog
- Stack Overflow Blog
- Smashing Magazine
- Product Hunt
- Engadget
- The Verge

### GitHub Releases

カテゴリごとに主要プロジェクトのGitHub Releases Atomフィードを取得します。

例:

- `openai/openai-python`
- `huggingface/transformers`
- `langchain-ai/langchain`
- `aws/aws-cdk`
- `cloudflare/workers-sdk`
- `aquasecurity/trivy`
- `vercel/next.js`
- `nodejs/node`
- `microsoft/TypeScript`
- `facebook/react`
- `obsidianmd/obsidian-releases`
- `microsoft/vscode`
- `n8n-io/n8n`

### Docs更新 / 公式Blog

公式Blog、Changelog、Release Notes系のフィードを取得します。

例:

- OpenAI News / Docs
- Google Developers Blog
- AWS What's New
- Cloudflare Blog
- Google Cloud Release Notes
- GitHub Changelog
- Vercel Changelog
- Chrome Developers Blog
- Y Combinator Blog
- Stripe Blog
- Google Workspace Updates
- Apple Developer Releases

### 公式X

公式Xは通常検索には混ぜず、`公式Xも見る` をオンにした場合のみ追加します。

公式XはX検索URLを候補として出します。アプリ側でXの投稿本文を直接スクレイピングする構成ではありません。

例:

- OpenAI
- Anthropic
- Google DeepMind
- AWS
- Azure
- Google Cloud
- Microsoft Threat Intelligence
- CISA
- GitHub
- Vercel
- Node.js
- Product Hunt
- Raycast
- Obsidian

## 信頼度スコア

| ソース種別 | 信頼度 |
| --- | ---: |
| GitHub Releases | 95 |
| Docs更新 | 95 |
| 公式Blog | 90 |
| 公式X | 85 |
| RSSニュース | 70 |

## 取得先モード

現在の仕様では、国内と海外は「優先」ではなく完全分離です。

### 国内

国内ソースとして分類されたRSS / Atomを対象にします。

### 海外

海外ソースとして分類されたRSS / Atomを対象にします。

### 注意

国内モードでは海外ソースを混ぜないため、キーワードによっては20件に届かない場合があります。  
例: 国内ソースだけで `AWS` を検索した場合、海外より結果が少なくなることがあります。

## 候補取得ロジック

### 通常検索

カテゴリを選んでキーワードなしで検索する場合:

1. 指定期間で候補を取得
2. 20件未満なら追加取得
3. `今日` 指定で20件未満の場合、3日以内で補完
4. それでも20件未満の場合、7日以内で補完
5. 日時が新しい順で表示

今日の記事を優先し、不足分だけ過去記事で補完します。

### 今日指定

期間が `今日` の場合でも、候補が20件に満たない場合は3日以内、さらに7日以内で補完します。  
そのため、画面上に前日以前の記事が出ることがあります。

ただし並び順は新しい順なので、今日の記事が先に出ます。

### キーワード検索

キーワードありの場合:

- カテゴリ未選択なら全カテゴリを対象
- カテゴリ選択中ならそのカテゴリのみ対象
- 国内/海外モードは維持
- RSS、GitHub Releases、Docs更新も検索対象
- 取得プールを通常より広げる
- 日本語キーワードでも英語記事に当たりやすいよう、候補プールを先に日本語翻訳してから一致判定

キーワード検索の対象期間:

- カテゴリ未選択: 最大90日以内
- カテゴリ選択あり: 最大30日以内

### キーワードのみ検索

キーワードのみでカテゴリを選ばない場合:

- 全カテゴリのフィードを重複除外して取得
- 国内モードなら国内ソースのみ
- 海外モードなら海外ソースのみ
- GitHub Releases / Docs更新も全カテゴリから取得
- 候補プールを最大160件まで翻訳してからキーワード一致判定

## 並び順

最終候補は日時の新しいものから表示します。

通常検索では、同一ソースだけで埋まらないように以下の制御があります。

- 第1パス: 各ソース1件まで
- 第2パス: 各ソース2件まで
- 不足時: 各ソース3件以上も許可
- 最終的に20件確保を優先

## 翻訳仕様

候補タイトル・概要は、Claude APIで日本語表示に変換します。

翻訳対象:

- 英語タイトル
- 英語概要
- GitHub Releases
- Docs更新

翻訳ルール:

- 企業名、サービス名、製品名、人名は英語のまま残す
- 技術用語は自然な日本語にする
- GitHub Releasesはバージョンだけでなく「何のリリースか」が分かるタイトルにする
- 概要は80文字以内

APIキーが未設定の場合、翻訳は実行されません。

## 投稿文生成

記事候補を選択後、参照URL先の本文を取得し、Claude APIでX投稿文を生成します。

投稿文生成では以下を考慮します。

- 記事タイトル
- 記事URL
- 記事本文
- 選択した感想スタイル
- ハッシュタグ
- Xの280文字制限

X文字数カウントは以下のルールです。

- 日本語・CJK文字: 2文字扱い
- 基本ラテン文字など: 1文字扱い
- URL: 23文字扱い

280文字を超えた場合は自動短縮ボタンを表示します。

## APIエンドポイント

| メソッド | パス | 内容 |
| --- | --- | --- |
| `GET` | `/` | メイン画面 |
| `GET` | `/login` | ログイン画面 |
| `POST` | `/login` | ログイン処理 |
| `GET` | `/logout` | ログアウト |
| `GET` | `/api/status` | APIキー設定状態を返す |
| `GET` | `/api/rss` | 記事候補を取得 |
| `GET` | `/api/fetch_article` | 参照URL先の本文を取得 |
| `POST` | `/api/translate_candidates` | 候補タイトル・概要を翻訳 |
| `POST` | `/api/claude` | Claude API経由で投稿文などを生成 |

### `/api/rss` の主なクエリ

| パラメータ | 内容 |
| --- | --- |
| `category` | カテゴリ名。空文字なら全カテゴリ検索 |
| `lang` | `jp` または `en` |
| `include_x` | `1` なら公式X候補を追加 |
| `days` | `0`, `1`, `3`, `7` |
| `keyword` | キーワード検索 |

## キャッシュ・速度改善

### RSSキャッシュ

- RSS取得キャッシュ: 5分
- 取得失敗フィードの一時スキップ: 10分
- 結果キャッシュ: 30分

### タイムアウト

通常取得:

- フィード取得タイムアウト: 1.8秒
- 高速取得予算: 1.2秒
- 最大取得予算: 2.6秒

追加取得:

- フィード取得タイムアウト: 3.5秒
- 高速取得予算: 3.0秒
- 最大取得予算: 7.0秒

キーワード検索時は取得対象が広いため、最初から追加取得相当の予算で取得します。

### 並列取得

- キーワードなし: 最大12並列
- キーワードのみ: 最大30並列
- 翻訳: 最大6バッチ並列

## 認証仕様

`BASIC_USER` と `BASIC_PASS` を設定した場合、ログイン画面が有効になります。

ログイン後は署名付きCookieを保存します。

- Cookie名: `it_post_session`
- 有効期間: 7日
- 署名方式: HMAC SHA-256

## デプロイ想定

RenderでのWeb運用を想定しています。

必要な環境変数:

- `ANTHROPIC_API_KEY`
- `BASIC_USER`
- `BASIC_PASS`
- `COOKIE_SECRET`
- `PORT`

現在、`render.yaml` はリポジトリ内にはありません。Render側のダッシュボード設定で管理する想定です。

## 料金目安

アプリ自体のRSS取得、GitHub Releases取得、Docs更新取得、公式X検索URL生成は無料です。

費用が発生する可能性があるのはClaude APIです。

主なAPI利用箇所:

- 候補の日本語翻訳
- 投稿文生成
- 自動短縮
- タグ生成

1回あたりの費用は記事本文の長さ、翻訳件数、再生成回数により変動します。  
現在は低コストモデル `claude-haiku-4-5` を使う設計です。

## 既知の仕様・注意点

- 国内/海外は完全分離のため、片方のソースだけでは20件に届かない場合があります。
- `今日` 指定でも20件未満なら3日以内、7日以内で補完するため、前日以前の記事が表示されることがあります。
- APIキー未設定のローカル環境では、日本語翻訳と投稿生成は動きません。
- 公式Xは実投稿取得ではなく、公式アカウントのX検索URLを候補として出します。
- RSSフィード側の更新頻度が低いカテゴリでは、当日記事が少なくなることがあります。
- GitHub Releasesはバージョン番号だけのタイトルになりやすいため、翻訳処理で内容が分かるタイトルへ補正しています。

## 最近の主な変更履歴

- 今日の記事を優先し、不足時のみ過去記事で補完するように変更
- キーワード検索時の取得プールを拡大
- キーワードのみ検索でも国内/海外モードを維持
- キーワード検索で翻訳後タイトル・概要に対して一致判定
- 検索結果を日時の新しい順に表示
- 初回取得失敗時の再試行を追加
- 取得結果の表示件数を20件に変更
- 公式Xを常時混在ではなく任意チェックに変更
- URLを翻訳用URLにせず、元の参照URLを開く仕様に戻した
