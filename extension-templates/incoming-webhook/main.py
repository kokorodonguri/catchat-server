"""incoming-webhook — catChat Incoming Webhook への最小送信サンプル.

使い方:
    cp .env.example .env
    # .env を編集して CATCHAT_WEBHOOK_URL を設定
    pip install -r requirements.txt
    python3 main.py
"""
from __future__ import annotations

import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

WEBHOOK_URL: str = os.getenv("CATCHAT_WEBHOOK_URL", "").strip()
MESSAGE_PREFIX: str = os.getenv("MESSAGE_PREFIX", "").strip()


def send_message(
    content: str,
    *,
    username: str | None = None,
    avatar_url: str | None = None,
) -> None:
    """catChat の Incoming Webhook URL にメッセージを POST する.

    Args:
        content: 送信するメッセージ本文（必須）。
        username: チャンネルに表示されるボット名（省略時はWebhook名が使われる）。
        avatar_url: ボットのアバター画像URL（省略可）。

    Raises:
        SystemExit: Webhook URL が未設定の場合。
        httpx.HTTPStatusError: サーバーがエラーを返した場合。
    """
    if not WEBHOOK_URL:
        print("ERROR: CATCHAT_WEBHOOK_URL が .env に設定されていません。", file=sys.stderr)
        sys.exit(1)

    full_content = f"{MESSAGE_PREFIX}{content}" if MESSAGE_PREFIX else content

    payload: dict = {"content": full_content}
    if username:
        payload["username"] = username
    if avatar_url:
        payload["avatar_url"] = avatar_url

    with httpx.Client(timeout=10.0) as client:
        response = client.post(WEBHOOK_URL, json=payload)

    if response.status_code == 201:
        print(f"✅ 送信成功: {full_content!r}")
    elif response.status_code == 403:
        print("❌ 送信失敗: Incoming Webhook が無効になっています。", file=sys.stderr)
        sys.exit(1)
    elif response.status_code == 429:
        print("❌ 送信失敗: レートリミット超過です。しばらく待ってから再試行してください。", file=sys.stderr)
        sys.exit(1)
    else:
        response.raise_for_status()


def main() -> None:
    """動作確認用のテストメッセージを送信する."""
    send_message(
        "👋 incoming-webhook テンプレートからのテストメッセージです！",
        username="Test Bot",
    )


if __name__ == "__main__":
    main()
