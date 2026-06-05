# incoming-webhook テンプレート

catChat の Incoming Webhook URL にメッセージを送信する最小サンプルです。

## 概要

このテンプレートは、外部のスクリプトや CI/CD から catChat チャンネルへメッセージを投稿するための最もシンプルな実装です。

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

`.env` に以下を設定してください：

```env
# catChat 管理画面で作成した Webhook URL
CATCHAT_WEBHOOK_URL=http://localhost:8100/api/webhooks/1/your-token-here

# メッセージの先頭に付けるプレフィックス（省略可）
MESSAGE_PREFIX=
```

## Webhook URL の取得方法

1. catChat サーバーに管理者としてログイン
2. `POST /api/webhooks` を呼び出してWebhookを作成します：

```bash
curl -X POST http://localhost:8100/api/webhooks \
  -H "Authorization: Bearer <YOUR_SERVER_SECRET>" \
  -H "Content-Type: application/json" \
  -d '{"channel_id": 1, "name": "MyBot"}'
```

3. レスポンスに含まれる `url` を `.env` の `CATCHAT_WEBHOOK_URL` に設定します

> [!CAUTION]
> Webhook URL に含まれるトークンは秘密です。URLを知っている人は誰でもメッセージを投稿できます。

## 実行

```bash
python3 main.py
```

## curl での直接送信例

Python を使わずに curl で直接送信することもできます：

```bash
curl -X POST "$CATCHAT_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Hello from curl!",
    "username": "My Bot"
  }'
```

## カスタマイズ

`main.py` の `send_message()` 関数を呼び出すだけで好きなメッセージを送れます：

```python
send_message("デプロイが完了しました 🚀", username="Deployment Bot")
```

## GitHub Actions での使い方

```yaml
# .github/workflows/notify.yml
steps:
  - name: catChat に通知
    env:
      CATCHAT_WEBHOOK_URL: ${{ secrets.CATCHAT_WEBHOOK_URL }}
    run: |
      pip install httpx python-dotenv
      python3 main.py
```
