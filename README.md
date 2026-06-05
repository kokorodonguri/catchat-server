# catChat Server

## Quick Start

Docker が使える VPS / 自宅サーバー / ローカル環境なら、基本はこれだけです。

```bash
git clone https://github.com/kokorodonguri/catchat-server.git
cd catchat-server
./setup.sh
```

`setup.sh` がサーバー名と公開方法を聞き、`.env` を作成して Docker で起動します。

公開方法は次から選べます。

- ローカルだけで試す
- Cloudflare Tunnel で簡単公開
- Nginx + ドメインで本番公開
- Tailscale で仲間内だけ公開
- Public URL を直接入力

最後に表示される共通招待リンク `https://.../join/{code}` を使用して catChat Hub に参加してください。共通招待リンクの生成には `CATCHAT_SERVER_REGISTRATION_TOKEN`（登録トークン）の設定が必要です（未設定の場合は、共通招待リンクの登録がスキップされ、互換用リンクのみ生成されます）。従来の `https://.../add-server?invite=...` 形式も互換性のために維持されますが、今後は共通招待リンクを推奨します。

招待リンクに `CATCHAT_SERVER_SECRET` は含まれません。Hub 登録 API に送る値も、サーバー名、Public URL、invite code、registration token のみです。既存 `.env` がある状態で `./setup.sh` を再実行した場合、`CATCHAT_SERVER_SECRET`、`CATCHAT_INVITE_CODE`、`CATCHAT_SERVER_REGISTRATION_TOKEN` は基本的に保持されます。secret と invite code を再生成する場合だけ明示確認が出ます。

`http://localhost:8100` は同じ PC でのテスト専用です。他人や catChat Hub から共通招待リンク経由で接続するには、Cloudflare Tunnel、Nginx + HTTPS、Tailscale、または外部から到達できる Public URL が必要です（localhost の場合は共通招待リンクの生成がスキップされ、互換用リンクのみ出力されます）。詳細は [共通招待リンクについて](docs/common-invite-domain.md) を確認してください。

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

```bash
docker compose up -d --build
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
| `CATCHAT_HUB_URL` | 招待リンクを作る Hub URL |
| `CATCHAT_SERVER_SECRET` | Hub backend とこのサーバーだけが使う secret |
| `CATCHAT_INVITE_CODE` | 招待リンクに入る invite code |
| `CATCHAT_PORT` | ホスト側の公開ポート。既定 `8100` |
| `CATCHAT_SERVER_REGISTRATION_TOKEN` | Hub への共通招待リンク登録に必要なトークン。既存 `.env` にある場合は `./setup.sh` 再実行時も保持されます。未設定時は登録をスキップし、互換用 `/add-server?invite=...` リンクのみ表示します |


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
