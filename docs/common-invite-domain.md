# 共通招待リンクについて (Common Invite Links)

catChat では、従来の複雑で長いパラメータを持つ `/add-server?invite=...` 形式から、シンプルで短い共通招待リンク `/join/{code}` 形式への移行を推奨しています。

- **推奨 (現在・将来):** `https://catchat.dongurihub.com/join/{invite_code}`
- **互換用 (レガシー):** `https://catchat.dongurihub.com/add-server?invite={base64_payload}`

---

## なぜ共通招待リンクなのか？

1. **シンプルで共有しやすい**:
   `https://catchat.dongurihub.com/join/abc123` のように短く、チャットやSNSで共有しやすい形式です。
2. **安全性の向上**:
   サーバーの秘密鍵である `CATCHAT_SERVER_SECRET` は、この共通招待リンクや API リクエスト、URL パラメータには一切含まれません。
3. **無効化や制限の管理**:
   Hub 側で招待コードの状態（有効/無効、有効期限、使用上限回数など）を管理できるため、安全に招待リンクをコントロールできます。

---

## 必要要件：登録トークン (Registration Token)

共通招待リンクの登録・生成を成功させるには、`.env` 内に有効な **`CATCHAT_SERVER_REGISTRATION_TOKEN`** の設定が必須となります。
- **登録トークンを設定している場合**: Hub サーバーへの登録が実行され、成功すると短い `join_url` が生成されて表示されます。
- **登録トークンを設定していない（未入力の）場合**: Hub サーバーへの登録処理自体がスキップされ、自動的にレガシーな「互換用招待リンク」(`/add-server?invite=...`) のみが表示されます。
- **既存 `.env` に登録トークンがある場合**: `./setup.sh` の再実行時も Enter で既存値を保持します。

Hub 登録 API や招待 URL に `CATCHAT_SERVER_SECRET` は含めません。登録 API に送る値はサーバー名、Public URL、invite code、registration token だけです。

---

## 制限事項：localhost での利用

- **localhost / 127.0.0.1 / 0.0.0.0 の Public URL では共通招待リンクは実用できません。**
- 共通招待リンクを解決して他のユーザーがサーバーに参加するには、Hub サーバー（および参加するユーザー）からあなたの `CATCHAT_SERVER_PUBLIC_URL` に直接通信できる必要があります。
- そのため、ローカルホスト環境のまま起動した場合は Hub への登録が自動的にスキップされ、自分自身の PC 内でのみテスト可能な「互換用（レガシー）招待リンク」のみが出力されます。

---

## 外部公開する方法の違いと選択

外部から到達可能な URL（Public URL）を作成するには、以下のいずれかの方法を設定します。

| 公開方法 | 特徴 | 用途 |
| --- | --- | --- |
| **Cloudflare Tunnel** | ルーターのポート開放が不要で、かつ最も安全に HTTPS 公開が可能です。`trycloudflare.com` を使えば数秒で一時的な公開用 URL が取得できます。 | 初心者・ポート開放ができない環境 |
| **Nginx + 独自ドメイン** | VPSなどで独自のドメインを設定し、Nginx などのリバースプロキシと Let's Encrypt 等の SSL 証明書を組み合わせて本番公開します。 | 本格的な本番運用・固定ドメインでの運用 |
| **Tailscale** | Tailscale の仮想専用ネットワーク（Tailnet）を構築し、VPN内の信頼できる仲間内だけでプライベートに共有します。 | 特定の知人やチーム内でのみ利用したい場合 |

---

## トラブルシューティング

### 1. 登録APIに失敗し、`join_url` が出ない場合

`./setup.sh` 完了時、または `./setup.sh invite` 実行時に「`⚠️ Hubへの共通招待リンク登録に失敗またはスキップしたため、互換用リンクのみ表示します。`」と表示される場合、以下の原因が考えられます。

- **Public URL が localhost やプライベートIPアドレスになっている**:
  - **対策**: Cloudflare Tunnel や独自ドメインを構成し、外部から到達可能な Public URL を指定して `./setup.sh` を再実行してください。
- **Hub サーバーが一時的にダウンしている、またはネットワーク疎通がない**:
  - **対策**: `CATCHAT_HUB_URL` (通常 `https://catchat.dongurihub.com`) にブラウザや curl でアクセスできるか確認してください。
- **`CATCHAT_SERVER_REGISTRATION_TOKEN`（登録トークン）の設定が間違っている**:
  - **対策**: Hub サーバーで登録トークンの検証が必須とされている場合、正しいトークンが `.env` の `CATCHAT_SERVER_REGISTRATION_TOKEN` に指定されているか確認してください。

### 2. 共通招待リンクを解決したのに参加できない場合

- 共通招待リンク自体は Hub で正常に解決できても、外部からあなたのサーバーの `CATCHAT_SERVER_PUBLIC_URL` に疎通ができない場合、接続エラー（502 や タイムアウト）になります。
- サーバー側で `CATCHAT_PORT` のポート（デフォルト `8100`）が正しく外部にフォワーディング/開放されているか、Cloudflare Tunnel や Nginx が正しく起動して稼働しているかを確認してください。
