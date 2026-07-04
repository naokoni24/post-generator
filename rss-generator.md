# IT記事投稿ジェネレーター仕様

更新日: 2026-06-20
リポジトリ: `https://github.com/naokoni24/post-generator`
ブランチ: `main`
対象ファイル: `it_post_generator_rss.py`

## 運用ルール

このプロジェクトを修正する時は、毎回このObsidianノートを読み込んでから作業します。

作業後は以下を行います。

- 実装内容に合わせてこの `rss-generator.md` を更新
- 必要に応じてリポジトリ内の仕様書も更新
- `post-generator.git` の `main` ブランチへpush

push先は必ず `https://github.com/naokoni24/post-generator` です。
公式HP用の `tail_tech_hp.git` にはpushしません。

## 概要

IT記事投稿ジェネレーターは、RSS / Atom、GitHub Releases、公式Blog / Docs更新、必要に応じて公式X検索を統合し、X投稿用の記事候補を取得する単一ファイルのPython製Webアプリです。

取得した候補は日本語で選びやすい表示に変換し、記事本文の取得とClaude APIによる投稿文生成を行います。

## 基本構成

- 実行方式: Python標準ライブラリの `ThreadingHTTPServer`
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
| `SESSION_IDLE_TIMEOUT_SECONDS` | 任意 | 最終操作から自動ログアウトまでの秒数。未指定時は `1800`（30分） |

`BASIC_USER` と `BASIC_PASS` が未設定の場合、ログイン認証は無効化されます。

ログインCookieは最終操作時刻を署名付きトークンとして保持します。認証済みの画面表示/APIアクセスのたびにCookieを再発行し、最終操作から `SESSION_IDLE_TIMEOUT_SECONDS` 秒を超えると次回アクセス時にログイン画面へ戻します。

ブラウザ/PWAが前回画面をメモリ復元した場合でも古い画面が残らないよう、画面復帰時（`pageshow` / `focus` / `visibilitychange`）に `/api/status` へ no-store でアクセスしてサーバー側の認証状態を確認します。期限切れやログイン画面へのリダイレクトが検出された場合は `/login` へ移動します。

## 画面仕様

### 初期状態

- デフォルトカテゴリ: `AI・機械学習`
- デフォルト取得先: `海外`
- デフォルト期間: `今日`
- 公式X: オフ
- 表示件数: 初期20件
- 候補取得中はキャンセルボタンを表示

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
- 取得中キャンセル
  - 取得中だけ `キャンセル` ボタンを表示
  - クリックするとブラウザ側の取得を中断
  - 同時にサーバー側へ `/api/cancel` を送り、該当 `request_id` の取得処理を停止
- 感想スタイル
  - 記事選択後、画面下部の `投稿文を生成` ボタン直上に表示
  - 選択した記事に対する投稿生成時だけ利用可能

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
12件取得 / AI・機械学習 / 海外 / 今日 / 検索:「Claude」
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

- ITmedia（AI、Enterprise、NEWS、ビジネス、セキュリティ）
- CNET Japan
- Publickey
- はてなブックマーク IT
- AINOW
- INTERNET Watch
- PC Watch
- ケータイ Watch
- クラウド Watch
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
- Google Research Blog
- Meta Engineering Blog
- TechCrunch（AI、Startups、Enterprise）
- VentureBeat（AI、Enterprise）
- WIRED AI
- MIT Technology Review
- Ars Technica（Tech、Gadgets）
- The Decoder（AI特化、高頻度）
- AI News（AI特化、高頻度）
- MarkTechPost（AI研究・実装、高頻度）
- InfoWorld（AI・開発）
- The New Stack（AI・クラウド・開発）
- Google News AI（AI企業・モデル / AIエージェントに限定した当日補完）
- Google News Cloud（AWS・主要クラウド / DevOps・クラウドネイティブに限定した当日補完）
- Google News Security / Development / Startups / Tools / App Updates / Apps / Hardware / Business Tech（各カテゴリに限定した当日補完）
- AWS Blog
- The New Stack
- InfoQ（クラウド・DevOps、高頻度）
- DevOps.com（高頻度）
- SD Times
- Kubernetes Blog
- Docker Blog
- CNCF Blog
- HashiCorp Blog
- The Hacker News
- Krebs on Security
- Dark Reading
- SANS Internet Storm Center
- Help Net Security
- BleepingComputer（高頻度）
- Security Affairs
- GitHub Blog
- Stack Overflow Blog
- Smashing Magazine
- CSS-Tricks
- Hacker News
- Product Hunt
- Lifehacker
- How-To Geek（高頻度）
- MakeUseOf（高頻度）
- Sifted
- EU-Startups
- Tech.eu
- CIO
- CIO Dive
- InformationWeek
- VentureBeat Enterprise
- ZDNet（高頻度）
- TechRepublic（高頻度）
- Engadget
- The Verge
- Gizmodo
- Tom's Hardware
- arxiv AI（cs.AI）
- arxiv ML（cs.LG）

### GitHub Releases

カテゴリごとに主要プロジェクトのGitHub Releases Atomフィードを取得します。

カテゴリごとの設定（現在）:

| カテゴリ | リポジトリ |
| --- | --- |
| AI・機械学習 | openai/openai-python、huggingface/transformers、langchain-ai/langchain |
| クラウド・AWS | aws/aws-cdk、aws/aws-cli、cloudflare/workers-sdk |
| セキュリティ | ossf/scorecard、aquasecurity/trivy、owasp-dep-scan/dep-scan |
| 開発 | vercel/next.js、nodejs/node、microsoft/TypeScript、facebook/react |
| スタートアップ | vercel/next.js、supabase/supabase、stripe/stripe-node |
| 便利ツール・Tips | Raycast Changelog、obsidianmd/obsidian-releases、microsoft/vscode |
| ガジェット・ハードウェア | raspberrypi/firmware、arduino/Arduino |
| ビジネス・DX | microsoft/PowerToys、n8n-io/n8n |

### Docs更新 / 公式Blog

公式Blog、Changelog、Release Notes系のフィードを取得します。

カテゴリごとの設定（現在）:

| カテゴリ | フィード |
| --- | --- |
| AI・機械学習 | OpenAI News / Docs、Google Developers Blog |
| クラウド・AWS | AWS What's New、Cloudflare Blog、Google Cloud Release Notes |
| セキュリティ | Cloudflare Security Blog |
| 開発 | GitHub Changelog、Vercel Changelog、Chrome Developers Blog |
| スタートアップ | Y Combinator Blog、Stripe Blog |
| 便利ツール・Tips | GitHub Changelog、Chrome Developers Blog、Google Workspace Updates |
| ガジェット・ハードウェア | Apple Developer Releases |
| ビジネス・DX | （現在未設定） |

### 公式X

公式Xは通常検索には混ぜず、`公式Xも見る` をオンにした場合のみ追加します。

公式XはX検索URLを候補として出します。アプリ側でXの投稿本文を直接スクレイピングする構成ではありません。

カテゴリごとにアカウントを設定しています（現在）:

| カテゴリ | アカウント |
| --- | --- |
| AI・機械学習 | @OpenAI、@AnthropicAI、@GoogleDeepMind |
| クラウド・AWS | @awscloud、@Azure、@googlecloud |
| セキュリティ | @msftsecintel、@CISAgov、@TheHackersNews |
| 開発 | @github、@vercel、@nodejs |
| スタートアップ | @ycombinator、@stripe、@supabase |
| 便利ツール・Tips | @ProductHunt、@raycastapp、@obsdmd |
| ガジェット・ハードウェア | @verge、@engadget |
| ビジネス・DX | @Forbes、@MicrosoftTeams |

## 信頼度スコア

| ソース種別 | 信頼度 |
| --- | ---: |
| GitHub Releases | 95 |
| Docs更新 | 95 |
| 公式Blog | 90 |
| 公式X | 85 |
| RSSニュース | 70 |

## 取得上限（type_caps）

| ソース種別 | 上限 |
| --- | ---: |
| GitHub Releases | 3 |
| Docs更新 | 3 |
| 公式Blog | 10 |
| 公式X | 2（オフ時は0） |
| RSSニュース | 上限なし（ソース分散で制御） |

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
3. `1日以内` または `3日以内` 指定で20件未満の場合、3日以内で補完
4. それでも20件未満の場合、指定モードに応じて最大7日以内で補完
5. 日時が新しい順で表示

`今日` 以外では、新しい記事を優先し、不足分だけ期間内の過去記事で補完します。

### 今日指定

期間が `今日` の場合は、公開日が当日（日本時間）の記事だけを表示します。
候補が20件未満でも、前日以前の記事で補完しません。キーワード検索時も同じ条件です。

海外（`en`）カテゴリ検索では鮮度を優先し、今日以外の自動補完は最大3日以内までに制限します。
国内（`jp`）カテゴリ検索は、今日以外の自動補完の上限が7日以内です。
`1週間以内` を明示的に選んだ場合は、国内・海外ともに7日以内の記事を候補に含めます。

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

- 第1優先: 当日記事をできるだけ多く採用
- 第2優先: 不足分を前日以降の記事で補完
- 同一URL、または正規化したタイトルが同じ記事は配信元が異なっても1件に統合
- Google News内では、異なる見出しでも固有名詞・人名などの主要語が一致する同一トピックを1件に統合
- 当日記事が十分ある場合は、ソース分散より当日記事の採用を優先
- 過去記事で補完する場合は、原則として同一ソース最大3件まで
- キーワード検索などカテゴリ外検索では、件数確保のため必要に応じて上限を緩和
- カテゴリ品質を優先するため、カテゴリによっては20件未満になる場合がある

## カテゴリ関連度フィルタ

カテゴリ検索では、汎用フィードからカテゴリ外の記事が混ざらないように、タイトル・概要に対してカテゴリ関連キーワードで絞り込みます。

対象カテゴリ:

- AI・機械学習
- クラウド・AWS
- セキュリティ
- 開発
- スタートアップ
- 便利ツール・Tips
- ガジェット・ハードウェア
- ビジネス・DX

専門性が高い公式Blog、GitHub Releases、Docs更新は基本的にそのまま採用します。
`はてブ IT`、`Publickey`、`ITmedia Enterprise`、`The New Stack`、`Lifehacker`、`Gizmodo` など広めのソースだけ、カテゴリ関連キーワードで絞ります。

また、RSS側に未来日付の記事が含まれる場合は候補から除外します。

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
- 本文＋記事URLのみの構成
- X Premiumアカウントの投稿上限（4,000文字相当）

### 投稿文の長さ

投稿本文は日本語350〜500文字程度を目安に生成します（X Premium加入により長文投稿が可能なため）。

- 3〜5文で、記事の背景・具体的な数値や固有名詞・利用者への影響・感想/考察を含める
- 文字数を埋めるための水増しはせず、具体的な情報で自然に厚みを持たせる
- ハッシュタグは自動付与しない
- URLは投稿本文の末尾に付ける
- 生成結果が短すぎる場合（重み600未満、日本語約300文字未満）は、Claude APIで本文だけを一度補強してから表示する

### 文字数オーバー時の処理

1. URL込みで4,000文字相当（`POST_CHAR_LIMIT`）を超える場合は Claude API で本文だけを自動短縮
2. 手動短縮ボタン（✂️ 自動短縮）でも再短縮可能

X文字数カウントは以下のルールです。

- 日本語・CJK文字: 2文字扱い
- 基本ラテン文字など: 1文字扱い
- URL: 23文字扱い

上限（4,000文字相当）を超えた場合は自動短縮ボタン（✂️ 自動短縮）が表示されます。

## APIエンドポイント

| メソッド | パス | 内容 |
| --- | --- | --- |
| `GET` | `/` | メイン画面 |
| `GET` | `/login` | ログイン画面 |
| `POST` | `/login` | ログイン処理 |
| `GET` | `/logout` | ログアウト |
| `GET` | `/api/status` | APIキー設定状態を返す |
| `GET` | `/api/cancel` | 実行中の記事候補取得をキャンセル |
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
| `request_id` | キャンセル対象を識別するID |

### 取得キャンセル

候補取得時、フロントエンドは `request_id` を生成して `/api/rss` に渡します。

キャンセルボタンを押すと以下を行います。

- `AbortController` でブラウザ側のfetchを中断
- `/api/cancel?request_id=...` を呼び出す
- サーバー側は該当 `request_id` のキャンセルフラグを立てる
- RSS取得のfuture待機、追加取得、再試行、補完処理の節目でキャンセルを検知して停止

サーバーはキャンセル通知を受けるため `ThreadingHTTPServer` で動作します。

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
- 翻訳: バッチサイズ5件、最大6バッチ並列
- サーバー: `ThreadingHTTPServer` により、取得中でもキャンセルAPIを受け付ける

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
- `今日` 指定では当日公開の記事だけを表示するため、候補が20件未満になることがあります。
- 海外カテゴリ検索は鮮度優先のため、自動補完は最大3日以内です。7日分を見たい場合は期間で `1週間以内` を選びます。
- APIキー未設定のローカル環境では、日本語翻訳と投稿生成は動きません。
- 公式Xは実投稿取得ではなく、公式アカウントのX検索URLを候補として出します。
- RSSフィード側の更新頻度が低いカテゴリでは、当日記事が少なくなることがあります。
- GitHub Releasesはバージョン番号だけのタイトルになりやすいため、翻訳処理で内容が分かるタイトルへ補正しています。
- カテゴリ品質を優先するため、20件に満たないカテゴリがあります。
- RSS側のカテゴリ名が正しく見えても、実際には汎用記事が混ざる場合があります。そのため、実取得結果を見ながらソース差し替えと関連度フィルタを調整します。
- キャンセルは取得処理の節目で反映されます。すでに個別フィード取得中の通信は即時停止できない場合がありますが、追加処理や待機中futureは停止します。

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
- 同一ソースに偏りすぎないよう、カテゴリ検索結果をソース分散
- クラウド・AWSカテゴリから `Hacker News` / `ZDNet Cloud` を削除し、Kubernetes / Docker / CNCF / HashiCorp系ソースを追加
- 全カテゴリに関連度フィルタを追加
- セキュリティ、スタートアップ、ビジネスDXの海外ソースを専門メディア寄りに差し替え
- 未来日付の記事を候補から除外
- このObsidianノートを毎回読み込み、作業後に更新する運用ルールを追加
- 候補取得中にキャンセルできるUI/APIを追加
- サーバーを `ThreadingHTTPServer` 化し、取得中でもキャンセルAPIを受け付けるように変更
- 海外カテゴリ検索の自動補完を最大3日以内に制限し、古い記事が出すぎないように変更（国内は最大7日）
- カテゴリ検索の選定ロジックを当日記事優先に変更。当日記事がある場合は、同一ソース上限より鮮度を優先
- 公式XアカウントをカテゴリごとのX検索URLとして整理
- ハッシュタグ自動生成を投稿文生成フローに追加（3つ、重要度順）
- 文字数オーバー時はハッシュタグ削除→本文短縮の2段階処理に変更
- GitHub Releases / Docs更新のカテゴリ別ソースを整備
- arxiv（AI/ML）、SANS Internet Storm Center、CSS-Tricks、Tom's Hardwareなどのソースを追加
- 国内ソースにケータイ Watch、クラウド Watch を追加
- 今日の記事が少ない問題対策: カテゴリごとに高頻度海外ニュースフィードを追加（The Decoder/AI News/BleepingComputer/InfoQ/SD Times/DevOps.com/How-To Geek/MakeUseOf/ZDNet/TechRepublic など）
- 幅広いソース（How-To Geek、MakeUseOf、ZDNet、TechRepublic 等）をカテゴリ関連度フィルタ対象に追加し、カテゴリ外記事の混入を防止
- 公式Blog取得上限を8件→10件に引き上げ
- 候補取得結果のinfo barに「今日○件」を表示（補完発動時のみ表示）
- `/api/rss` レスポンスに `today_count` フィールドを追加
- fetch_rss のキャッシュバグ修正（limit>=キャッシュ件数で毎回再通信していた問題を解消）
- RSSパース時の[:limit]上限を削除し、全件キャッシュするよう修正
- タイムアウトしたフィード名をサーバーログに出力（`[RSS] タイムアウト(N件): [...]`）
- タイムアウト常発フィードを削除（The Decoder, AI News, OpenAI News/Docs, Google Developers Blog, huggingface/transformers, langchain GitHub Releases, arxiv AI/ML）
- RSSフェッチ予算をRender（米国サーバー）向けに拡大（fast: 1.2s→4.0s、max: 2.6s→8.0s）
- Renderのデプロイブランチをmaster→mainに修正
- AIカテゴリに公式ブログ追加（Anthropic Blog、Google Gemini Blog、Microsoft AI Blog、NVIDIA Blog、Amazon Science、Apple ML Research、Mistral AI Blog）
- 「公式優先」チェックボックスを追加（チェック時にofficial_blog/github_release/docs_updateを上位表示）
- 「公式Xも見る」チェックボックスを削除（include_xは常にオフ）
- info barの「追加取得あり」表示を削除
- 検索中は「公式優先」チェックボックスを無効化
- 記事選択時に感想スタイルパネルを自動表示
- 記事選択後の感想スタイルを、投稿文を生成ボタンの直上へ移動
- AI海外の当日候補を増やすため、MarkTechPost / InfoWorld / The New Stack / Google News AI（AI企業・モデル、AIエージェント）を追加
- 取得不能を確認したAnthropic / Microsoft AI / Apple ML Research / Mistral AIのRSSを削除し、初回取得の無駄な待機を削減
- `今日` 指定時は、件数不足でも過去記事へ自動補完せず、当日公開の記事だけを返すように変更
- 同一URLや同じタイトルで複数配信された記事を重複表示しないように変更
- `今日` 指定で残っていた最大期間への自動補完も停止し、レスポンス直前にも当日以外を除外する二重チェックを追加
- Google Newsの同一ニュースを、見出しが異なる場合も主要語の一致で重複除外するように変更
- 異なるRSSソース間（Google News以外）でも同一記事をトークン一致率で重複除外するように拡張
- クラウド・AWSの海外・今日検索を補強するため、Google Newsのクラウド／DevOps限定フィードを追加
- 全カテゴリの海外・今日検索を補強するため、カテゴリ別のGoogle Newsフィードを追加
- Google News同士のトークン一致閾値を引き下げ（shared≥3&overlap≥0.4）、同一ニュースを複数媒体が異なる見出しで配信する重複をより積極的に除外
- 投稿文へのハッシュタグ自動生成・付与を廃止し、本文＋URLのみ出力するように変更
- ハッシュタグ削除で空いた文字枠を活かし、本文の目安を100文字以内から120〜130文字程度に拡大して内容を充実
- 本文の文字数を最終的に105〜115文字程度に調整（一時的に125〜135文字へ拡大したが多すぎたため中間値に戻した）
- iPhoneのホーム画面追加（PWA）に対応。apple-mobile-web-app系メタタグ・theme-color・manifestを追加し、アプリ名「記事投稿」・単独表示（Safari UI非表示）・ステータスバー設定を反映
- ホーム画面アイコン（180x180 PNG）をPILで動的生成し `/apple-touch-icon.png` で配信、`/manifest.webmanifest` も追加（いずれも認証前に配信しOSが取得可能）
- アイコンデザインを「執筆（ペン）」に決定。コーラル背景（#ea580c）に斜めの白いペン（ピンク消しゴム・濃紺の芯）。4倍解像度で描画→LANCZOS縮小でアンチエイリアス。theme-color/manifestのテーマ色もコーラルに統一
- 【不具合修正】Render環境にはPillowが無く（requirements.txtは標準ライブラリのみの方針）、PIL依存のアイコン生成がサイレントに404していた。ローカルでPillowを使い事前生成したPNGをBase64文字列としてコードに埋め込み、配信時はデコードのみで完結するように変更。サードパーティ依存ゼロの方針を維持したまま解決
- 【大きな変更】投稿文生成・記事タイトル翻訳をClaude API（claude-haiku-4-5）からGemini API（gemini-2.5-flash）に完全移行し、無料枠だけで運用できるようにした
  - 環境変数を `ANTHROPIC_API_KEY` → `GEMINI_API_KEY`（+ 任意で `GEMINI_MODEL`）に変更
  - Gemini呼び出しは `call_gemini()` に集約。`thinkingConfig.thinkingBudget=0` でthinkingトークンを無効化しコスト・レイテンシを抑制（meal-fitプロジェクトの実装パターンを踏襲）
  - 翻訳バッチ処理は `responseMimeType: "application/json"` でJSON強制出力に変更
  - `/api/status` の `has_key` 判定もGEMINI_API_KEY基準に変更
  - 使用するGeminiキーはpet-feeling-app・meal-fitとは別プロジェクトで新規発行し、無料枠（1,500回/日）を分離
- 【重要な発見・要注意】現在使用しているGeminiキー（新規発行分）のプロジェクトは、`gemini-2.5-flash` だけでなく **`gemini-2.5-flash-lite` も無料枠の日次上限が実測20回/日**（`GenerateRequestsPerDayPerProjectPerModel-FreeTier` quotaValue=20、モデル問わず共通）。一般に案内されている1,500回/日よりずっと少なく、通常利用でも簡単に枯渇しうる。デフォルトモデルは `gemini-2.5-flash-lite` のままにしているが、これはレイテンシ・thinking無効化の観点での選択であり、クォータ問題の根本解決ではない点に注意
  - 日次上限に達すると `HTTP Error 429: Too Many Requests` としてエラー表示される（自動リトライは無し）
  - 上限緩和にはGoogle Cloudプロジェクトの請求設定（billing）有効化が必要になる可能性が高い。無料のまま運用する場合は「1日に使える生成回数が実質20回程度」という制約を前提にする
- 記事に合う画像を生成するための英語プロンプトを作成する機能を追加
  - 投稿結果カード内に「🎨 画像生成プロンプトを作成」ボタンを追加（`imgPromptBtn`）
  - `/api/claude` は `json_mode: true` を受け取ると `call_gemini()` に `responseMimeType: application/json` を指定して呼び出す（レスポンスをそのままプロンプト文として使わず構造化データとして取得し、クライアント側で最終プロンプトを組み立てる設計。Gemini任せの自由記述だと指示の重複・不整合が出たため）
  - 実際の画像生成は行わず、プロンプト文の表示・コピーのみ（コスト・実装をシンプルに保つ判断）
  - 投稿文生成のたびに `lastArticle` / `lastArticleBody` を更新し、画像プロンプト表示もリセットする
  - 【スタイル変更】ユーザー提供の参考画像（「フィジカルAIってなに？」のような、見出し＋複数ステップのフロー＋マスコットロボット＋日本語ラベルを含む解説インフォグラフィック）に合わせ、単純な1枚イラスト＋短いキャッチコピーの形式から、本格的なインフォグラフィック構成に変更
    - Geminiへの出力形式: `{"title_ja": "文字列", "sections": [{"label_ja": "文字列", "visual_en": "文字列"}, ...]}`
    - `title_ja`: 画像上部の大見出し（15〜25文字程度、興味を引く言い回し）
    - `sections`: 記事内容を2〜4個の流れ・比較・要素に分解。各要素に短い日本語ラベル（`label_ja`）と、それを表すイラスト要素の英語説明（`visual_en`）
    - クライアント側で「左から右へ読み進める複数セクション＋矢印でつなぐ＋かわいいマスコットロボット＋日本語タイポグラフィ＋キラキラ装飾」という説明文に組み立てて最終プロンプトとする
    - 人物の実写・著名人・ロゴ再現は避けるよう明記
    - Gemini呼び出しは日次無料枠（20回/日、上記参照）を消費するため、実機での動作確認はPython側でパース・組み立てロジックのみ模擬検証済み（サンプルJSONで正しく1つの英語プロンプト文が組み上がることを確認）。実際のGemini出力での確認は無料枠回復後に推奨
- 【Claudeに復元】Geminiの無料枠が実質20回/日と少なく安定運用が難しいため、投稿文生成・翻訳をClaude API（`claude-haiku-4-5`）に戻した。将来的に別のGeminiプロジェクト/キーで再度切り替える可能性はあるが、現時点では複雑な切り替え機構は作らずシンプルにClaude運用へ戻す方針
  - `call_gemini()` を `call_claude()` に置き換え（`https://api.anthropic.com/v1/messages` を呼び出す従来の形に復元）
  - 環境変数を `GEMINI_API_KEY` → `ANTHROPIC_API_KEY` に戻す
  - 画像生成プロンプト機能（`json_mode`引数）はそのまま維持。ClaudeにはGeminiの`responseMimeType`のようなJSON強制モードが無いため、`json_mode`引数は現状未使用（プロンプト内でJSON形式を指示し、クライアント側の正規表現でコードフェンスを除去する既存方式で対応）
  - `/api/status` の `has_key` 判定もANTHROPIC_API_KEY基準に戻す
- 【レイアウト修正】iPhoneのPWA/ホーム画面表示でステータスバーと上部タイトルが重ならないよう、`viewport-fit=cover` 使用時の `safe-area-inset-top` / `safe-area-inset-bottom` を `body` と固定下部バーに反映。ヘッダーも `.app-header` / `.app-title` / `.logout-link` のCSSクラス化により、狭い画面でタイトル・バッジ・ログアウトが詰まらず自然に折り返すように変更
- 【認証修正】最終操作から30分で自動ログアウトするアイドルタイムアウトを追加。従来は固定トークンCookieを7日間保持していたが、現在はCookie値に最終操作時刻とHMAC署名を持たせ、認証済みの画面/APIアクセスごとにCookieを再発行して期限を延長する。30分以上操作がない場合は次回アクセス時にCookieを削除して `/login` へリダイレクトする。タイムアウト秒数は `SESSION_IDLE_TIMEOUT_SECONDS` で変更可能
- 【UI調整】画像生成プロンプト機能はチェック式の自動生成をいったん見送り、従来どおり投稿結果カード内の手動ボタンで生成する。生成後の「📋 プロンプトをコピー」ボタンは、長いプロンプト本文の下ではなく上に表示するように配置を変更
- 【投稿文調整】投稿文が短く感じられるため、本文目安を日本語120〜125文字程度に再調整。2〜3文で要点・影響・感想/考察を含める指示に強め、生成結果が短すぎる場合はURL込み280文字以内に収まる範囲で本文だけを一度補強する処理を追加
- 【画像プロンプト調整】X/Twitterの1枚添付向けに、生成画像の指定を16:9横長・1200x675構図へ変更。スマホタイムラインで見切れにくいよう中央セーフエリアと余白を指定する。日本語タイトル・ラベルは引き続き画像内に描画する指定を残す
- 【認証UI修正】Render無料プランでサーバーがスリープしていても、iPhone/PWAが前回DOMを復元してログイン済み画面だけ見えてしまう問題を避けるため、画面復帰時に `/api/status` でセッション確認を行うクライアント側チェックを追加。サーバー側Cookieが期限切れならログイン画面へ戻す
- 【アイコン更新】iPhoneホーム画面アイコンを「X記事生成」用途に合わせたロボット＋記事作成デザインへ差し替え。スクリーンショット外周の白背景をトリミングし、180x180 PNGとして `apple-touch-icon.png` に保存。配信時はこのPNGファイルを優先し、従来のBase64埋め込みアイコンはフォールバックとして残す
- 【重大バグ修正】ログイン直後に強制的にログイン画面へ戻されてしまう不具合を修正
  - 原因: サーバー側 `do_GET` の `/api/status` ルーティングが `self.path == "/api/status"` という厳密一致だったため、クライアントが付けるキャッシュ回避用クエリ文字列（`/api/status?_=<timestamp>`）と一致せず、フォールスルーしてメインアプリのHTML（`Content-Type: text/html`）が200で返っていた
  - 上記「画面復帰時のセッション確認」機能（`checkSessionOnResume`）は `pageshow` イベントでログイン直後の初回画面表示時にも必ず発火し、その `/api/status` フェッチが `Content-Type: application/json` でないことを検知して即座に `window.location.href='/login'` を実行していたため、認証自体は成功しているのに毎回ログイン画面へ引き戻されていた
  - 修正: `self.path == "/api/status"` を `self.path.split("?", 1)[0] == "/api/status"` に変更し、クエリ文字列の有無に関わらず正しくマッチするように修正
  - Previewブラウザで `document.cookie` はHttpOnly Cookieを操作できないため再現・検証には `/logout` エンドポイントと `form.requestSubmit()` を使い、fetchの`redirected`/`contentType`/本文を直接確認して原因を特定した
- 【大きな変更】Xアカウントが「X Premium」（旧Blue）に加入し、投稿可能文字数が大幅に増えた（Premium: 最大4,000文字）ことを受け、投稿文の文字数制限を280文字から4,000文字相当に引き上げ
  - クライアント側に `POST_CHAR_LIMIT = 4000` 定数を追加し、`updateChar()` / 上限超過判定 / 自動短縮ボタン表示条件をすべてこの定数基準に変更（従来の280直書きを排除）
  - 投稿文生成プロンプトの目標文字数を「日本語120〜125文字・2〜3文」から「日本語350〜500文字・3〜5文」に拡大。背景・具体的な数値や固有名詞・利用者への影響を交えて内容の厚みを増す指示に変更（水増し表現は禁止と明記）
  - 「短すぎる場合の自動補強」ロジックの発火しきい値を（重み230→600）に引き上げ、補強後の目標文字数も新しい350〜500文字に合わせて変更
  - サーバー側 `/api/claude` の `call_claude()` 呼び出しの `max_tokens` を800→2000に引き上げ（長文の日本語生成でトークン不足による打ち切りを防止）
  - なお「Xの認証を受けた」＝X Premium加入は、X API（プログラムからの自動投稿）とは無関係。本アプリの投稿は引き続き `https://twitter.com/intent/tweet?text=...` を開いて手動で投稿ボタンを押す方式のまま（自動投稿化は別途X Developer PortalでのAPIキー取得が必要）
- 【生成品質改善】投稿文がリンク先記事の内容を具体的・正確に反映するように強化
  - `fetch_article_body()` の取得文字数を1,500文字→3,000文字に拡大（`/api/fetch_article` エンドポイントも同様）。長めの記事でも要点が本文取得範囲に収まりやすくする
  - 投稿文生成プロンプトに「記事本文に実際に書かれている情報だけを根拠にする（タイトルからの推測・一般論で埋めない）」「固有名詞・数値・機能名・日付・引用など具体的事実を最低2〜3個は本文に盛り込む」「専門用語・略語は一般読者向けに簡潔に噛み砕いて説明する」という指示を追加
  - 「短すぎる場合の自動補強」プロンプトにも同様に「記事に無い情報を推測で足さない」「専門用語は噛み砕いて説明する」を追加し、一貫性を持たせた
- 【投稿文の構成変更】「記事内容＋実務ではこう見る」という2部構成の投稿にしたいという要望を受け対応
  - 感想スタイルのデフォルトを `impression`（一言感想）から `practical`（🔧 実務目線）に変更（`activeOpinionStyle` 初期値、UI上も「実務目線」ピルがデフォルトで選択状態になる）
  - 投稿文生成プロンプトを「前半: 記事の具体的内容を客観的に説明／後半: 『実務目線では、』のような一言を起点に視点を明確に区切って書く」という2部構成の指示に変更（従来は感想を「1文添える」程度の弱い指示だった）
  - 実務目線スタイルの指示文を「〜があれば現場で〇〇できそう」で終わらせず、なぜそう言えるかまで2〜3文で具体的に踏み込むように強化
  - ソース種別ごとの記述指示（GitHub Releases/Docs更新/RSS）から「実務への影響」の重複記述を削除し、前半＝事実説明・後半＝実務視点、と役割分担を明確化
  - 「短すぎる場合の自動補強」プロンプトにも同じ2部構成指示を追加し、フォールバック時も一貫した構成になるようにした
- 【画像プロンプト改善】画像生成プロンプトも記事内容をしっかり反映するように修正
  - 記事本文の使用範囲を400文字→2,500文字に拡大（本文取得自体は3,000文字まで行っているのに、画像プロンプト生成では先頭400文字しか渡していなかった）
  - 投稿文生成と同様に「記事に実際に書かれている内容を根拠にする（タイトルからの推測や一般論で埋めない）」「sectionsは記事中の具体的な流れ・変化・比較を反映し、テンプレ的な『今までのAI→新しいAI』のような使い回しにしない」「label_jaには記事中の固有名詞・製品名・数値を可能な範囲で使う」という指示を追加
- 【コスト目安】Claude Haiku 4.5基準で、記事1本の「投稿文＋画像プロンプト」1回生成あたり約$0.011（約1.7円）。投稿文生成（本文3,000字入力・800トークン出力目安）が約$0.0065、画像プロンプト生成（本文2,500字入力・450トークン出力目安）が約$0.0045。自動補強/自動短縮が発生した場合は+$0.003〜0.008程度。候補一覧の翻訳（検索1回あたり、記事1本ごとではない）は別途約$0.003〜0.01
- 【iOS自動ズーム修正】投稿文生成後に画面が拡大されて見える不具合を修正
  - 原因: iOS Safariは、フォーカス可能なテキスト入力要素（`input`・`textarea`・`contenteditable`）のフォントサイズが16px未満だとフォーカス時に自動的にページを拡大する仕様がある。投稿文編集エリア `.tweet-box`（`contenteditable="true"`）が `font-size: 14px` だったため、投稿文生成後にこの要素をタップ/フォーカスすると画面が拡大されていた
  - 修正: `.tweet-box` を16pxに変更。あわせてログイン画面の `input`（`font-size: .95rem` ≈ 15.2px）も同じ原因になり得るため16pxに統一
  - `<select>` 要素（期間選択など）はネイティブピッカーが開くだけでズームの対象外のため変更不要
  - 検索キーワード欄 `#keywordBox` は元々16pxで対応済みだった
