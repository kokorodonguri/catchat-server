"""minecraft-status — Minecraftサーバーの接続状態を監視し、catChatへ通知する拡張機能サンプル.

このスクリプトは、指定されたホストとポート（デフォルト: 127.0.0.1:25565）に対して
定期的に TCP ソケット接続を試み、サーバーが起動した（オンラインになった）、または
停止した（オフラインになった）瞬間に catChat の Incoming Webhook へ自動通知を行います。

使い方:
    cp .env.example .env
    # .env を編集して CATCHAT_WEBHOOK_URL や監視対象サーバー情報を設定
    pip install -r requirements.txt
    python3 main.py
"""
from __future__ import annotations

import logging
import os
import socket
import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# 環境変数の読み込み
WEBHOOK_URL: str = os.getenv("CATCHAT_WEBHOOK_URL", "").strip()
MINECRAFT_HOST: str = os.getenv("MINECRAFT_HOST", "127.0.0.1").strip()
MINECRAFT_PORT: int = int(os.getenv("MINECRAFT_PORT", "25565"))
CHECK_INTERVAL: int = int(os.getenv("CHECK_INTERVAL_SECONDS", "60"))

if not WEBHOOK_URL:
    log.error("CATCHAT_WEBHOOK_URL が .env に設定されていません。")
    sys.exit(1)

log.info("Minecraft サーバー監視を開始します。対象: %s:%d, 間隔: %d 秒", MINECRAFT_HOST, MINECRAFT_PORT, CHECK_INTERVAL)


def check_server_status(host: str, port: int, timeout: float = 3.0) -> bool:
    """socket を使用して指定ホスト・ポートに接続できるかチェックする (簡易 ping)."""
    try:
        # socket.create_connection を使用して TCP ハンドシェイクを試みる
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def post_status_to_catchat(message: str) -> None:
    """Incoming Webhook URL へステータス通知メッセージを送信する."""
    payload = {
        "content": message,
        "username": "Minecraft Monitor",
        "avatar_url": "https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/gamepad-2.svg"
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(WEBHOOK_URL, json=payload)
        if resp.status_code == 201:
            log.info("catChatへの通知送信完了: %s", message)
        else:
            log.warning("catChatへの通知送信失敗: %d %s", resp.status_code, resp.text)
    except httpx.HTTPError as exc:
        log.error("Webhook 送信中に通信エラーが発生しました: %s", exc)


def main() -> None:
    # 状態の初期値 (None: 未測定, True: オンライン, False: オフライン)
    is_online: bool | None = None

    while True:
        current_status = check_server_status(MINECRAFT_HOST, MINECRAFT_PORT)

        # 初回起動時の判定
        if is_online is None:
            is_online = current_status
            status_str = "🟢 オンライン" if is_online else "🔴 オフライン"
            log.info("初期状態検出: サーバーは現在 %s です。", status_str)
            post_status_to_catchat(
                f"🛡️ Minecraft サーバーの監視を開始しました。\n"
                f"対象: `{MINECRAFT_HOST}:{MINECRAFT_PORT}`\n"
                f"現在の状態: {status_str}"
            )
        # 2回目以降で状態が変わった場合の判定
        elif is_online != current_status:
            is_online = current_status
            if is_online:
                message = f"🟢 **Minecraft サーバーが起動しました！**\n対象: `{MINECRAFT_HOST}:{MINECRAFT_PORT}`\nログイン可能になりました。🎮"
            else:
                message = f"🔴 **Minecraft サーバーが停止しました。**\n対象: `{MINECRAFT_HOST}:{MINECRAFT_PORT}`\n現在接続できません。💔"
            
            log.info("サーバー状態が変更されました: %s", "オンライン" if is_online else "オフライン")
            post_status_to_catchat(message)
        else:
            log.debug("サーバー状態に変化はありません (%s)", "オンライン" if is_online else "オフライン")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("監視プログラムを停止します。")
        sys.exit(0)
