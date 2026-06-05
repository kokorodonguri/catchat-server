# catChat Server

## Quick Start

Docker が使える VPS / 自宅サーバーなら、次を一回コピペしてください。Public URL には Cloudflare Tunnel、Nginx + HTTPS、Tailscale、または外部から到達できる URL が必要です。

macOS / Linux / WSL:

```bash
git clone https://github.com/kokorodonguri/catchat-server.git && cd catchat-server && ./setup.sh
```

Windows PowerShell:

```powershell
git clone https://github.com/kokorodonguri/catchat-server.git; cd catchat-server; bash ./setup.sh
```

Windows では Git for Windows または WSL の `bash` と Docker Desktop が必要です。PowerShell で `bash` が見つからない場合は、WSL のターミナルで macOS / Linux / WSL 用コマンドを使ってください。

`setup.sh` がサーバー名と公開方法を聞き、`.env` を作成して Docker で起動します。

公開方法は次から選べます。

- Cloudflare Tunnel で簡単公開
- Nginx + ドメインで本番公開
- Tailscale で仲間内だけ公開
- Public URL を直接入力

最後に表示される共通招待リンク `https://.../join/{code}` を使用して catChat Hub に参加してください。共通招待リンクの生成には `CATCHAT_SERVER_REGISTRATION_TOKEN`（登録トークン）の設定が必要です（未設定の場合は、共通招待リンクの登録がスキップされ、互換用リンクのみ生成されます）。従来の `https://.../add-server?invite=...` 形式も互換性のために維持されますが、今後は共通招待リンクを推奨します。

既定の Hub URL は `https://chat.dongurihub.com` です。README、docs、`.env.example`、`server.properties.example`、`setup.sh`、server の既定値はこの URL に統一しています。

招待リンクに `CATCHAT_SERVER_SECRET` は含まれません。Hub 登録 API に送る値も、サーバー名、Public URL、invite code、registration token のみです。既存 `.env` がある状態で `./setup.sh` を再実行した場合、`CATCHAT_SERVER_SECRET`、`CATCHAT_INVITE_CODE`、`CATCHAT_SERVER_REGISTRATION_TOKEN` は基本的に保持されます。secret と invite code を再生成する場合だけ明示確認が出ます。

Public URL に `localhost`、`127.0.0.1`、`0.0.0.0` は使えません。ローカル health check の `http://127.0.0.1:8100/api/server/health` は内部確認用として使えますが、招待リンクや Hub 接続には Cloudflare Tunnel、Nginx + HTTPS、Tailscale、または外部から到達できる Public URL を指定してください。詳細は [共通招待リンクについて](docs/common-invite-domain.md) を確認してください。

## curl installer

`install.sh` は、公開配布用の別 repository `https://github.com/kokorodonguri/catchat-server.git` を clone または update してから `./setup.sh` を実行するための installer です。この monorepo から切り出した `catchat-server` 単体 repo で使う前提です。

将来的に、clone なしで次の形でも使える構成にしています。

```bash
curl -fsSL https://raw.githubusercontent.com/kokorodonguri/catchat-server/main/install.sh | bash
```

既定では `$HOME/catchat-server` に clone または update します。場所を変える場合:

```bash
CATCHAT_INSTALL_DIR=/opt/catchat-server bash install.sh
```

## What this repo is

`catchat-server` は、ユーザーが自分の VPS、自宅サーバー、PC でセルフホストする catChat のコミュニティサーバーです。

catChat の hub 鯖は公開配布しません。この repo には hub backend、hub frontend、hub DB、OAuth secret、JWT secret、管理者情報、外部サーバー secret 管理コードは含めません。公開配布するのは `catchat-server` Docker だけです。

## Commands

起動:

macOS / Linux / WSL:

```bash
docker compose up -d --build && curl http://127.0.0.1:8100/api/server/health
```

Windows PowerShell:

```powershell
docker compose up -d --build; curl.exe http://127.0.0.1:8100/api/server/health
```

初回 setup をもう一度走らせる場合:

macOS / Linux / WSL:

```bash
cd catchat-server && ./setup.sh
```

Windows PowerShell:

```powershell
cd catchat-server; bash ./setup.sh
```

ログ:

```bash
docker compose logs -f catchat-server
```

health check:

```bash
curl http://127.0.0.1:8100/api/server/health
```

現在の招待リンクだけ表示:

```bash
./setup.sh --print-invite
```

短い別名も使えます。

```bash
./setup.sh invite
```

完成済み `.env` を使って入力なしで起動:

```bash
./setup.sh --non-interactive
```

`--non-interactive` は将来の自動 installer 用入口です。現時点では `.env` の必須値が揃っている場合だけ使えます。

停止:

```bash
docker compose down
```

## Configuration

`./setup.sh` が `.env` を生成します。手動で作る場合は `.env.example` をコピーしてください。

```bash
cp .env.example .env
```

主な項目:

| key | 説明 |
| --- | --- |
| `CATCHAT_SERVER_NAME` | Hub に表示するサーバー名 |
| `CATCHAT_SERVER_PUBLIC_URL` | Hub とユーザーから到達できる URL |
| `CATCHAT_HUB_URL` | 招待リンクを作る Hub URL。既定 `https://chat.dongurihub.com` |
| `CATCHAT_SERVER_SECRET` | Hub backend とこのサーバーだけが使う secret |
| `CATCHAT_INVITE_CODE` | 招待リンクに入る invite code |
| `CATCHAT_PORT` | ホスト側の公開ポート。既定 `8100` |
| `CATCHAT_SERVER_REGISTRATION_TOKEN` | Hub への共通招待リンク登録に必要なトークン。既存 `.env` にある場合は `./setup.sh` 再実行時も保持されます。未設定時は登録をスキップし、互換用 `/add-server?invite=...` リンクのみ表示します |

## Hub proxy headers

Hub backend は、この server に proxy するとき `Authorization: Bearer CATCHAT_SERVER_SECRET` を送ります。

管理系操作では、追加で `X-Catchat-Hub-User-Id` が必要です。server は `members.role` を見て権限を判定します。

| API | 必要な権限 |
| --- | --- |
| `POST /api/channels` | `MANAGE_CHANNELS` |
| `PATCH /api/messages/{message_id}` | 投稿者本人、または `MANAGE_MESSAGES` |
| `DELETE /api/messages/{message_id}` | 投稿者本人、または `MANAGE_MESSAGES` |
| `POST /api/webhooks` | `MANAGE_WEBHOOKS` |
| `DELETE /api/webhooks/{webhook_id}` | `MANAGE_WEBHOOKS` |

`X-Catchat-Hub-User-Id` が無い管理操作は 403 になります。読み取り、通常投稿、添付追加などの既存 proxy API は互換性のため従来通り server secret を使います。

## Docker and uploads

Docker コンテナ内の uvicorn は root ではなく専用ユーザー `catchat` で起動します。`/app/data` と `/app/uploads` はこのユーザーで書き込めるように作成され、`docker-compose.yml` の `./data` / `./uploads` mount と一致しています。

アップロードは chunk 単位で保存され、`max-attachment-size-mb` を超えた時点で途中ファイルを削除して 413 を返します。ファイル名は basename に正規化し、実行ファイル拡張子と SVG は拒否します。

## Docs

- [Quick Start](docs/quickstart.md)
- [Cloudflare Tunnel](docs/cloudflare-tunnel.md)
- [Nginx + HTTPS](docs/nginx.md)
- [Troubleshooting](docs/troubleshooting.md)

## Security

- `.env` を commit しない
- `CATCHAT_SERVER_SECRET` を公開しない
- secret 実値を README、スクリーンショット、招待リンクに含めない
- 本番公開では HTTPS を使う
- `data/` と `uploads/` は必要に応じてバックアップする
