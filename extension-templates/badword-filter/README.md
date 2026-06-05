# badword-filter テンプレート

`message.created` イベントを受け取り、NGワードを検出したら Incoming Webhook で警告を送るサンプルです。

## 概要

catChat のメッセージイベントを監視し、設定したNGワードが含まれていた場合に管理者向け警告メッセージを投稿します。

> [!IMPORTANT]
> このテンプレートはメッセージの**検出と通知**のみを行います。
> メッセージの自動削除は実装していません（削除API呼び出しを追加することで拡張可能です）。

## セットアップ

```bash
# 1. 依存ライブラリのインストール
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. .env を作成
cp .env.example .env
nano .env
```

`.env` の設定：

```env
# catChat のイベント Webhook Secret
CATCHAT_EVENT_SECRET=your-event-secret

# 警告を投稿する Incoming Webhook URL（管理者向けチャンネルを推奨）
CATCHAT_WEBHOOK_URL=http://localhost:8100/api/webhooks/1/your-token

# 検出するNGワード（カンマ区切り、大文字小文字を区別しない）
BAD_WORDS=spam,badword,禁止語

# このサーバーのホストとポート
HOST=0.0.0.0
PORT=9002
```

## 起動

```bash
python3 main.py
```

## catChat 側の設定

catChat のイベント送信先 URL を以下に設定します：

```
http://your-host:9002/events
```

## NGワードの設定

`BAD_WORDS` にカンマ区切りでNGワードを列挙します：

```env
# 例: 複数のNGワードを設定
BAD_WORDS=spam,広告,フィッシング,詐欺,無料配布
```

- **大文字小文字を区別しない**: `Spam`, `SPAM`, `spam` はすべて検出されます
- **部分一致**: `spam` は `spammy` という単語中にも一致します
- **Unicode対応**: 日本語のNGワードも設定できます

## 警告メッセージの例

検出時に以下のような警告メッセージが指定チャンネルに投稿されます：

```
⚠️ NGワードを検出しました
チャンネル: #1
投稿者: user123
検出語: `spam`, `test`
メッセージID: 42
```

## 注意事項

- **誤検知**: 部分一致のため、正常な単語の一部がNGワードと一致することがあります（例: `email` の中の `mail`）。NGワードリストは慎重に設定してください。
- **パフォーマンス**: NGワード数が多い場合、正規表現のコンパイルに時間がかかります。起動時に一度コンパイルされるため、通常の運用では問題ありません。
- **メッセージ削除**: 自動削除を実装したい場合は、catChat API の `DELETE /api/channels/{id}/messages/{msg_id}` を `server_secret` 付きで呼び出してください。
