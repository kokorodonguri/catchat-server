import sys
from pathlib import Path
import os
import atexit
import shutil

# Add the catchat-server directory to system path
sys.path.append(str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient


def cleanup_test_files():
    for ext in ["", "-wal", "-shm"]:
        path = Path(f"test_guild.db{ext}")
        if path.exists():
            path.unlink()
    shutil.rmtree("test_uploads", ignore_errors=True)


# Set environment variables before importing main so module-level settings use test values.
cleanup_test_files()
atexit.register(cleanup_test_files)
os.environ["CATCHAT_SERVER_DATABASE_PATH"] = "test_guild.db"
os.environ["CATCHAT_SERVER_UPLOAD_DIR"] = "test_uploads"
os.environ["CATCHAT_SERVER_SECRET"] = "test-secret-key-12345"

import main  # noqa: E402

client = TestClient(main.app)

def test_flow():
    print("Starting catChat Server verification flow...")
    
    # 1. Initialize DB
    main.initialize_database()
    
    # Validate DB table creation
    with main.connect() as db:
        tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        print("  Created tables in test DB:", tables)
        assert "server_settings" in tables
        
        # Check initial channel count (should contain only 'general' which is automatically created)
        channel_count = db.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
        print(f"  Initial channel count: {channel_count}")
        assert channel_count == 1

        db.execute(
            """INSERT INTO members (id, username, display_name, role, created_at, last_seen_at)
               VALUES ('owner-user', 'owner', 'Owner', 'owner', 0, 0)
               ON CONFLICT(id) DO UPDATE SET role = 'owner'"""
        )
    
    # Authenticate header
    headers = {
        "Authorization": f"Bearer {main.SERVER_SECRET}",
        "X-Catchat-Hub-User-Id": "owner-user",
    }
    
    # 2. Get initial settings (Default MAX_CHANNELS is 100)
    resp = client.get("/api/server/settings", headers=headers)
    print("  GET /api/server/settings (Initial):", resp.json())
    assert resp.status_code == 200
    assert resp.json()["max_channels"] == 100
    
    # 3. Change max_channels to 1 (Rejecting further creations since 'general' already exists)
    resp = client.patch("/api/server/settings", headers=headers, json={"max_channels": 1})
    print("  PATCH /api/server/settings (Set to 1):", resp.json())
    assert resp.status_code == 200
    assert resp.json()["max_channels"] == 1
    
    # Verify via server info
    resp = client.get("/api/server/info")
    print("  GET /api/server/info max_channels:", resp.json()["limits"]["max_channels"])
    assert resp.json()["limits"]["max_channels"] == 1
    
    # 4. Attempt to create a new channel (Expected to fail with 403)
    resp = client.post("/api/channels", headers=headers, json={"name": "new-test-channel", "topic": "should fail"})
    print("  POST /api/channels (Expected 403 failure):", resp.status_code, resp.json())
    assert resp.status_code == 403
    assert "Maximum channel count reached" in resp.json()["detail"]
    
    # 5. Change max_channels to 5
    resp = client.patch("/api/server/settings", headers=headers, json={"max_channels": 5})
    print("  PATCH /api/server/settings (Set to 5):", resp.json())
    assert resp.status_code == 200
    assert resp.json()["max_channels"] == 5
    
    # Verify server info sync
    resp = client.get("/api/server/info")
    print("  GET /api/server/info max_channels (Updated):", resp.json()["limits"]["max_channels"])
    assert resp.json()["limits"]["max_channels"] == 5
    
    # 6. Create a new channel (Expected to succeed)
    resp = client.post("/api/channels", headers=headers, json={"name": "new-test-channel", "topic": "should succeed"})
    print("  POST /api/channels (Expected 201 success):", resp.status_code, resp.json())
    assert resp.status_code == 201
    assert resp.json()["name"] == "new-test-channel"
    channel_id = resp.json()["id"]

    # 7. Management APIs require the Hub user id header.
    secret_only_headers = {"Authorization": f"Bearer {main.SERVER_SECRET}"}
    resp = client.post("/api/channels", headers=secret_only_headers, json={"name": "missing-user"})
    print("  POST /api/channels without user header (Expected 403):", resp.status_code, resp.json())
    assert resp.status_code == 403

    # 8. Webhook management requires MANAGE_WEBHOOKS; owner is allowed.
    resp = client.post("/api/webhooks", headers=headers, json={"channel_id": channel_id, "name": "Deploy Bot"})
    print("  POST /api/webhooks as owner (Expected 201):", resp.status_code, resp.json())
    assert resp.status_code == 201
    webhook_id = resp.json()["id"]

    resp = client.delete(f"/api/webhooks/{webhook_id}", headers=headers)
    print("  DELETE /api/webhooks/{id} as owner (Expected 200):", resp.status_code, resp.json())
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # 9. Message edits are allowed for the author and denied for unrelated members.
    resp = client.post(
        f"/api/channels/{channel_id}/messages",
        headers=secret_only_headers,
        json={
            "hub_user_id": "alice",
            "username": "alice",
            "display_name": "Alice",
            "content": "hello",
        },
    )
    print("  POST /api/channels/{id}/messages as alice (Expected 201):", resp.status_code, resp.json())
    assert resp.status_code == 201
    message_id = resp.json()["id"]

    alice_headers = {
        "Authorization": f"Bearer {main.SERVER_SECRET}",
        "X-Catchat-Hub-User-Id": "alice",
    }
    resp = client.patch(f"/api/messages/{message_id}", headers=alice_headers, json={"content": "edited"})
    print("  PATCH /api/messages/{id} as author (Expected 200):", resp.status_code, resp.json())
    assert resp.status_code == 200
    assert resp.json()["content"] == "edited"

    other_headers = {
        "Authorization": f"Bearer {main.SERVER_SECRET}",
        "X-Catchat-Hub-User-Id": "bob",
    }
    resp = client.patch(f"/api/messages/{message_id}", headers=other_headers, json={"content": "blocked"})
    print("  PATCH /api/messages/{id} as unrelated user (Expected 403):", resp.status_code, resp.json())
    assert resp.status_code == 403
    
    # 10. Check persistence after a fresh connection re-open (Re-query database via helper)
    with main.connect() as db:
        db_max_channels = main.get_current_max_channels(db)
        print("  Re-opened DB connection check, max_channels:", db_max_channels)
        assert db_max_channels == 5
        
    print("\n--- ALL TESTS COMPLETED SUCCESSFULLY! Catchat server functions perfectly. ---")

if __name__ == "__main__":
    try:
        test_flow()
    finally:
        cleanup_test_files()
