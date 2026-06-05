"""badword-filter — message.created でNGワードを検出して警告を投稿するサンプル.

使い方:
    cp .env.example .env
    # .env を編集して CATCHAT_EVENT_SECRET, CATCHAT_WEBHOOK_URL, BAD_WORDS を設定
    pip install -r requirements.txt
    python3 main.py
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
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
BAD_WORDS_RAW: str = os.getenv("BAD_WORDS", "").strip()
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "9002"))

# NGワードを小文字リストに変換し、空文字列を除外する
BAD_WORDS: list[str] = [w.strip().lower() for w in BAD_WORDS_RAW.split(",") if w.strip()]

_errors: list[str] = []
if not EVENT_SECRET:
    _errors.append("CATCHAT_EVENT_SECRET")
if not WEBHOOK_URL:
    _errors.append("CATCHAT_WEBHOOK_URL")
if not BAD_WORDS:
    _errors.append("BAD_WORDS")
if _errors:
    log.error(".env に未設定または空の必須変数があります: %s", ", ".join(_errors))
    sys.exit(1)

log.info("NGワード (%d 件): %s", len(BAD_WORDS), ", ".join(BAD_WORDS))

app = FastAPI(title="catChat Bad Word Filter")

# NGワードを単語境界で検出する正規表現を事前コンパイル
_BAD_WORD_PATTERN: re.Pattern = re.compile(
    r"(?:" + "|".join(re.escape(w) for w in BAD_WORDS) + r")",
    re.IGNORECASE,
)


def verify_signature(secret: str, timestamp: str, body: bytes, signature: str) -> bool:
    """HMAC-SHA256 で catChat からのリクエスト署名を検証する."""
    message = f"{timestamp}.".encode() + body
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def find_bad_words(text: str) -> list[str]:
    """テキスト中に含まれるNGワードを検索して返す.

    Args:
        text: 検索対象のテキスト。

    Returns:
        検出された NGワードのリスト（重複なし・小文字）。
    """
    found = set(_BAD_WORD_PATTERN.findall(text.lower()))
    return sorted(found)


def post_warning(message_id: int | None, channel_id: int | None, author_id: str, detected: list[str]) -> None:
    """NGワード検出の警告を Incoming Webhook で送信する."""
    words_str = ", ".join(f"`{w}`" for w in detected)
    content = (
        f"⚠️ NGワードを検出しました\n"
        f"チャンネル: #{channel_id}\n"
        f"投稿者: {author_id}\n"
        f"検出語: {words_str}\n"
        f"メッセージID: {message_id}"
    )
    payload = {"content": content, "username": "Bad Word Filter"}
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(WEBHOOK_URL, json=payload)
        if resp.status_code == 201:
            log.info("警告送信完了: %s", words_str)
        else:
            log.warning("警告送信失敗: %d %s", resp.status_code, resp.text)
    except httpx.HTTPError as exc:
        log.error("Webhook 送信エラー: %s", exc)


@app.post("/events")
async def receive_event(
    request: Request,
    x_catchat_event: Annotated[str | None, Header()] = None,
    x_catchat_timestamp: Annotated[str | None, Header()] = None,
    x_catchat_signature: Annotated[str | None, Header()] = None,
) -> dict:
    """catChat からのイベントを受け取り、message.created でNGワードをチェックする."""
    body = await request.body()

    if not x_catchat_timestamp or not x_catchat_signature:
        raise HTTPException(status_code=403, detail="Missing signature headers")

    if not verify_signature(EVENT_SECRET, x_catchat_timestamp, body, x_catchat_signature):
        log.warning("署名検証失敗")
        raise HTTPException(status_code=403, detail="Invalid signature")

    event_type = x_catchat_event or ""
    payload: dict = await request.json() if body else {}

    if event_type == "message.created":
        content: str = payload.get("content", "")
        author_id: str = payload.get("author_id", "unknown")
        channel_id: int | None = payload.get("channel_id")
        message_id: int | None = payload.get("id")

        detected = find_bad_words(content)
        if detected:
            log.warning(
                "NGワード検出: message_id=%s author=%s words=%s",
                message_id, author_id, detected,
            )
            post_warning(message_id, channel_id, author_id, detected)
        else:
            log.debug("[OK] message_id=%s", message_id)
    else:
        log.debug("受信イベント（無視）: %s", event_type)

    return {"ok": True}


if __name__ == "__main__":
    log.info("Bad Word Filter を起動中... http://%s:%d/events", HOST, PORT)
    uvicorn.run(app, host=HOST, port=PORT)
