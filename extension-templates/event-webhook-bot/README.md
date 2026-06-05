# event-webhook-bot テンプレート

catChat からイベントを受け取る FastAPI ボットサーバーのサンプルです。

## 概要

catChat が送信するイベント Webhook を受け取り、HMAC-SHA256 で署名を検証したうえでイベントを処理します。
`message.created` を受け取ったらログに表示します。

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
# catChat のイベント Webhook Secret（catChat側の設定画面で確認できる値と同じにする）
CATCHAT_EVENT_SECRET=your-secret-here

# このサーバーを起動するホストとポート
HOST=0.0.0.0
PORT=9000
```

## 起動

```bash
python3 main.py
```

サーバーが `http://0.0.0.0:9000` で起動します。

## catChat 側の設定

catChat サーバー側で、イベント送信先 URL を以下のように設定してください：

```
http://your-host:9000/events
```

> [!NOTE]
> catChat と同じマシンで動かす場合は `http://localhost:9000/events` です。
> 別マシンの場合は適切なIPアドレスまたはドメイン名に変えてください。

## イベントの種類

| イベント名 | 説明 |
|---|---|
| `message.created` | メッセージが投稿された |
| `message.updated` | メッセージが編集された |
| `message.deleted` | メッセージが削除された |
| `member.joined` | メンバーが参加した |

## 署名検証について

リクエストヘッダーに含まれる `X-CatChat-Signature` を HMAC-SHA256 で検証することで、
リクエストが本当に catChat から送られたものかを確認します。

署名の計算方法：
```
HMAC-SHA256(secret, f"{timestamp}.{body_bytes}")
```

検証に失敗したリクエストは `403 Forbidden` を返して無視します。
