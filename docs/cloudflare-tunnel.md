# Cloudflare Tunnel

Cloudflare Tunnel を使うと、VPS や自宅サーバーで 8100 番ポートを直接開けずに HTTPS URL を作れます。

## Quick tunnel

一時的に試すだけなら、別ターミナルで次を実行します。

```bash
cloudflared tunnel --url http://localhost:8100
```

表示された URL を `./setup.sh` に入力します。

```text
https://xxxxx.trycloudflare.com
```

`trycloudflare.com` の URL は一時的です。cloudflared を止めると使えなくなることがあります。

## Fixed domain

本番に近い形で使う場合は Cloudflare Zero Trust で Tunnel を作り、Public Hostname を設定します。

```text
Hostname: catchat.example.com
Service: http://localhost:8100
```

その場合の `.env`:

```env
CATCHAT_SERVER_PUBLIC_URL=https://catchat.example.com
CATCHAT_PORT=8100
```

変更後:

```bash
docker compose restart
```

## Check

```bash
curl http://127.0.0.1:8100/api/server/health
curl https://catchat.example.com/api/server/health
docker compose logs --tail=100 catchat-server
```

## Notes

- `CATCHAT_SERVER_PUBLIC_URL` が `localhost` のままだと Hub から接続できません。
- Cloudflare Access などで認証をかけると Hub backend が接続できない場合があります。
- 添付ファイルのサイズは Cloudflare 側の制限にも影響されます。
