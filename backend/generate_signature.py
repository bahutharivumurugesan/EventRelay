
import sqlite3
import json
import hmac
import hashlib

WEBHOOK_ID = "6eb04281-0028-4ef1-8808-b7b44edf21bb"

# Read the secret locally from the existing database.
connection = sqlite3.connect("eventbridge.db")

row = connection.execute(
    "SELECT secret_key, event_type FROM webhooks WHERE id = ?",
    (WEBHOOK_ID,)
).fetchone()

connection.close()

if not row or not row[0]:
    raise SystemExit("Webhook or secret key not found.")

secret_key, event_type = row

payload = {
    "event_type": event_type,
    "data": {
        "order_id": 303,
        "event": "order.created"
    }
}

payload_bytes = json.dumps(
    payload,
    sort_keys=True
).encode("utf-8")

signature = hmac.new(
    secret_key.encode("utf-8"),
    payload_bytes,
    hashlib.sha256
).hexdigest()

print("Signature:")
print("sha256=" + signature)
