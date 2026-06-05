# welcome-message テンプレート

新しいメンバーが参加したときに、Incoming Webhook 経由でウェルカムメッセージを自動送信するサンプルです。

## 概要

catChat の `member.joined` イベントを受け取り、指定した Incoming Webhook URL へ歓迎メッセージを投稿します。

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

# ウェルカムメッセージを投稿する Incoming Webhook URL
CATCHAT_WEBHOOK_URL=http://localhost:8100/api/webhooks/1/your-token

# ウェルカムメッセージのテンプレート（{display_name} がユーザー名に置換されます）
WELCOME_MESSAGE=🎉 {display_name} さん、サーバーへようこそ！

# このサーバーのホストとポート
HOST=0.0.0.0
PORT=9001
```

## 起動

```bash
python3 main.py
```

## catChat 側の設定

catChat のイベント送信先 URL を以下に設定します：

```
http://your-host:9001/events
```

## メッセージテンプレートのカスタマイズ

`WELCOME_MESSAGE` に以下のプレースホルダーを使用できます：

| プレースホルダー | 置換される値 |
|---|---|
| `{display_name}` | メンバーの表示名 |
| `{username}` | メンバーのユーザー名（@なし） |

カスタム例：

```env
WELCOME_MESSAGE=👋 {display_name}（@{username}）さん、はじめまして！何かあれば気軽に質問してください。
```

## ウェルカムメッセージを送るチャンネルの変更

`.env` の `CATCHAT_WEBHOOK_URL` が指すWebhookのチャンネルを変えることで、送信先チャンネルを変更できます。
`#general` や `#welcome` など、専用チャンネルに送るのがおすすめです。
