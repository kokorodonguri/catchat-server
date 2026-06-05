# catChat 拡張機能テンプレート集

catChat サーバーを拡張するための公式テンプレートです。
すべてのテンプレートは **Webhook型** で実装されており、catchat-server 本体を改変せずに安全に機能を追加できます。

---

## 🏗️ アーキテクチャ概要

```
catChat Server (catchat-server)
    │
    ├── Incoming Webhook: 外部→catChatへメッセージを送る
    │       └── 外部ツール/スクリプト → POST /api/webhooks/{id}/{token} → チャンネルへ投稿
    │
    └── Event Webhook: catChat→外部へイベントを送る (将来機能)
            └── catChat → POST http://your-bot:9000/events → 自作ボット処理
```

> [!IMPORTANT]
> すべての拡張機能は **catchat-server とは別プロセス・別コンテナで動かしてください**。
> catchat-server 本体の内部でサードパーティコードを直接実行するプラグイン方式は、セキュリティ上の理由から現在推奨していません。

---

## 📦 テンプレート一覧

| テンプレート | 難易度 | 概要 | 依存 |
|---|---|---|---|
| [incoming-webhook](./incoming-webhook/) | ⭐ かんたん | catChatにメッセージを送る最小サンプル | `httpx` |
| [event-webhook-bot](./event-webhook-bot/) | ⭐⭐ 中級 | catChatのイベントを受け取るFastAPI bot | `fastapi`, `uvicorn`, `httpx` |
| [welcome-message](./welcome-message/) | ⭐⭐ 中級 | 参加者に自動ウェルカムメッセージを送る | `fastapi`, `uvicorn`, `httpx` |
| [minecraft-status](./minecraft-status/) | ⭐ かんたん | Minecraftサーバーの状態を定期通知する | `httpx` |
| [badword-filter](./badword-filter/) | ⭐⭐ 中級 | NGワードを検出して警告を投稿する | `fastapi`, `uvicorn`, `httpx` |

---

## 🚀 初めての方へ：どれから始めるか

**まず [incoming-webhook](./incoming-webhook/) から試してください。**

catChat の Incoming Webhook URL に HTTP POST するだけなので、依存ライブラリが最小限で動きます。
Bashスクリプトや curl でも代用できますが、Python版のサンプルとして参考にしてください。

```
推奨学習順序:
1. incoming-webhook    ← まずここから
2. event-webhook-bot   ← イベント受信を理解する
3. welcome-message     ← 受信＋送信を組み合わせる
4. minecraft-status    ← 定期監視パターンを学ぶ
5. badword-filter      ← フィルタリングパターンを学ぶ
```

---

## 🔑 Incoming Webhook と Event Webhook の違い

### Incoming Webhook（外部 → catChat）
- **方向**: 外部サービス/スクリプト **から** catChat **へ** メッセージを送る
- **使い方**: catChat 管理画面でWebhook URLを発行 → そのURLにPOSTするだけ
- **認証**: URL に含まれるトークンで認証（ヘッダー不要）
- **例**: CI/CDのデプロイ通知、Minecraft死亡通知、定期レポート

### Event Webhook（catChat → 外部）
- **方向**: catChat **から** 自作ボット **へ** イベントを送る
- **使い方**: 自作ボットサーバーを立てて、catChat のイベント送信先URLに登録する
- **認証**: HMAC-SHA256 署名で検証（`X-CatChat-Signature` ヘッダー）
- **例**: ウェルカムメッセージBot、NGワードフィルター、翻訳Bot

---

## ⚙️ 共通セットアップ手順

各テンプレートディレクトリで以下の手順を実行します。

```bash
# 1. テンプレートをコピー
cp -r incoming-webhook/ my-extension/
cd my-extension/

# 2. .env を作成して設定
cp .env.example .env
nano .env  # または好みのエディタで編集

# 3. 依存ライブラリをインストール
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. 実行
python3 main.py
```

---

## 🔒 セキュリティガイドライン

- **`.env` はコミットしない** — `.gitignore` に必ず追加してください
- **Webhook URL は秘密** — URLを知っている人は誰でも投稿できます
- **HTTPS を使う** — 本番環境では必ずHTTPSで通信してください
- **別プロセスで動かす** — catchat-server の venv や プロセスとは分離してください
- **最小権限の原則** — 必要なチャンネルのWebhookだけ発行してください

---

## 📝 自作テンプレートの投稿

テンプレートを自作して公開したい場合は、以下の構成を参考にしてください：

```
my-extension/
├── README.md          # 必須: 使い方の説明
├── .env.example       # 必須: 設定項目のサンプル（実値を書かない）
├── requirements.txt   # 必須: 依存パッケージ一覧
└── main.py            # 必須: エントリーポイント
```
