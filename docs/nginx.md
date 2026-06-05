# Nginx + HTTPS

VPS で本番公開する場合は、8100 を直接インターネットに出すより Nginx で HTTPS 終端する構成を推奨します。

## DNS

ドメインの A レコードを VPS の public IP に向けます。

```text
chat.my-domain.com -> your VPS public IP
```

## .env

```env
CATCHAT_SERVER_PUBLIC_URL=https://chat.my-domain.com
CATCHAT_PORT=8100
```

変更後:

```bash
docker compose restart
```

## Nginx config

`/etc/nginx/sites-available/catchat-server`:

```nginx
server {
    listen 80;
    server_name chat.my-domain.com;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8100;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

有効化:

```bash
sudo ln -s /etc/nginx/sites-available/catchat-server /etc/nginx/sites-enabled/catchat-server
sudo nginx -t
sudo systemctl reload nginx
```

## Certbot

Ubuntu / Debian の例:

```bash
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx
sudo certbot --nginx -d chat.my-domain.com
```

## Firewall

通常は 80 と 443 を開けます。8100 は外部公開しなくてかまいません。

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

## Check

```bash
curl http://127.0.0.1:8100/api/server/health
curl https://chat.my-domain.com/api/server/health
docker compose ps
docker compose logs --tail=100 catchat-server
```

Nginx が 502 を返す場合は、Docker 側の health check が通るか先に確認してください。
