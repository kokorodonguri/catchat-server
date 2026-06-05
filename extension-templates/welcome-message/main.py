"""welcome-message — member.joined イベントでウェルカムメッセージを自動送信するサンプル.

使い方:
    cp .env.example .env
    # .env を編集して CATCHAT_EVENT_SECRET と CATCHAT_WEBHOOK_URL を設定
    pip install -r requirements.txt
    python3 main.py
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import sys
from typing import Annotated

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

EVENT_SECRET: str = os.getenv("CATCHAT_EVENT_SECRET", "").strip()
WEBHOOK_URL: str = os.getenv("CATCHAT_WEBHOOK_URL", "").strip()
WELCOME_MESSAGE: str = os.getenv("WELCOME_MESSAGE", "🎉 {display_name} さん、サーバーへようこそ！")
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "9001"))

_errors: list[str] = []
if not EVENT_SECRET:
    _errors.append("CATCHAT_EVENT_SECRET")
if not WEBHOOK_URL:
    _errors.append("CATCHAT_WEBHOOK_URL")
if _errors:
    log.error(".env に未設定の必須変数があります: %s", ", ".join(_errors))
    sys.exit(1)

app = FastAPI(title="catChat Welcome Message Bot")


def verify_signature(secret: str, timestamp: str, body: bytes, signature: str) -> bool:
    """HMAC-SHA256 で catChat からのリクエスト署名を検証する."""
    message = f"{timestamp}.".encode() + body
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def post_welcome(display_name: str, username: str) -> None:
    """Incoming Webhook URL へウェルカムメッセージを送信する."""
    content = WELCOME_MESSAGE.format(display_name=display_name, username=username)
    payload = {"content": content, "username": "Welcome Bot"}
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(WEBHOOK_URL, json=payload)
        if resp.status_code == 201:
            log.info("ウェルカムメッセージ送信完了: %s", display_name)
        else:
            log.warning("ウェルカムメッセージ送信失敗: %d %s", resp.status_code, resp.text)
    except httpx.HTTPError as exc:
        log.error("Webhook 送信エラー: %s", exc)


@app.post("/events")
async def receive_event(
    request: Request,
    x_catchat_event: Annotated[str | None, Header()] = None,
    x_catchat_timestamp: Annotated[str | None, Header()] = None,
    x_catchat_signature: Annotated[str | None, Header()] = None,
) -> dict:
    """catChat からのイベントを受け取り、member.joined のときにウェルカムメッセージを送る."""
    body = await request.body()

    if not x_catchat_timestamp or not x_catchat_signature:
        raise HTTPException(status_code=403, detail="Missing signature headers")

    if not verify_signature(EVENT_SECRET, x_catchat_timestamp, body, x_catchat_signature):
        log.warning("署名検証失敗")
        raise HTTPException(status_code=403, detail="Invalid signature")

    event_type = x_catchat_event or ""
    payload: dict = await request.json() if body else {}

    if event_type == "member.joined":
        display_name: str = payload.get("display_name") or payload.get("username", "新しいメンバー")
        username: str = payload.get("username", display_name)
        log.info("%s がサーバーに参加しました", display_name)
        post_welcome(display_name, username)
    else:
        log.debug("受信イベント（無視）: %s", event_type)

    return {"ok": True}


if __name__ == "__main__":
    log.info("Welcome Message Bot を起動中... http://%s:%d/events", HOST, PORT)
    uvicorn.run(app, host=HOST, port=PORT)
