# Troubleshooting

## Docker permission denied

現在のユーザーが Docker を使えません。

```bash
docker info
```

`permission denied` や `Cannot connect to the Docker daemon` が出る場合は、Docker が起動していないか、現在のユーザーに権限がありません。

確認:

```bash
sudo docker info
```

よくある対処:

```bash
sudo systemctl start docker
sudo usermod -aG docker $USER
```

`usermod` の後はログアウトしてログインし直してください。

## Docker Compose が見つからない

次を確認します。

```bash
docker compose version
docker-compose version
```

どちらも失敗する場合は Docker Compose v2 をインストールしてください。

## .env を作り直したい

```bash
./setup.sh
```

`.env` が既にある場合、`./setup.sh` は既存の `CATCHAT_SERVER_SECRET`、`CATCHAT_INVITE_CODE`、`CATCHAT_SERVER_REGISTRATION_TOKEN` を基本的に保持します。サーバー名、Public URL、Hub URL、ポートだけを更新できます。

`CATCHAT_SERVER_SECRET` を再生成すると Hub 側の既存登録が壊れる可能性があります。`CATCHAT_INVITE_CODE` を再生成すると、既に配った `/add-server?invite=...` リンクが使えなくなる可能性があります。再生成する場合だけ、setup 中に明示確認が出ます。

## 招待リンクをもう一度表示したい

`.env` から現在の招待リンクを再表示できます。Docker は起動しません。

```bash
./setup.sh invite
```

同じ動作の正式オプション:

```bash
./setup.sh --print-invite
```

Public URL が `localhost`、`127.0.0.1`、`0.0.0.0` の場合は警告が出ます。その招待リンクは同じ PC でのテスト以外では使えません。

## CATCHAT_SERVER_SECRET must be configured

`.env` がない、または `CATCHAT_SERVER_SECRET` が placeholder のままです。

```bash
openssl rand -hex 32
cp .env.example .env
nano .env
```

初心者は手動編集より `./setup.sh` を推奨します。

## health check failed

まずローカルで確認します。

```bash
docker compose ps
docker compose logs --tail=100 catchat-server
curl http://127.0.0.1:8100/api/server/health
```

起動し直す場合:

```bash
docker compose up -d --build
```

## invite URL が localhost になる / 共通招待リンク (join_url) が表示されない

`.env` の `CATCHAT_SERVER_PUBLIC_URL` が `http://localhost:8100` のままになっているか、もしくは `CATCHAT_SERVER_REGISTRATION_TOKEN`（登録トークン）が空のままになっています。
これらが適切に設定されていないと、Hub への登録処理が自動的にスキップされ、共通招待リンク (join_url) が生成されません。
登録トークンが未入力の場合でもセットアップ自体は続行され、互換用の `/add-server?invite=...` リンクが表示されます。

設定を修正する場合:

1. `.env` を開き、必要に応じて以下を設定します。
   - `CATCHAT_SERVER_PUBLIC_URL` に外部公開用の正しいURL（例: `https://catchat.example.com`）を指定
   - `CATCHAT_SERVER_REGISTRATION_TOKEN` に Hub 側で定義された登録トークンを指定

2. 変更後、再起動および再登録を行います:

```bash
docker compose restart
./setup.sh invite
```

`localhost` は同じ PC でのテスト専用です。他人や catChat Hub から共通招待リンクを使って接続するには、Cloudflare Tunnel や Nginx などを設定し、外部から到達できる Public URL を指定する必要があります。詳細は [共通招待リンクについて](common-invite-domain.md) を確認してください。

## Cloudflare Tunnel URL が変わった

`trycloudflare.com` の URL は一時的です。URL が変わったら `.env` を更新します。

```env
CATCHAT_SERVER_PUBLIC_URL=https://new-url.trycloudflare.com
```

その後:

```bash
docker compose restart
```

## Nginx 502

Nginx から catChat Server に接続できていません。

```bash
docker compose ps
curl http://127.0.0.1:8100/api/server/health
sudo nginx -t
sudo systemctl status nginx --no-pager
```

`proxy_pass http://127.0.0.1:8100;` と `CATCHAT_PORT=8100` が一致しているか確認してください。

## Port already in use

8100 が既に使われています。

```bash
ss -ltnp | grep 8100
```

別ポートにする場合:

```env
CATCHAT_PORT=18100
CATCHAT_SERVER_PUBLIC_URL=http://localhost:18100
```

Nginx を使う場合は `proxy_pass` も同じポートに変えてください。

## permission denied on data/uploads

Docker から永続化ディレクトリに書き込めません。

```bash
sudo chown -R 1000:1000 data uploads
docker compose restart
```

## Logs

調査に必要なログ:

```bash
docker compose logs --tail=200 catchat-server
docker compose ps
docker inspect catchat-server --format '{{json .State.Health}}'
```
