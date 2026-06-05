# minecraft-status テンプレート

Minecraft サーバーの稼働状態を定期確認し、状態が変わったときに catChat に通知するサンプルです。

## 概要

指定した Minecraft サーバーのホスト:ポートに TCP 接続を試みて、オンライン/オフラインを判定します。
状態が変わったとき（オンライン→オフライン、またはその逆）だけ Incoming Webhook で通知します。

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
# 通知先 Incoming Webhook URL
CATCHAT_WEBHOOK_URL=http://localhost:8100/api/webhooks/1/your-token

# 監視する Minecraft サーバーのアドレス
MINECRAFT_HOST=127.0.0.1
MINECRAFT_PORT=25565

# 確認間隔（秒）
CHECK_INTERVAL_SECONDS=60
```

## 起動

```bash
python3 main.py
```

サーバーが起動すると、即時に最初の状態確認を行い、その後は設定した間隔で定期チェックします。

## 動作の仕組み

1. `MINECRAFT_HOST:MINECRAFT_PORT` に TCP 接続を試みます（タイムアウト: 5秒）
2. 接続できれば **オンライン**、できなければ **オフライン** と判定します
3. 前回の状態から変化があった場合のみ catChat に通知します
4. `CHECK_INTERVAL_SECONDS` 秒待って、1. に戻ります

> [!NOTE]
> より詳細なステータス（プレイヤー数など）を取得するには、`mcstatus` ライブラリの利用を検討してください。
> このテンプレートは依存を最小限にするため、TCP 接続チェックのみ実装しています。

## よくある使い方

- **個人の Minecraft サーバー**: 自分がプレイするサーバーが落ちたら catChat で通知
- **複数サーバーの監視**: このスクリプトを複数インスタンス起動して並列監視

## 注意事項

- `CHECK_INTERVAL_SECONDS` を短くしすぎると Minecraft サーバーに負荷をかける可能性があります。最短でも30秒以上を推奨します。
- Minecraft サーバーと catChat が同じマシンにある場合、catChat 自体が停止すると通知が届かないことがあります。
