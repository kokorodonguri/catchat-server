import asyncio
import base64
import fnmatch
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def load_server_properties() -> dict[str, str]:
    path = BASE_DIR / "server.properties"
    if not path.exists():
        return {}
    settings: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        settings[key.strip()] = value.strip()
    return settings


PROPERTIES = load_server_properties()


def _as_list(value: str | list[str]) -> list[str]:
    return [value] if isinstance(value, str) else value


def _first_env(names: list[str]) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value is not None:
            return value
    return None


def configured_value(
    suffixes: str | list[str],
    property_name: str,
    default: str,
    *,
    server_env_names: list[str] | None = None,
    guild_suffixes: str | list[str] | None = None,
) -> str:
    server_suffixes = _as_list(suffixes)
    legacy_guild_suffixes = _as_list(guild_suffixes) if guild_suffixes is not None else server_suffixes

    server_names = [*(server_env_names or []), *(f"CATCHAT_SERVER_{suffix}" for suffix in server_suffixes)]
    server_value = _first_env(server_names)
    if server_value is not None:
        return server_value

    guild_value = _first_env([f"CATCHAT_GUILD_{suffix}" for suffix in legacy_guild_suffixes])
    if guild_value is not None:
        return guild_value

    return PROPERTIES.get(property_name, default)


def configured_path(suffixes: str | list[str], property_name: str, default: str) -> Path:
    path = Path(configured_value(suffixes, property_name, default))
    return path if path.is_absolute() else BASE_DIR / path


def positive_int_setting(suffixes: str | list[str], property_name: str, default: int) -> int:
    raw_value = configured_value(suffixes, property_name, str(default))
    try:
        value = int(raw_value)
    except ValueError as error:
        raise RuntimeError(f"{property_name} must be a positive integer") from error
    if value <= 0:
        raise RuntimeError(f"{property_name} must be a positive integer")
    return value


def boolean_setting(suffixes: str | list[str], property_name: str, default: bool) -> bool:
    raw_value = configured_value(suffixes, property_name, str(default).lower()).lower()
    if raw_value not in {"true", "false"}:
        raise RuntimeError(f"{property_name} must be true or false")
    return raw_value == "true"


def int_setting(suffixes: str | list[str], property_name: str, default: int) -> int:
    raw_value = configured_value(suffixes, property_name, str(default))
    try:
        return int(raw_value)
    except ValueError as error:
        raise RuntimeError(f"{property_name} must be an integer") from error


DATABASE_PATH = configured_path("DATABASE_PATH", "database-path", "server.db")
UPLOAD_DIR = configured_path("UPLOAD_DIR", "upload-dir", "uploads")
SERVER_SECRET = configured_value("SECRET", "server-secret", "", guild_suffixes=["SECRET"])
REGISTRATION_TOKEN = configured_value("REGISTRATION_TOKEN", "registration-token", "")
PUBLIC_URL = configured_value(
    "PUBLIC_URL",
    "public-url",
    "http://localhost:8100",
    server_env_names=["CATCHAT_SERVER_PUBLIC_URL", "CATCHAT_PUBLIC_URL", "CATCHAT_SERVER_BASE_URL"],
    guild_suffixes=["PUBLIC_URL", "BASE_URL"],
).rstrip("/")
SERVER_NAME = configured_value("NAME", "server-name", "My Server").strip() or "My Server"
SERVER_DESCRIPTION = configured_value("DESCRIPTION", "server-description", "").strip()
HUB_URL = configured_value(
    "HUB_URL",
    "hub-url",
    "https://chat.dongurihub.com",
    server_env_names=["CATCHAT_HUB_URL"],
).rstrip("/")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in configured_value(
        "ALLOWED_ORIGINS",
        "allowed-origins",
        "https://chat.dongurihub.com,http://localhost:5173",
    ).split(",")
    if origin.strip()
]

max_attachment_size_bytes = configured_value("MAX_ATTACHMENT_SIZE", "max-attachment-size-bytes", "")
if max_attachment_size_bytes:
    try:
        MAX_ATTACHMENT_SIZE = int(max_attachment_size_bytes)
    except ValueError as error:
        raise RuntimeError("max-attachment-size-bytes must be a positive integer") from error
    if MAX_ATTACHMENT_SIZE <= 0:
        raise RuntimeError("max-attachment-size-bytes must be a positive integer")
else:
    MAX_ATTACHMENT_SIZE = positive_int_setting("MAX_ATTACHMENT_SIZE_MB", "max-attachment-size-mb", 10) * 1024 * 1024

MAX_ATTACHMENTS_PER_MESSAGE = positive_int_setting("MAX_ATTACHMENTS_PER_MESSAGE", "max-attachments-per-message", 5)
MAX_MESSAGE_LENGTH = positive_int_setting("MAX_MESSAGE_LENGTH", "max-message-length", 4000)
MAX_MESSAGE_HISTORY = positive_int_setting("MAX_MESSAGE_HISTORY", "max-message-history", 100)
UPLOAD_CHUNK_SIZE = 1024 * 1024
EMPTY_MESSAGE_CLEANUP_SECONDS = 60 * 60
ALLOWED_FILE_TYPES = [
    value.strip().lower()
    for value in configured_value(
        "ALLOWED_FILE_TYPES",
        "allowed-file-types",
        "image/*,video/*,audio/*,application/pdf,text/plain,application/zip",
    ).split(",")
    if value.strip()
]
ALLOW_EXECUTABLE_FILES = boolean_setting("ALLOW_EXECUTABLE_FILES", "allow-executable-files", False)
DEFAULT_CHANNEL_NAME = configured_value("DEFAULT_CHANNEL_NAME", "default-channel-name", "general").strip().lower()

# Enforce all properties from server.properties
ALLOW_MESSAGE_EDIT = boolean_setting("ALLOW_MESSAGE_EDIT", "allow-message-edit", True)
ALLOW_MESSAGE_DELETE = boolean_setting("ALLOW_MESSAGE_DELETE", "allow-message-delete", True)
ALLOW_REPLIES = boolean_setting("ALLOW_REPLIES", "allow-replies", True)
ALLOW_REACTIONS = boolean_setting("ALLOW_REACTIONS", "allow-reactions", True)
ALLOW_CHANNEL_CREATE = boolean_setting("ALLOW_CHANNEL_CREATE", "allow-channel-create", True)
MAX_CHANNELS = positive_int_setting("MAX_CHANNELS", "max-channels", 100)
MAX_MEMBERS = int_setting("MAX_MEMBERS", "max-members", 0)
DEFAULT_INVITE_ENABLED = boolean_setting("DEFAULT_INVITE_ENABLED", "default-invite-enabled", True)
DEFAULT_INVITE_MAX_USES = int_setting("DEFAULT_INVITE_MAX_USES", "default-invite-max-uses", 0)
DEFAULT_INVITE_EXPIRES_HOURS = int_setting("DEFAULT_INVITE_EXPIRES_HOURS", "default-invite-expires-hours", 0)
STARTUP_INVITE_CODE = configured_value(
    "INVITE_CODE",
    "startup-invite-code",
    "",
    server_env_names=["CATCHAT_INVITE_CODE", "CATCHAT_SERVER_INVITE_CODE"],
).strip()
ALLOW_USERS_CREATE_INVITES = boolean_setting("ALLOW_USERS_CREATE_INVITES", "allow-users-create-invites", False)
ENABLE_BANS = boolean_setting("ENABLE_BANS", "enable-bans", True)
ENABLE_KICKS = boolean_setting("ENABLE_KICKS", "enable-kicks", True)
ENABLE_REPORTS = boolean_setting("ENABLE_REPORTS", "enable-reports", True)
ENABLE_AUDIT_LOG = boolean_setting("ENABLE_AUDIT_LOG", "enable-audit-log", True)
REQUIRE_HUB_PROXY = boolean_setting("REQUIRE_HUB_PROXY", "require-hub-proxy", True)
ALLOW_DIRECT_BROWSER_ACCESS = boolean_setting("ALLOW_DIRECT_BROWSER_ACCESS", "allow-direct-browser-access", False)

ENABLE_INCOMING_WEBHOOKS = boolean_setting("ENABLE_INCOMING_WEBHOOKS", "enable-incoming-webhooks", True)
MAX_WEBHOOKS = positive_int_setting("MAX_WEBHOOKS", "max-webhooks", 20)
WEBHOOK_RATE_LIMIT_PER_MINUTE = positive_int_setting("WEBHOOK_RATE_LIMIT_PER_MINUTE", "webhook-rate-limit-per-minute", 30)

if not DEFAULT_CHANNEL_NAME or not re.fullmatch(r"[a-z0-9_-]+", DEFAULT_CHANNEL_NAME):
    raise RuntimeError("default-channel-name may contain letters, numbers, underscores, and hyphens")
def is_placeholder_secret(value: str) -> bool:
    normalized = value.strip().lower()
    return (
        not normalized
        or normalized.startswith("replace-with-")
        or "your-generated-secret" in normalized
        or "change-this-secret" in normalized
    )


def is_placeholder_public_url(value: str) -> bool:
    hostname = (urlparse(value).hostname or "").lower()
    return (
        not hostname
        or hostname == "example.com"
        or hostname.endswith(".example.com")
        or hostname.startswith("your-")
        or hostname.startswith("your.")
        or "placeholder" in hostname
    )


if is_placeholder_secret(SERVER_SECRET):
    raise RuntimeError("CATCHAT_SERVER_SECRET must be configured in catchat-server/.env (legacy CATCHAT_GUILD_SECRET is also supported)")
if REGISTRATION_TOKEN and is_placeholder_secret(REGISTRATION_TOKEN):
    raise RuntimeError("CATCHAT_SERVER_REGISTRATION_TOKEN must be a generated secret when enabled")
parsed_public_url = urlparse(PUBLIC_URL)
if (
    parsed_public_url.scheme not in {"http", "https"}
    or not parsed_public_url.netloc
    or parsed_public_url.username
    or parsed_public_url.password
    or parsed_public_url.query
    or parsed_public_url.fragment
):
    raise RuntimeError("CATCHAT_PUBLIC_URL must be a public HTTP(S) URL without credentials, query, or fragment")
if parsed_public_url.hostname in {"localhost", "127.0.0.1", "0.0.0.0"}:
    raise RuntimeError("CATCHAT_PUBLIC_URL must not be localhost, 127.0.0.1, or 0.0.0.0")
if is_placeholder_public_url(PUBLIC_URL):
    raise RuntimeError("CATCHAT_PUBLIC_URL must not be an example.com or placeholder URL")


class ServerSettingsResponse(BaseModel):
    max_channels: int
    channel_count: int
    allow_channel_create: bool


class ServerSettingsPatch(BaseModel):
    max_channels: int = Field(..., ge=0, le=1000)


class GuildLimits(BaseModel):
    max_attachment_size: int
    max_attachment_size_mb: int
    max_attachments_per_message: int
    max_message_length: int
    max_message_history: int
    max_channels: int
    max_members: int
    allowed_file_types: list[str]
    allow_executable_files: bool


class GuildFeatures(BaseModel):
    message_edit: bool
    message_delete: bool
    replies: bool
    reactions: bool
    channel_create: bool
    default_invite_enabled: bool
    allow_users_create_invites: bool
    bans: bool
    kicks: bool
    reports: bool
    audit_log: bool
    require_hub_proxy: bool
    allow_direct_browser_access: bool


class GuildInfo(BaseModel):
    id: str
    name: str
    description: str
    version: str
    channel_count: int
    member_count: int
    max_attachment_size: int
    max_message_length: int
    limits: GuildLimits
    features: GuildFeatures


class GuildHealth(BaseModel):
    status: str
    storage: str
    websocket: str
    timestamp: int


class ChannelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    topic: str = Field(default="", max_length=280)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        name = value.strip().lower().removeprefix("#").replace(" ", "-")
        if not name or not re.fullmatch(r"[a-z0-9_-]+", name):
            raise ValueError("channel name may contain letters, numbers, underscores, and hyphens")
        return name

    @field_validator("topic")
    @classmethod
    def normalize_topic(cls, value: str) -> str:
        return value.strip()


class Channel(BaseModel):
    id: int
    name: str
    topic: str
    created_at: int


class Attachment(BaseModel):
    id: int
    filename: str
    content_type: str
    size: int
    url: str


class MessageCreate(BaseModel):
    hub_user_id: str = Field(min_length=1, max_length=120)
    username: str = Field(min_length=1, max_length=40)
    display_name: str = Field(min_length=1, max_length=80)
    avatar_url: str | None = Field(default=None, max_length=2048)
    content: str = Field(max_length=MAX_MESSAGE_LENGTH)

    @field_validator("hub_user_id", "username", "display_name")
    @classmethod
    def strip_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        return value.strip()


class MessageUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        content = value.strip()
        if not content:
            raise ValueError("message must not be empty")
        return content


class Message(BaseModel):
    id: int
    channel_id: int
    author_id: str
    author_name: str
    author_avatar_url: str | None = None
    content: str
    created_at: int
    updated_at: int | None
    deleted_at: int | None
    attachments: list[Attachment] = Field(default_factory=list)


class WebhookCreate(BaseModel):
    channel_id: int
    name: str = Field(min_length=1, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=2048)

    @field_validator("name")
    @classmethod
    def strip_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be empty")
        return value


# Returned only on POST /api/webhooks — includes the secret token once.
# The caller must store the token immediately; it is not retrievable again via GET.
class WebhookCreateResponse(BaseModel):
    id: int
    channel_id: int
    name: str
    avatar_url: str | None = None
    token: str
    enabled: bool
    created_at: int
    url: str


# Returned by GET /api/webhooks — token is intentionally omitted for security.
class WebhookListItem(BaseModel):
    id: int
    channel_id: int
    name: str
    avatar_url: str | None = None
    enabled: bool
    created_at: int
    url: str


class WebhookPayload(BaseModel):
    content: str
    username: str | None = Field(default=None, min_length=1, max_length=80)
    avatar_url: str | None = Field(default=None, max_length=2048)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        content = value.strip()
        if not content:
            raise ValueError("content must not be empty")
        if len(content) > MAX_MESSAGE_LENGTH:
            raise ValueError(f"content exceeds maximum message length ({MAX_MESSAGE_LENGTH})")
        return content

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        username = value.strip()
        if not username:
            raise ValueError("username must not be empty")
        return username


EXECUTABLE_EXTENSIONS = {
    ".bat",
    ".cmd",
    ".com",
    ".exe",
    ".jar",
    ".msi",
    ".ps1",
    ".scr",
    ".sh",
    ".vbs",
}
SVG_CONTENT_TYPES = {"image/svg+xml", "image/svg"}


def validate_attachment_file(filename: str, content_type: str) -> None:
    if not ALLOW_EXECUTABLE_FILES and Path(filename).suffix.lower() in EXECUTABLE_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Executable file uploads are disabled")
    normalized_type = content_type.split(";", 1)[0].strip().lower()
    if Path(filename).suffix.lower() == ".svg" or normalized_type in SVG_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="SVG uploads are disabled")
    if ALLOWED_FILE_TYPES and not any(fnmatch.fnmatch(normalized_type, pattern) for pattern in ALLOWED_FILE_TYPES):
        raise HTTPException(status_code=415, detail="File type is not allowed by this server")


async def write_upload_file(file: UploadFile, target: Path) -> int:
    size = 0
    with target.open("wb") as output:
        while True:
            chunk = await file.read(UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_ATTACHMENT_SIZE:
                raise HTTPException(status_code=413, detail=f"Files must be {MAX_ATTACHMENT_SIZE} bytes or smaller")
            await asyncio.to_thread(output.write, chunk)
    return size


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DATABASE_PATH, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 5000")
    return db


def initialize_database() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    now = int(time.time())
    with connect() as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS guild_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                guild_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                topic TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS members (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL DEFAULT '',
                display_name TEXT NOT NULL,
                avatar_url TEXT,
                created_at INTEGER NOT NULL,
                last_seen_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
                author_id TEXT NOT NULL REFERENCES members(id),
                content TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER,
                deleted_at INTEGER
            );
            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                stored_name TEXT NOT NULL UNIQUE,
                filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                size INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS invites (
                code TEXT PRIMARY KEY,
                created_at INTEGER NOT NULL,
                expires_at INTEGER,
                max_uses INTEGER,
                use_count INTEGER NOT NULL DEFAULT 0,
                is_startup INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS incoming_webhooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                avatar_url TEXT,
                token TEXT NOT NULL UNIQUE,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS server_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at INTEGER NOT NULL,
                updated_by TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel_id, id DESC);
            CREATE INDEX IF NOT EXISTS idx_attachments_message ON attachments(message_id, id);
            """
        )
        db.execute(
            """INSERT OR IGNORE INTO guild_settings (id, guild_id, name, description, created_at)
               VALUES (1, ?, ?, ?, ?)""",
            (uuid.uuid4().hex, SERVER_NAME, SERVER_DESCRIPTION, now),
        )
        db.execute(
            "UPDATE guild_settings SET name = ?, description = ? WHERE id = 1",
            (SERVER_NAME, SERVER_DESCRIPTION),
        )
        db.execute(
            """INSERT OR IGNORE INTO channels (name, topic, created_at)
               VALUES (?, 'General conversation', ?)""",
            (DEFAULT_CHANNEL_NAME, now),
        )
        columns = {row["name"] for row in db.execute("PRAGMA table_info(invites)").fetchall()}
        if "is_startup" not in columns:
            db.execute("ALTER TABLE invites ADD COLUMN is_startup INTEGER NOT NULL DEFAULT 0")
        member_columns = {row["name"] for row in db.execute("PRAGMA table_info(members)").fetchall()}
        if "username" not in member_columns:
            db.execute("ALTER TABLE members ADD COLUMN username TEXT NOT NULL DEFAULT ''")
        if "avatar_url" not in member_columns:
            db.execute("ALTER TABLE members ADD COLUMN avatar_url TEXT")
        if "role" not in member_columns:
            db.execute("ALTER TABLE members ADD COLUMN role TEXT NOT NULL DEFAULT 'member'")
        
        webhook_columns = {row["name"] for row in db.execute("PRAGMA table_info(incoming_webhooks)").fetchall()}
        if "avatar_url" not in webhook_columns:
            db.execute("ALTER TABLE incoming_webhooks ADD COLUMN avatar_url TEXT")


def get_server_setting_int(db, key: str, default: int) -> int:
    row = db.execute("SELECT value FROM server_settings WHERE key = ?", (key,)).fetchone()
    if not row:
        return default
    try:
        return int(row["value"])
    except ValueError:
        return default


def get_current_max_channels(db) -> int:
    return get_server_setting_int(db, "max_channels", MAX_CHANNELS)


def set_server_setting(db, key: str, value: str, updated_by: str | None = None) -> None:
    db.execute(
        """
        INSERT INTO server_settings (key, value, updated_at, updated_by)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at,
            updated_by = excluded.updated_by
        """,
        (key, value, int(time.time()), updated_by),
    )


class ServerPermission:
    MANAGE_SERVER = "MANAGE_SERVER"
    MANAGE_CHANNELS = "MANAGE_CHANNELS"
    MANAGE_WEBHOOKS = "MANAGE_WEBHOOKS"
    CREATE_INVITE = "CREATE_INVITE"
    SEND_MESSAGES = "SEND_MESSAGES"
    ATTACH_FILES = "ATTACH_FILES"
    MANAGE_MESSAGES = "MANAGE_MESSAGES"


def has_server_permission(db: sqlite3.Connection, member_id: str, permission: str) -> bool:
    row = db.execute("SELECT role FROM members WHERE id = ?", (member_id,)).fetchone()
    if not row:
        return False
    role = row["role"]
    if role == "owner":
        return True
    if role == "admin":
        return True
    if role == "moderator":
        return permission in {
            ServerPermission.SEND_MESSAGES,
            ServerPermission.ATTACH_FILES,
            ServerPermission.CREATE_INVITE,
            ServerPermission.MANAGE_MESSAGES,
        }
    return permission in {
        ServerPermission.SEND_MESSAGES,
        ServerPermission.ATTACH_FILES,
        ServerPermission.CREATE_INVITE,
    }


def require_hub_user_id(x_catchat_hub_user_id: Annotated[str | None, Header()] = None) -> str:
    member_id = (x_catchat_hub_user_id or "").strip()
    if not member_id:
        raise HTTPException(status_code=403, detail="X-Catchat-Hub-User-Id header is required")
    return member_id


def require_member_permission(db: sqlite3.Connection, member_id: str, permission: str) -> None:
    if not has_server_permission(db, member_id, permission):
        raise HTTPException(status_code=403, detail=f"Permission required: {permission}")


def require_secret(authorization: Annotated[str | None, Header()] = None) -> None:
    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        raise HTTPException(status_code=401, detail="Server authorization required")
    supplied = authorization[len(prefix):].strip()
    if not secrets.compare_digest(supplied, SERVER_SECRET):
        raise HTTPException(status_code=401, detail="Invalid server authorization")


def authorize_socket(websocket: WebSocket) -> bool:
    authorization = websocket.headers.get("authorization", "")
    prefix = "Bearer "
    return authorization.startswith(prefix) and secrets.compare_digest(
        authorization[len(prefix):].strip(), SERVER_SECRET
    )


def channel_or_404(db: sqlite3.Connection, channel_id: int) -> sqlite3.Row:
    channel = db.execute("SELECT * FROM channels WHERE id = ?", (channel_id,)).fetchone()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


def attachment_from_row(row: sqlite3.Row) -> Attachment:
    return Attachment(
        id=row["id"],
        filename=row["filename"],
        content_type=row["content_type"],
        size=row["size"],
        url=f"/api/attachments/{row['id']}",
    )


def fetch_message(db: sqlite3.Connection, message_id: int) -> Message:
    row = db.execute(
        """SELECT messages.*, members.display_name AS author_name, members.avatar_url AS author_avatar_url
           FROM messages JOIN members ON members.id = messages.author_id
           WHERE messages.id = ?""",
        (message_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Message not found")
    attachments = db.execute(
        "SELECT * FROM attachments WHERE message_id = ? ORDER BY id", (message_id,)
    ).fetchall()
    return Message(
        id=row["id"],
        channel_id=row["channel_id"],
        author_id=row["author_id"],
        author_name=row["author_name"],
        author_avatar_url=row["author_avatar_url"],
        content="" if row["deleted_at"] is not None else row["content"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
        attachments=[] if row["deleted_at"] is not None else [attachment_from_row(item) for item in attachments],
    )


def cleanup_empty_message(db: sqlite3.Connection, message_id: int, author_id: str | None = None) -> Message | None:
    try:
        message = fetch_message(db, message_id)
    except HTTPException:
        return None
    if author_id is not None and message.author_id != author_id:
        return None
    if message.deleted_at is not None or message.content or message.attachments:
        return None
    db.execute(
        "UPDATE messages SET content = '', deleted_at = ? WHERE id = ?",
        (int(time.time()), message_id),
    )
    return fetch_message(db, message_id)


def cleanup_stale_empty_messages() -> None:
    cutoff = int(time.time()) - EMPTY_MESSAGE_CLEANUP_SECONDS
    with connect() as db:
        rows = db.execute(
            """SELECT id FROM messages
               WHERE deleted_at IS NULL AND TRIM(content) = '' AND created_at <= ?
                 AND NOT EXISTS (SELECT 1 FROM attachments WHERE attachments.message_id = messages.id)""",
            (cutoff,),
        ).fetchall()
        for row in rows:
            cleanup_empty_message(db, row["id"])


def messages_for_channel(db: sqlite3.Connection, channel_id: int, limit: int) -> list[Message]:
    rows = db.execute(
        "SELECT id FROM messages WHERE channel_id = ? ORDER BY id DESC LIMIT ?",
        (channel_id, limit),
    ).fetchall()
    return [fetch_message(db, row["id"]) for row in reversed(rows)]


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: dict[int, set[WebSocket]] = {}
        self.lock = asyncio.Lock()

    async def connect(self, channel_id: int, socket: WebSocket) -> None:
        await socket.accept()
        async with self.lock:
            self.connections.setdefault(channel_id, set()).add(socket)

    async def disconnect(self, channel_id: int, socket: WebSocket) -> None:
        async with self.lock:
            self.connections.get(channel_id, set()).discard(socket)

    async def broadcast(self, channel_id: int, event_type: str, message: Message) -> None:
        event = {"type": event_type, "message": message.model_dump()}
        for socket in list(self.connections.get(channel_id, set())):
            try:
                await socket.send_json(event)
            except (RuntimeError, WebSocketDisconnect):
                await self.disconnect(channel_id, socket)


initialize_database()
cleanup_stale_empty_messages()
manager = ConnectionManager()
app = FastAPI(title="catChat Server", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Catchat-Hub-User-Id"],
)


@app.get("/api/guild/info", response_model=GuildInfo)
def guild_info() -> GuildInfo:
    with connect() as db:
        settings = db.execute("SELECT * FROM guild_settings WHERE id = 1").fetchone()
        channel_count = db.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
        member_count = db.execute("SELECT COUNT(*) FROM members").fetchone()[0]
        current_max_channels = get_current_max_channels(db)
    return GuildInfo(
        id=settings["guild_id"],
        name=settings["name"],
        description=settings["description"],
        version="0.1.0",
        channel_count=channel_count,
        member_count=member_count,
        max_attachment_size=MAX_ATTACHMENT_SIZE,
        max_message_length=MAX_MESSAGE_LENGTH,
        limits=GuildLimits(
            max_attachment_size=MAX_ATTACHMENT_SIZE,
            max_attachment_size_mb=MAX_ATTACHMENT_SIZE // (1024 * 1024),
            max_attachments_per_message=MAX_ATTACHMENTS_PER_MESSAGE,
            max_message_length=MAX_MESSAGE_LENGTH,
            max_message_history=MAX_MESSAGE_HISTORY,
            max_channels=current_max_channels,
            max_members=MAX_MEMBERS,
            allowed_file_types=ALLOWED_FILE_TYPES,
            allow_executable_files=ALLOW_EXECUTABLE_FILES,
        ),
        features=GuildFeatures(
            message_edit=ALLOW_MESSAGE_EDIT,
            message_delete=ALLOW_MESSAGE_DELETE,
            replies=ALLOW_REPLIES,
            reactions=ALLOW_REACTIONS,
            channel_create=ALLOW_CHANNEL_CREATE,
            default_invite_enabled=DEFAULT_INVITE_ENABLED,
            allow_users_create_invites=ALLOW_USERS_CREATE_INVITES,
            bans=ENABLE_BANS,
            kicks=ENABLE_KICKS,
            reports=ENABLE_REPORTS,
            audit_log=ENABLE_AUDIT_LOG,
            require_hub_proxy=REQUIRE_HUB_PROXY,
            allow_direct_browser_access=ALLOW_DIRECT_BROWSER_ACCESS,
        )
    )


@app.get("/api/server/info", response_model=GuildInfo)
def server_info() -> GuildInfo:
    return guild_info()


@app.get("/api/server/settings", response_model=ServerSettingsResponse, dependencies=[Depends(require_secret)])
def get_server_settings() -> ServerSettingsResponse:
    with connect() as db:
        max_channels = get_current_max_channels(db)
        channel_count = db.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
    return ServerSettingsResponse(
        max_channels=max_channels,
        channel_count=channel_count,
        allow_channel_create=ALLOW_CHANNEL_CREATE,
    )


@app.patch("/api/server/settings", response_model=ServerSettingsResponse, dependencies=[Depends(require_secret)])
def update_server_settings(data: ServerSettingsPatch) -> ServerSettingsResponse:
    with connect() as db:
        set_server_setting(db, "max_channels", str(data.max_channels))
        max_channels = get_current_max_channels(db)
        channel_count = db.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
    return ServerSettingsResponse(
        max_channels=max_channels,
        channel_count=channel_count,
        allow_channel_create=ALLOW_CHANNEL_CREATE,
    )


@app.get("/api/guild/health", response_model=GuildHealth)
def guild_health() -> GuildHealth:
    with connect() as db:
        db.execute("SELECT 1").fetchone()
    return GuildHealth(status="ok", storage="local", websocket="enabled", timestamp=int(time.time()))


@app.get("/api/server/health", response_model=GuildHealth)
def server_health() -> GuildHealth:
    return guild_health()


@app.get("/api/channels", response_model=list[Channel], dependencies=[Depends(require_secret)])
def get_channels() -> list[Channel]:
    with connect() as db:
        return [Channel(**dict(row)) for row in db.execute("SELECT * FROM channels ORDER BY id").fetchall()]


@app.post("/api/channels", response_model=Channel, status_code=201, dependencies=[Depends(require_secret)])
def create_channel(data: ChannelCreate, hub_user_id: Annotated[str, Depends(require_hub_user_id)]) -> Channel:
    if not ALLOW_CHANNEL_CREATE:
        raise HTTPException(status_code=403, detail="Channel creation is disabled on this server")
    try:
        with connect() as db:
            require_member_permission(db, hub_user_id, ServerPermission.MANAGE_CHANNELS)
            channel_count = db.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
            current_max_channels = get_current_max_channels(db)
            if current_max_channels > 0 and channel_count >= current_max_channels:
                raise HTTPException(status_code=403, detail=f"Maximum channel count reached ({current_max_channels})")
            cursor = db.execute(
                "INSERT INTO channels (name, topic, created_at) VALUES (?, ?, ?)",
                (data.name, data.topic, int(time.time())),
            )
            row = db.execute("SELECT * FROM channels WHERE id = ?", (cursor.lastrowid,)).fetchone()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Channel name is already in use")
    return Channel(**dict(row))


@app.get("/api/channels/{channel_id}/messages", response_model=list[Message], dependencies=[Depends(require_secret)])
def get_messages(
    channel_id: int,
    limit: Annotated[int, Query(ge=1, le=MAX_MESSAGE_HISTORY)] = MAX_MESSAGE_HISTORY,
) -> list[Message]:
    with connect() as db:
        channel_or_404(db, channel_id)
        return messages_for_channel(db, channel_id, limit)


@app.get("/api/messages/search", response_model=list[Message], dependencies=[Depends(require_secret)])
def search_messages(q: Annotated[str, Query(min_length=1, max_length=100)]) -> list[Message]:
    with connect() as db:
        rows = db.execute(
            "SELECT id FROM messages WHERE deleted_at IS NULL AND content LIKE ? ORDER BY id DESC LIMIT 50",
            (f"%{q.strip()}%",),
        ).fetchall()
        return [fetch_message(db, row["id"]) for row in reversed(rows)]


@app.post("/api/channels/{channel_id}/messages", response_model=Message, status_code=201, dependencies=[Depends(require_secret)])
async def create_message(channel_id: int, data: MessageCreate) -> Message:
    now = int(time.time())
    with connect() as db:
        channel_or_404(db, channel_id)
        if MAX_MEMBERS > 0:
            is_member = db.execute("SELECT 1 FROM members WHERE id = ?", (data.hub_user_id,)).fetchone()
            if not is_member:
                member_count = db.execute("SELECT COUNT(*) FROM members").fetchone()[0]
                if member_count >= MAX_MEMBERS:
                    raise HTTPException(status_code=403, detail=f"Maximum member limit reached ({MAX_MEMBERS})")
        db.execute(
            """INSERT INTO members (id, username, display_name, avatar_url, created_at, last_seen_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET username = excluded.username, display_name = excluded.display_name,
                   avatar_url = excluded.avatar_url, last_seen_at = excluded.last_seen_at""",
            (data.hub_user_id, data.username, data.display_name, data.avatar_url, now, now),
        )
        cursor = db.execute(
            "INSERT INTO messages (channel_id, author_id, content, created_at) VALUES (?, ?, ?, ?)",
            (channel_id, data.hub_user_id, data.content, now),
        )
        message = fetch_message(db, cursor.lastrowid)
    await manager.broadcast(channel_id, "message.created", message)
    return message


@app.patch("/api/messages/{message_id}", response_model=Message, dependencies=[Depends(require_secret)])
async def update_message(
    message_id: int,
    data: MessageUpdate,
    hub_user_id: Annotated[str, Depends(require_hub_user_id)],
) -> Message:
    if not ALLOW_MESSAGE_EDIT:
        raise HTTPException(status_code=403, detail="Message editing is disabled on this server")
    with connect() as db:
        existing = fetch_message(db, message_id)
        if existing.deleted_at is not None:
            raise HTTPException(status_code=409, detail="Deleted messages cannot be edited")
        if existing.author_id != hub_user_id:
            require_member_permission(db, hub_user_id, ServerPermission.MANAGE_MESSAGES)
        db.execute(
            "UPDATE messages SET content = ?, updated_at = ? WHERE id = ?",
            (data.content, int(time.time()), message_id),
        )
        message = fetch_message(db, message_id)
    await manager.broadcast(message.channel_id, "message.updated", message)
    return message


@app.delete("/api/messages/{message_id}", response_model=Message, dependencies=[Depends(require_secret)])
async def delete_message(
    message_id: int,
    hub_user_id: Annotated[str, Depends(require_hub_user_id)],
) -> Message:
    if not ALLOW_MESSAGE_DELETE:
        raise HTTPException(status_code=403, detail="Message deletion is disabled on this server")
    with connect() as db:
        existing = fetch_message(db, message_id)
        if existing.author_id != hub_user_id:
            require_member_permission(db, hub_user_id, ServerPermission.MANAGE_MESSAGES)
        if existing.deleted_at is None:
            db.execute(
                "UPDATE messages SET content = '', deleted_at = ? WHERE id = ?",
                (int(time.time()), message_id),
            )
        message = fetch_message(db, message_id)
    await manager.broadcast(message.channel_id, "message.deleted", message)
    return message


@app.post("/api/messages/{message_id}/attachments", response_model=Message, status_code=201, dependencies=[Depends(require_secret)])
async def add_attachment(
    message_id: int,
    file: Annotated[UploadFile, File()],
    x_catchat_hub_user_id: Annotated[str | None, Header()] = None,
) -> Message:
    with connect() as db:
        existing = fetch_message(db, message_id)
        if existing.deleted_at is not None:
            raise HTTPException(status_code=409, detail="Attachments cannot be added to deleted messages")
        if not x_catchat_hub_user_id or existing.author_id != x_catchat_hub_user_id:
            raise HTTPException(status_code=403, detail="Attachments can only be added to your own messages")
        attachment_count = db.execute(
            "SELECT COUNT(*) FROM attachments WHERE message_id = ?", (message_id,)
        ).fetchone()[0]
        if attachment_count >= MAX_ATTACHMENTS_PER_MESSAGE:
            raise HTTPException(status_code=409, detail="Maximum attachments per message reached")
    target: Path | None = None
    try:
        filename = Path(file.filename or "attachment").name[:255] or "attachment"
        content_type = file.content_type or "application/octet-stream"
        validate_attachment_file(filename, content_type)
        stored_name = uuid.uuid4().hex
        target = UPLOAD_DIR / stored_name
        size = await write_upload_file(file, target)
        with connect() as db:
            db.execute(
                """INSERT INTO attachments
                   (message_id, stored_name, filename, content_type, size, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (message_id, stored_name, filename, content_type, size, int(time.time())),
            )
            message = fetch_message(db, message_id)
    except Exception:
        if target is not None:
            target.unlink(missing_ok=True)
        deleted_message = None
        with connect() as db:
            deleted_message = cleanup_empty_message(db, message_id, x_catchat_hub_user_id)
        if deleted_message is not None:
            await manager.broadcast(deleted_message.channel_id, "message.deleted", deleted_message)
        raise
    await manager.broadcast(message.channel_id, "message.updated", message)
    return message


@app.get("/api/attachments/{attachment_id}", dependencies=[Depends(require_secret)])
def download_attachment(attachment_id: int) -> FileResponse:
    with connect() as db:
        row = db.execute(
            """SELECT attachments.* FROM attachments
               JOIN messages ON messages.id = attachments.message_id
               WHERE attachments.id = ? AND messages.deleted_at IS NULL""",
            (attachment_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Attachment not found")
        path = UPLOAD_DIR / row["stored_name"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Attachment file not found")
    return FileResponse(path, media_type=row["content_type"], filename=row["filename"])


@app.websocket("/ws/channels/{channel_id}")
async def channel_socket(websocket: WebSocket, channel_id: int) -> None:
    if not authorize_socket(websocket):
        await websocket.close(code=1008)
        return
    with connect() as db:
        try:
            channel_or_404(db, channel_id)
        except HTTPException:
            await websocket.close(code=1008)
            return
    await manager.connect(channel_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(channel_id, websocket)


# ==============================================================================
# FEDERATION & INVITE ENDPOINTS
# ==============================================================================
# Security policy:
#   - /api/server/invite/{code}  : public (no auth) — returns public metadata only
#   - /api/server/join           : public (no auth) — returns public info ONLY, NEVER secret
#   - /api/server/register       : hub backend ONLY (X-Catchat-Registration-Token required)
#                                  hidden from OpenAPI schema (include_in_schema=False)
#                                  returns secret ONLY to authenticated hub backend caller
# The SERVER_SECRET / GUILD_SECRET must NEVER be sent to browsers or end users.
# ==============================================================================

class InviteCheckResponse(BaseModel):
    code: str
    guild_id: str
    name: str
    description: str
    version: str
    channel_count: int
    member_count: int
    valid: bool
    limits: GuildLimits | None = None
    features: GuildFeatures | None = None

class JoinRequest(BaseModel):
    code: str

class JoinResponse(BaseModel):
    """Public join response — contains NO secret fields. Safe to return to any caller."""
    joined: bool
    server_id: str
    name: str
    member_count: int

# SECURITY: ServerRegistrationResponse is for hub backend use ONLY.
# This model is intentionally NOT exposed to browser clients or end users.
# It is returned exclusively by /api/server/register, which requires
# a pre-shared X-Catchat-Registration-Token header and is hidden from OpenAPI docs.
class ServerRegistrationResponse(JoinResponse):
    secret: str

class GuildMember(BaseModel):
    id: str
    username: str
    display_name: str
    avatar_url: str | None
    created_at: int
    last_seen_at: int


def build_hub_invite_url(invite_code: str) -> str:
    token_payload = {"url": PUBLIC_URL, "code": invite_code}
    token_json = json.dumps(token_payload, separators=(",", ":")).encode()
    token = base64.urlsafe_b64encode(token_json).rstrip(b"=").decode()
    return f"{HUB_URL}/add-server?invite={token}"


@app.on_event("startup")
def on_startup():
    now = int(time.time())
    invite_code = None
    with connect() as db:
        if STARTUP_INVITE_CODE:
            invite_code = STARTUP_INVITE_CODE
            max_uses = DEFAULT_INVITE_MAX_USES if DEFAULT_INVITE_MAX_USES > 0 else None
            expires_at = now + (DEFAULT_INVITE_EXPIRES_HOURS * 3600) if DEFAULT_INVITE_EXPIRES_HOURS > 0 else None
            db.execute("DELETE FROM invites WHERE is_startup = 1 AND code != ?", (invite_code,))
            db.execute(
                """INSERT INTO invites (code, max_uses, expires_at, created_at, use_count, is_startup)
                   VALUES (?, ?, ?, ?, 0, 1)
                   ON CONFLICT(code) DO UPDATE SET
                     max_uses = excluded.max_uses,
                     expires_at = excluded.expires_at,
                     is_startup = 1
                """,
                (invite_code, max_uses, expires_at, now),
            )
        elif DEFAULT_INVITE_ENABLED:
            row = db.execute("SELECT code FROM invites WHERE is_startup = 1 ORDER BY created_at LIMIT 1").fetchone()
            if row:
                invite_code = row["code"]
            else:
                invite_code = f"INVITE-{secrets.token_urlsafe(12)}"
                max_uses = DEFAULT_INVITE_MAX_USES if DEFAULT_INVITE_MAX_USES > 0 else None
                expires_at = now + (DEFAULT_INVITE_EXPIRES_HOURS * 3600) if DEFAULT_INVITE_EXPIRES_HOURS > 0 else None
                db.execute(
                    "INSERT INTO invites (code, max_uses, expires_at, created_at, use_count, is_startup) VALUES (?, ?, ?, ?, 0, 1)",
                    (invite_code, max_uses, expires_at, now),
                )

    print("\n" + "="*80)
    print("catChat Server Started")
    print()
    print(f"Server Name: {SERVER_NAME}")
    print(f"Public URL: {PUBLIC_URL}")
    print(f"Hub URL: {HUB_URL}")
    print()
    
    if REQUIRE_HUB_PROXY:
        print("Note: This server is configured to require Hub Proxy (recommended).")
    if not ALLOW_DIRECT_BROWSER_ACCESS:
        print("Warning: Direct browser access is deprecated and not recommended (allow-direct-browser-access=false).")
        print("         Please access this server via catChat Hub Proxy.")
        print()

    if invite_code:
        hub_invite_url = build_hub_invite_url(invite_code)
        print("Add this server to catChat Hub (legacy format):")
        print(f"{hub_invite_url}")
        print()
        print("This invite does not contain your server secret.")
        
        if REGISTRATION_TOKEN and HUB_URL:
            def register_to_hub():
                import urllib.request
                import json
                try:
                    data = {
                        "server_name": SERVER_NAME,
                        "server_public_url": PUBLIC_URL,
                        "server_invite_code": invite_code,
                        "registration_token": REGISTRATION_TOKEN
                    }
                    req = urllib.request.Request(
                        f"{HUB_URL.rstrip('/')}/api/server-registry/register",
                        data=json.dumps(data).encode("utf-8"),
                        headers={"Content-Type": "application/json"}
                    )
                    with urllib.request.urlopen(req, timeout=10) as res:
                        result = json.loads(res.read().decode("utf-8"))
                        print()
                        print("✅ Successfully registered to Hub!")
                        print(f"👉 Common Invite Link: {result.get('join_url')}")
                except Exception as e:
                    print()
                    print(f"⚠️ Failed to register to Hub: {e}")

            import threading
            threading.Thread(target=register_to_hub, daemon=True).start()

    else:
        print("Startup invite disabled")
    print("="*80 + "\n")


def _validate_invite(db: sqlite3.Connection, code: str) -> sqlite3.Row:
    """Validate an invite code and return its row. Raises HTTPException on failure."""
    now = int(time.time())
    row = db.execute("SELECT * FROM invites WHERE code = ?", (code,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Invite code not found")
    if row["expires_at"] is not None and row["expires_at"] <= now:
        raise HTTPException(status_code=400, detail="Invite code expired")
    if row["max_uses"] is not None and row["use_count"] >= row["max_uses"]:
        raise HTTPException(status_code=400, detail="Invite code maximum uses reached")
    if MAX_MEMBERS > 0:
        member_count = db.execute("SELECT COUNT(*) FROM members").fetchone()[0]
        if member_count >= MAX_MEMBERS:
            raise HTTPException(status_code=403, detail="Maximum member count reached")
    return row


def _consume_invite(db: sqlite3.Connection, code: str) -> sqlite3.Row:
    """Validate an invite and atomically consume one use."""
    row = _validate_invite(db, code)
    cursor = db.execute(
        """UPDATE invites
           SET use_count = use_count + 1
           WHERE code = ?
             AND (max_uses IS NULL OR use_count < max_uses)""",
        (code,),
    )
    if cursor.rowcount != 1:
        raise HTTPException(status_code=400, detail="Invite code maximum uses reached")
    return row


def _public_join_response(db: sqlite3.Connection) -> JoinResponse:
    settings = db.execute("SELECT * FROM guild_settings WHERE id = 1").fetchone()
    member_count = db.execute("SELECT COUNT(*) FROM members").fetchone()[0]
    return JoinResponse(
        joined=True,
        server_id=settings["guild_id"],
        name=settings["name"],
        member_count=member_count,
    )


def require_registration_token(x_catchat_registration_token: Annotated[str | None, Header()] = None) -> None:
    if not REGISTRATION_TOKEN:
        raise HTTPException(status_code=404, detail="Server registration is not enabled")
    if not x_catchat_registration_token or not secrets.compare_digest(x_catchat_registration_token, REGISTRATION_TOKEN):
        raise HTTPException(status_code=401, detail="Server registration authorization required")


@app.get("/api/server/invite/{code}", response_model=InviteCheckResponse)
def check_invite_code(code: str) -> InviteCheckResponse:
    with connect() as db:
        _validate_invite(db, code)

        settings = db.execute("SELECT * FROM guild_settings WHERE id = 1").fetchone()
        channel_count = db.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
        member_count = db.execute("SELECT COUNT(*) FROM members").fetchone()[0]
        current_max_channels = get_current_max_channels(db)

    return InviteCheckResponse(
        code=code,
        guild_id=settings["guild_id"],
        name=settings["name"],
        description=settings["description"],
        version="0.1.0",
        channel_count=channel_count,
        member_count=member_count,
        valid=True,
        limits=GuildLimits(
            max_attachment_size=MAX_ATTACHMENT_SIZE,
            max_attachment_size_mb=MAX_ATTACHMENT_SIZE // (1024 * 1024),
            max_attachments_per_message=MAX_ATTACHMENTS_PER_MESSAGE,
            max_message_length=MAX_MESSAGE_LENGTH,
            max_message_history=MAX_MESSAGE_HISTORY,
            max_channels=current_max_channels,
            max_members=MAX_MEMBERS,
            allowed_file_types=ALLOWED_FILE_TYPES,
            allow_executable_files=ALLOW_EXECUTABLE_FILES,
        ),
        features=GuildFeatures(
            message_edit=ALLOW_MESSAGE_EDIT,
            message_delete=ALLOW_MESSAGE_DELETE,
            replies=ALLOW_REPLIES,
            reactions=ALLOW_REACTIONS,
            channel_create=ALLOW_CHANNEL_CREATE,
            default_invite_enabled=DEFAULT_INVITE_ENABLED,
            allow_users_create_invites=ALLOW_USERS_CREATE_INVITES,
            bans=ENABLE_BANS,
            kicks=ENABLE_KICKS,
            reports=ENABLE_REPORTS,
            audit_log=ENABLE_AUDIT_LOG,
            require_hub_proxy=REQUIRE_HUB_PROXY,
            allow_direct_browser_access=ALLOW_DIRECT_BROWSER_ACCESS,
        )
    )


# SECURITY: Public endpoint — accessible by anyone with a valid invite code.
# response_model=JoinResponse ensures only public fields are serialized.
# response_model_exclude is set as a second layer of defence to guarantee
# the `secret` field can never appear in this response even if the model
# is accidentally changed in the future.
@app.post(
    "/api/server/join",
    response_model=JoinResponse,
    response_model_exclude={"secret"},
)
def join_guild_server(data: JoinRequest) -> JoinResponse:
    """Public endpoint: validate invite and return public server info. Never returns secret."""
    with connect() as db:
        _consume_invite(db, data.code)
        return _public_join_response(db)


# SECURITY: Hub backend registration endpoint — NOT for browser use.
# - Requires X-Catchat-Registration-Token header (pre-shared between hub and this server).
# - Returns the server secret ONLY to the authenticated hub backend caller so it can
#   store it encrypted in its own database and use it as a proxy credential.
# - Hidden from OpenAPI docs (include_in_schema=False) to reduce attack surface.
# - The secret returned here is NEVER forwarded to browser clients by the hub backend.
@app.post(
    "/api/server/register",
    response_model=ServerRegistrationResponse,
    dependencies=[Depends(require_registration_token)],
    include_in_schema=False,
)
def register_guild_server(data: JoinRequest) -> ServerRegistrationResponse:
    """Hub backend only: register this server and receive the secret for proxy auth."""
    with connect() as db:
        _consume_invite(db, data.code)
        public_response = _public_join_response(db)

    return ServerRegistrationResponse(**public_response.model_dump(), secret=SERVER_SECRET)


@app.get("/api/members", response_model=list[GuildMember], dependencies=[Depends(require_secret)])
def get_guild_members() -> list[GuildMember]:
    with connect() as db:
        rows = db.execute("SELECT * FROM members ORDER BY display_name").fetchall()
        return [GuildMember(**dict(row)) for row in rows]


def check_webhooks_enabled() -> None:
    if not ENABLE_INCOMING_WEBHOOKS:
        raise HTTPException(status_code=403, detail="Incoming webhooks are disabled on this server")


webhook_request_history: dict[str, list[float]] = {}


@app.post(
    "/api/webhooks",
    response_model=WebhookCreateResponse,
    status_code=201,
    dependencies=[Depends(check_webhooks_enabled), Depends(require_secret)],
)
def create_webhook(
    data: WebhookCreate,
    hub_user_id: Annotated[str, Depends(require_hub_user_id)],
) -> WebhookCreateResponse:
    now = int(time.time())
    with connect() as db:
        require_member_permission(db, hub_user_id, ServerPermission.MANAGE_WEBHOOKS)
        channel_or_404(db, data.channel_id)
        count = db.execute("SELECT COUNT(*) FROM incoming_webhooks WHERE enabled = 1").fetchone()[0]
        if count >= MAX_WEBHOOKS:
            raise HTTPException(status_code=409, detail=f"Maximum webhook limit reached ({MAX_WEBHOOKS})")

        token = secrets.token_urlsafe(32)
        cursor = db.execute(
            """INSERT INTO incoming_webhooks (channel_id, name, avatar_url, token, enabled, created_at)
               VALUES (?, ?, ?, ?, 1, ?)""",
            (data.channel_id, data.name, data.avatar_url, token, now),
        )
        webhook_id = cursor.lastrowid
        row = db.execute("SELECT * FROM incoming_webhooks WHERE id = ?", (webhook_id,)).fetchone()

    url = f"{PUBLIC_URL}/api/webhooks/{webhook_id}/{token}"
    return WebhookCreateResponse(
        id=row["id"],
        channel_id=row["channel_id"],
        name=row["name"],
        avatar_url=row["avatar_url"],
        token=row["token"],
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],
        url=url,
    )


@app.get(
    "/api/webhooks",
    response_model=list[WebhookListItem],
    dependencies=[Depends(check_webhooks_enabled), Depends(require_secret)],
)
def get_webhooks() -> list[WebhookListItem]:
    """List all webhooks. Token is intentionally excluded from the response."""
    with connect() as db:
        rows = db.execute("SELECT * FROM incoming_webhooks ORDER BY id DESC").fetchall()

    res = []
    for row in rows:
        # Build a masked URL that shows the id but hides the token
        masked_url = f"{PUBLIC_URL}/api/webhooks/{row['id']}/<token>"
        res.append(
            WebhookListItem(
                id=row["id"],
                channel_id=row["channel_id"],
                name=row["name"],
                avatar_url=row["avatar_url"],
                enabled=bool(row["enabled"]),
                created_at=row["created_at"],
                url=masked_url,
            )
        )
    return res


@app.delete(
    "/api/webhooks/{webhook_id}",
    dependencies=[Depends(check_webhooks_enabled), Depends(require_secret)],
)
def delete_webhook(
    webhook_id: int,
    hub_user_id: Annotated[str, Depends(require_hub_user_id)],
) -> dict[str, bool]:
    """Logically disable a webhook (sets enabled=0). Does not physically delete it."""
    with connect() as db:
        require_member_permission(db, hub_user_id, ServerPermission.MANAGE_WEBHOOKS)
        row = db.execute("SELECT * FROM incoming_webhooks WHERE id = ?", (webhook_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Webhook not found")
        db.execute("UPDATE incoming_webhooks SET enabled = 0 WHERE id = ?", (webhook_id,))
    return {"success": True}


@app.post(
    "/api/webhooks/{webhook_id}/{token}",
    status_code=201,
    dependencies=[Depends(check_webhooks_enabled)],
)
async def execute_webhook(webhook_id: int, token: str, data: WebhookPayload) -> Message:
    now = int(time.time())
    
    with connect() as db:
        webhook = db.execute("SELECT * FROM incoming_webhooks WHERE id = ?", (webhook_id,)).fetchone()
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")
        
        if not secrets.compare_digest(webhook["token"], token):
            raise HTTPException(status_code=401, detail="Invalid webhook token")
        
        if webhook["enabled"] != 1:
            raise HTTPException(status_code=403, detail="Webhook is disabled")

        rate_limit_key = str(webhook_id)
        history = [t for t in webhook_request_history.get(rate_limit_key, []) if now - t < 60]
        webhook_request_history[rate_limit_key] = history
        if len(history) >= WEBHOOK_RATE_LIMIT_PER_MINUTE:
            raise HTTPException(
                status_code=429,
                detail="操作が多すぎます。時間をおいて再試行してください。",
            )
        webhook_request_history[rate_limit_key].append(now)
            
        channel_id = webhook["channel_id"]
        channel_or_404(db, channel_id)
        
        bot_display_name = data.username.strip() if (data.username and data.username.strip()) else webhook["name"]
        bot_avatar_url = data.avatar_url.strip() if (data.avatar_url and data.avatar_url.strip()) else webhook["avatar_url"]
        author_id = f"webhook_{webhook_id}"
        
        db.execute(
            """INSERT INTO members (id, username, display_name, avatar_url, created_at, last_seen_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET username = excluded.username, display_name = excluded.display_name,
                   avatar_url = excluded.avatar_url, last_seen_at = excluded.last_seen_at""",
            (author_id, bot_display_name.lower(), bot_display_name, bot_avatar_url, now, now),
        )
        
        cursor = db.execute(
            "INSERT INTO messages (channel_id, author_id, content, created_at) VALUES (?, ?, ?, ?)",
            (channel_id, author_id, data.content, now),
        )
        message = fetch_message(db, cursor.lastrowid)
        
    await manager.broadcast(channel_id, "message.created", message)
    return message
