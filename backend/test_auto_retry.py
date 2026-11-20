
import asyncio
import json
from datetime import datetime
from uuid import uuid4
from unittest.mock import patch

import webhooks
from database import SessionLocal
from models import Webhook, WebhookDelivery


async def fake_sleep(seconds):
    print(f"Simulated wait: {seconds} seconds")


async def fake_send_delivery(delivery, webhook, payload):
    delivery.attempt_count += 1
    delivery.last_attempt_at = datetime.now()

    if delivery.attempt_count < 3:
        delivery.status = "failed"
        delivery.response_status = "503"
        delivery.error_message = "Simulated temporary failure"
    else:
        delivery.status = "success"
        delivery.response_status = "200"
        delivery.error_message = None

    print(
        f"Attempt {delivery.attempt_count}: "
        f"{delivery.status}"
    )

    return delivery


async def run_test():
    db = SessionLocal()
    test_delivery_id = str(uuid4())

    try:
        webhook = db.query(Webhook).filter(
            Webhook.endpoint_url == "https://httpbin.org/post"
        ).first()

        if not webhook:
            print("No safe demo webhook found.")
            return

        test_delivery = WebhookDelivery(
            id=test_delivery_id,
            webhook_id=webhook.id,
            event_payload=json.dumps({
                "event_type": webhook.event_type,
                "data": {"test": "automatic-retry"}
            }, sort_keys=True),
            idempotency_key=None,
            attempt_count=1,
            max_attempts=3,
            status="failed",
            error_message="Simulated first failure",
            created_at=datetime.now()
        )

        db.add(test_delivery)
        db.commit()

        print("Starting automatic retry simulation...")

        with patch.object(
            webhooks.asyncio,
            "sleep",
            new=fake_sleep
        ), patch.object(
            webhooks,
            "send_delivery",
            new=fake_send_delivery
        ):
            await webhooks.auto_retry_delivery(test_delivery_id)

        db.expire_all()

        result = db.query(WebhookDelivery).filter(
            WebhookDelivery.id == test_delivery_id
        ).first()

        if result:
            print("\nFinal result:")
            print("Status:", result.status)
            print("Attempts:", result.attempt_count)

            if result.status == "success" and result.attempt_count == 3:
                print("AUTOMATIC RETRY TEST PASSED!")
            else:
                print("AUTOMATIC RETRY TEST FAILED!")

    finally:
        db.query(WebhookDelivery).filter(
            WebhookDelivery.id == test_delivery_id
        ).delete(synchronize_session=False)
        db.commit()
        db.close()
        print("Temporary test record cleaned up.")


if __name__ == "__main__":
    asyncio.run(run_test())
