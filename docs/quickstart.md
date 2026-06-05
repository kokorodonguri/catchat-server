# Quick Start

catChat Server は Docker で起動します。hub 鯖は配布しません。

## 1. Install Docker

Docker Desktop または Docker Engine をインストールし、次が成功する状態にしてください。

```bash
docker --version
docker compose version
docker info
```

`docker info` が permission denied になる場合は [Troubleshooting](troubleshooting.md) を見てください。

## 2. Clone and setup

```bash
git clone https://github.com/kokorodonguri/catchat-server.git
cd catchat-server
./setup.sh
```

`setup.sh` は次を行います。

- Docker / Docker Compose の確認
- `.env` がある場合の上書き確認
- サーバー名の入力
- 公開方法の選択
- `CATCHAT_SERVER_SECRET` の自動生成
- `CATCHAT_INVITE_CODE` の自動生成
- `docker compose up -d --build`
- `http://127.0.0.1:8100/api/server/health` の確認

## 3. Choose public access

初心者は Cloudflare Tunnel が一番簡単です。本番でドメインを持っている場合は Nginx + HTTPS を使ってください。

| 方法 | 向いている用途 |
| --- | --- |
| ローカル | 同じ PC での動作確認 |
| Cloudflare Tunnel | ポート開放なしで試す、簡単に HTTPS 公開する |
| Nginx + ドメイン | VPS で本番運用する |
| Tailscale | 仲間内、tailnet 内だけで使う |
| 直接入力 | 既に Public URL がある |

`localhost` は同じ PC からしか届きません。他人や catChat Hub から接続するには外部 URL が必要です。

## 4. Add to catChat Hub

setup の最後に表示される招待リンクを Hub に追加、またはブラウザで開きます。

**推奨 (共通招待リンク):**
```text
https://chat.dongurihub.com/join/abc123
```

**互換用 (レガシー招待リンク):**
```text
https://chat.dongurihub.com/add-server?invite=...
```

これらの招待リンクには `CATCHAT_SERVER_SECRET` は含まれません。
※ localhost などのローカル環境では共通招待リンクは機能しないため、互換用リンクのみが生成されます。詳細は [共通招待リンクについて](common-invite-domain.md) を確認してください。

## 5. Daily commands

```bash
docker compose ps
docker compose logs -f catchat-server
curl http://127.0.0.1:8100/api/server/health
docker compose restart
docker compose down
```

## 6. Security defaults

- 既定の Hub URL は `https://chat.dongurihub.com` です。
- Docker コンテナは root ではなく `catchat` ユーザーで uvicorn を実行します。
- Hub proxy は `Authorization: Bearer CATCHAT_SERVER_SECRET` を送ります。チャンネル作成、メッセージ編集/削除、webhook 管理では追加で `X-Catchat-Hub-User-Id` が必要です。
- 添付ファイルは chunk 保存され、上限超過時は途中ファイルを削除します。実行ファイル拡張子と SVG は拒否されます。
