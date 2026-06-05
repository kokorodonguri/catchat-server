"""event-webhook-bot — catChat Event Webhook を受け取る FastAPI ボットサンプル.

このサーバーは catChat が送信するイベントを受け取り、HMAC-SHA256 で署名を検証して処理します。

使い方:
    cp .env.example .env
    # .env を編集して CATCHAT_EVENT_SECRET を設定
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
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "9000"))

if not EVENT_SECRET:
    log.error("CATCHAT_EVENT_SECRET が .env に設定されていません。")
    sys.exit(1)

app = FastAPI(title="catChat Event Webhook Bot")


def verify_signature(secret: str, timestamp: str, body: bytes, signature: str) -> bool:
    """HMAC-SHA256 で catChat からのリクエスト署名を検証する.

    Args:
        secret: .env に設定した CATCHAT_EVENT_SECRET。
        timestamp: リクエストヘッダー X-CatChat-Timestamp の値（Unix秒）。
        body: リクエストボディの生バイト列。
        signature: リクエストヘッダー X-CatChat-Signature の値。

    Returns:
        署名が一致すれば True、不一致なら False。
    """
    message = f"{timestamp}.".encode() + body
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.post("/events")
async def receive_event(
    request: Request,
    x_catchat_event: Annotated[str | None, Header()] = None,
    x_catchat_timestamp: Annotated[str | None, Header()] = None,
    x_catchat_signature: Annotated[str | None, Header()] = None,
) -> dict:
    """catChat からのイベントを受け取るエンドポイント.

    Headers:
        X-CatChat-Event: イベントの種類（例: message.created）。
        X-CatChat-Timestamp: Unix タイムスタンプ（秒）。
        X-CatChat-Signature: HMAC-SHA256 署名（16進数文字列）。

    Returns:
        {"ok": true} — 処理成功。

    Raises:
        403: 署名の検証に失敗した場合。
    """
    body = await request.body()

    # --- 署名検証 ---
    if not x_catchat_timestamp or not x_catchat_signature:
        raise HTTPException(status_code=403, detail="Missing signature headers")

    if not verify_signature(EVENT_SECRET, x_catchat_timestamp, body, x_catchat_signature):
        log.warning("署名検証失敗 — 不正なリクエストの可能性があります")
        raise HTTPException(status_code=403, detail="Invalid signature")

    # --- イベント処理 ---
    event_type = x_catchat_event or "unknown"
    payload: dict = await request.json() if body else {}

    log.info("イベント受信: %s", event_type)

    if event_type == "message.created":
        on_message_created(payload)
    elif event_type == "message.updated":
        on_message_updated(payload)
    elif event_type == "message.deleted":
        on_message_deleted(payload)
    elif event_type == "member.joined":
        on_member_joined(payload)
    else:
        log.info("未知のイベント: %s — payload: %s", event_type, payload)

    return {"ok": True}


# ==============================================================================
# イベントハンドラ — ここをカスタマイズしてください
# ==============================================================================

def on_message_created(payload: dict) -> None:
    """message.created イベントの処理."""
    author = payload.get("author_id", "unknown")
    content = payload.get("content", "")
    channel_id = payload.get("channel_id", "?")
    log.info("[message.created] #%s %s: %s", channel_id, author, content[:80])


def on_message_updated(payload: dict) -> None:
    """message.updated イベントの処理."""
    log.info("[message.updated] id=%s", payload.get("id"))


def on_message_deleted(payload: dict) -> None:
    """message.deleted イベントの処理."""
    log.info("[message.deleted] id=%s", payload.get("id"))


def on_member_joined(payload: dict) -> None:
    """member.joined イベントの処理."""
    name = payload.get("display_name") or payload.get("username", "someone")
    log.info("[member.joined] %s がサーバーに参加しました", name)


if __name__ == "__main__":
    log.info("Event Webhook Bot を起動中... http://%s:%d/events", HOST, PORT)
    uvicorn.run(app, host=HOST, port=PORT)
