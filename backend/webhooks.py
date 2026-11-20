
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Header,
    BackgroundTasks
)
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from uuid import uuid4
from urllib.parse import urlparse

import asyncio
import httpx
import json
import hmac
import hashlib

from database import get_db, SessionLocal
from models import (
    Webhook,
    WebhookDelivery,
    WebhookSubscription
)


router = APIRouter()

MAX_ATTEMPTS = 3

RETRY_DELAYS = {
    1: 5,
    2: 15
}


# --------------------------------------------------
# REQUEST MODELS
# --------------------------------------------------

class WebhookRequest(BaseModel):
    name: str
    endpoint_url: HttpUrl
    event_type: str


class EventRequest(BaseModel):
    payload: dict


class SignatureVerifyRequest(BaseModel):
    payload: dict


class PublishEventRequest(BaseModel):
    event_type: str
    payload: dict


class SubscriptionRequest(BaseModel):
    event_type: str


# --------------------------------------------------
# ENDPOINT VALIDATION
# --------------------------------------------------

def validate_endpoint(endpoint_url: str):
    """Allow only the exact HTTPS httpbin.org test endpoint."""

    parsed_url = urlparse(str(endpoint_url))

    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname != "httpbin.org"
        or parsed_url.port not in (None, 443)
        or parsed_url.path != "/post"
        or parsed_url.query
        or parsed_url.fragment
        or parsed_url.username
        or parsed_url.password
    ):
        raise HTTPException(
            status_code=400,
            detail="For this demo, use exactly https://httpbin.org/post"
        )


# --------------------------------------------------
# SIGNATURE GENERATION AND VERIFICATION
# --------------------------------------------------

def generate_signature(
    secret_key: str,
    payload_bytes: bytes
) -> str:

    signature = hmac.new(
        secret_key.encode("utf-8"),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()

    return f"sha256={signature}"


def verify_signature(
    secret_key: str,
    payload_bytes: bytes,
    received_signature: str
) -> bool:

    expected_signature = generate_signature(
        secret_key,
        payload_bytes
    )

    return hmac.compare_digest(
        expected_signature,
        received_signature.strip()
    )


# --------------------------------------------------
# SEND DELIVERY
# --------------------------------------------------

async def send_delivery(delivery, webhook, payload):
    """Send one signed delivery attempt and update its status."""

    validate_endpoint(webhook.endpoint_url)

    delivery.attempt_count = (
        delivery.attempt_count or 0
    ) + 1

    delivery.last_attempt_at = datetime.now()
    delivery.status = "pending"
    delivery.response_status = None
    delivery.response_body = None
    delivery.error_message = None

    if not webhook.secret_key:
        delivery.status = "failed"
        delivery.error_message = "Webhook secret key is missing"
        return delivery

    try:
        serialized_payload = json.dumps(
            payload,
            sort_keys=True
        )

        payload_bytes = serialized_payload.encode("utf-8")

        signature = generate_signature(
            webhook.secret_key,
            payload_bytes
        )

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-Signature-Algorithm": "HMAC-SHA256"
        }

        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=False
        ) as client:

            response = await client.post(
                webhook.endpoint_url,
                content=payload_bytes,
                headers=headers
            )

        delivery.response_status = str(response.status_code)
        delivery.response_body = response.text[:2000]

        delivery.status = (
            "success" if response.is_success else "failed"
        )

        if not response.is_success:
            delivery.error_message = (
                f"HTTP {response.status_code}"
            )

    except httpx.RequestError as error:
        delivery.status = "failed"
        delivery.error_message = str(error)[:1000]

    return delivery


# --------------------------------------------------
# AUTOMATIC RETRY
# --------------------------------------------------

async def auto_retry_delivery(delivery_id: str):
    """
    Retry failed deliveries automatically.

    Attempt 1: Initial delivery
    Attempt 2: After 5 seconds
    Attempt 3: After another 15 seconds
    """

    while True:

        db = SessionLocal()

        try:
            delivery = db.query(WebhookDelivery).filter(
                WebhookDelivery.id == delivery_id
            ).first()

            if not delivery:
                return

            if delivery.status != "failed":
                return

            current_attempt = delivery.attempt_count or 0
            max_attempts = delivery.max_attempts or MAX_ATTEMPTS

            if current_attempt >= max_attempts:
                return

            delay = RETRY_DELAYS.get(current_attempt)

            if delay is None:
                return

        finally:
            db.close()

        await asyncio.sleep(delay)

        db = SessionLocal()

        try:
            delivery = db.query(WebhookDelivery).filter(
                WebhookDelivery.id == delivery_id
            ).first()

            if not delivery or delivery.status != "failed":
                return

            current_attempt = delivery.attempt_count or 0
            max_attempts = delivery.max_attempts or MAX_ATTEMPTS

            if current_attempt >= max_attempts:
                return

            webhook = db.query(Webhook).filter(
                Webhook.id == delivery.webhook_id
            ).first()

            if not webhook:
                delivery.error_message = (
                    "Associated webhook not found"
                )
                db.commit()
                return

            try:
                payload = json.loads(delivery.event_payload)

            except (json.JSONDecodeError, TypeError):
                delivery.error_message = (
                    "Stored delivery payload is invalid"
                )
                db.commit()
                return

            if not isinstance(payload, dict):
                delivery.error_message = (
                    "Stored delivery payload must be an object"
                )
                db.commit()
                return

            await send_delivery(
                delivery,
                webhook,
                payload
            )

            db.commit()

            if delivery.status == "success":
                return

        except Exception:
            db.rollback()
            raise

        finally:
            db.close()


# --------------------------------------------------
# DELIVERY RESPONSE
# --------------------------------------------------

def delivery_response(delivery, duplicate=False):

    return {
        "message": (
            "Duplicate request detected. Existing delivery returned."
            if duplicate
            else "Webhook delivery completed"
        ),
        "duplicate": duplicate,
        "delivery_id": delivery.id,
        "idempotency_key": delivery.idempotency_key,
        "status": delivery.status,
        "response_status": delivery.response_status,
        "attempt_count": delivery.attempt_count,
        "max_attempts": delivery.max_attempts,
        "error": delivery.error_message
    }


# --------------------------------------------------
# CREATE WEBHOOK
# --------------------------------------------------

@router.post("/api/webhooks")
def create_webhook(
    data: WebhookRequest,
    db: Session = Depends(get_db)
):

    webhook = Webhook(
        id=str(uuid4()),
        name=data.name,
        endpoint_url=str(data.endpoint_url),
        event_type=data.event_type,
        status="active",
        created_at=datetime.now()
    )

    db.add(webhook)
    db.flush()

    # Every new webhook automatically subscribes to
    # its original event type.
    subscription = WebhookSubscription(
        id=str(uuid4()),
        webhook_id=webhook.id,
        event_type=data.event_type.strip(),
        created_at=datetime.now()
    )

    db.add(subscription)
    db.commit()
    db.refresh(webhook)

    return {
        "message": "Webhook created successfully",
        "webhook": {
            "id": webhook.id,
            "name": webhook.name,
            "endpoint_url": webhook.endpoint_url,
            "event_type": webhook.event_type,
            "status": webhook.status,
            "created_at": webhook.created_at.isoformat(),
            "secret_key": webhook.secret_key
        },
        "secret_notice": (
            "Store this secret securely. It is returned only "
            "when the webhook is created."
        ),
        "subscription": {
            "event_type": subscription.event_type
        }
    }


# --------------------------------------------------
# GET WEBHOOKS
# --------------------------------------------------

@router.get("/api/webhooks")
def get_webhooks(
    db: Session = Depends(get_db)
):

    webhooks = db.query(Webhook).all()

    return {
        "total": len(webhooks),
        "webhooks": [
            {
                "id": webhook.id,
                "name": webhook.name,
                "endpoint_url": webhook.endpoint_url,
                "event_type": webhook.event_type,
                "status": webhook.status,
                "created_at": webhook.created_at.isoformat()
            }
            for webhook in webhooks
        ]
    }


# --------------------------------------------------
# DIRECT WEBHOOK DELIVERY WITH IDEMPOTENCY
# --------------------------------------------------

@router.post("/api/webhooks/{webhook_id}/deliver")
async def deliver_webhook(
    webhook_id: str,
    data: EventRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key"
    ),
    db: Session = Depends(get_db)
):

    webhook = db.query(Webhook).filter(
        Webhook.id == webhook_id
    ).first()

    if not webhook:
        raise HTTPException(
            status_code=404,
            detail="Webhook not found"
        )

    validate_endpoint(webhook.endpoint_url)

    if not webhook.secret_key:
        raise HTTPException(
            status_code=500,
            detail="Webhook secret key is missing"
        )

    if idempotency_key is not None:

        idempotency_key = idempotency_key.strip()

        if not idempotency_key or len(idempotency_key) > 255:
            raise HTTPException(
                status_code=400,
                detail="Idempotency-Key must contain 1 to 255 characters"
            )

    payload = {
        "event_type": webhook.event_type,
        "data": data.payload
    }

    serialized_payload = json.dumps(
        payload,
        sort_keys=True
    )

    if idempotency_key is not None:

        existing_delivery = db.query(WebhookDelivery).filter(
            WebhookDelivery.idempotency_key == idempotency_key
        ).first()

        if existing_delivery:

            if (
                existing_delivery.webhook_id != webhook.id
                or existing_delivery.event_payload != serialized_payload
            ):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "This Idempotency-Key was already used "
                        "with a different webhook or payload."
                    )
                )

            return delivery_response(
                existing_delivery,
                duplicate=True
            )

    delivery = WebhookDelivery(
        id=str(uuid4()),
        webhook_id=webhook.id,
        event_payload=serialized_payload,
        idempotency_key=idempotency_key,
        attempt_count=0,
        max_attempts=MAX_ATTEMPTS,
        status="pending",
        created_at=datetime.now()
    )

    db.add(delivery)

    try:
        db.commit()

    except IntegrityError:
        db.rollback()

        if idempotency_key is None:
            raise HTTPException(
                status_code=500,
                detail="Could not create delivery"
            )

        existing_delivery = db.query(WebhookDelivery).filter(
            WebhookDelivery.idempotency_key == idempotency_key
        ).first()

        if not existing_delivery:
            raise HTTPException(
                status_code=409,
                detail="Idempotency conflict. Please use a new key."
            )

        if (
            existing_delivery.webhook_id != webhook.id
            or existing_delivery.event_payload != serialized_payload
        ):
            raise HTTPException(
                status_code=409,
                detail="Idempotency key was already used for another event."
            )

        return delivery_response(
            existing_delivery,
            duplicate=True
        )

    db.refresh(delivery)

    await send_delivery(
        delivery,
        webhook,
        payload
    )

    db.commit()
    db.refresh(delivery)

    if (
        delivery.status == "failed"
        and delivery.attempt_count < delivery.max_attempts
    ):
        background_tasks.add_task(
            auto_retry_delivery,
            delivery.id
        )

    return delivery_response(delivery)


# --------------------------------------------------
# MANUAL RETRY
# --------------------------------------------------

@router.post("/api/deliveries/{delivery_id}/retry")
async def retry_delivery(
    delivery_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):

    delivery = db.query(WebhookDelivery).filter(
        WebhookDelivery.id == delivery_id
    ).first()

    if not delivery:
        raise HTTPException(
            status_code=404,
            detail="Delivery not found"
        )

    if delivery.status != "failed":
        raise HTTPException(
            status_code=400,
            detail="Only failed deliveries can be retried"
        )

    webhook = db.query(Webhook).filter(
        Webhook.id == delivery.webhook_id
    ).first()

    if not webhook:
        raise HTTPException(
            status_code=404,
            detail="Associated webhook not found"
        )

    validate_endpoint(webhook.endpoint_url)

    try:
        payload = json.loads(delivery.event_payload)

    except (json.JSONDecodeError, TypeError):
        raise HTTPException(
            status_code=400,
            detail="Stored delivery payload is invalid"
        )

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400,
            detail="Stored delivery payload must be an object"
        )

    delivery.attempt_count = 0
    delivery.max_attempts = MAX_ATTEMPTS
    delivery.status = "pending"
    delivery.response_status = None
    delivery.response_body = None
    delivery.error_message = None

    db.commit()

    await send_delivery(
        delivery,
        webhook,
        payload
    )

    db.commit()
    db.refresh(delivery)

    if (
        delivery.status == "failed"
        and delivery.attempt_count < delivery.max_attempts
    ):
        background_tasks.add_task(
            auto_retry_delivery,
            delivery.id
        )

    return {
        "message": "Manual retry completed",
        "delivery_id": delivery.id,
        "status": delivery.status,
        "attempt_count": delivery.attempt_count,
        "max_attempts": delivery.max_attempts,
        "response_status": delivery.response_status,
        "error": delivery.error_message
    }


# --------------------------------------------------
# GET ALL DELIVERIES
# --------------------------------------------------

@router.get("/api/deliveries")
def get_deliveries(
    db: Session = Depends(get_db)
):

    deliveries = (
        db.query(WebhookDelivery)
        .order_by(WebhookDelivery.created_at.desc())
        .all()
    )

    return {
        "total": len(deliveries),
        "deliveries": [
            {
                "id": item.id,
                "webhook_id": item.webhook_id,
                "idempotency_key": item.idempotency_key,
                "status": item.status,
                "response_status": item.response_status,
                "error_message": item.error_message,
                "attempt_count": item.attempt_count,
                "max_attempts": item.max_attempts,
                "last_attempt_at": (
                    item.last_attempt_at.isoformat()
                    if item.last_attempt_at else None
                ),
                "created_at": item.created_at.isoformat()
            }
            for item in deliveries
        ]
    }


# --------------------------------------------------
# GET DELIVERY DETAILS
# --------------------------------------------------

@router.get("/api/deliveries/{delivery_id}")
def get_delivery_details(
    delivery_id: str,
    db: Session = Depends(get_db)
):

    delivery = db.query(WebhookDelivery).filter(
        WebhookDelivery.id == delivery_id
    ).first()

    if not delivery:
        raise HTTPException(
            status_code=404,
            detail="Delivery not found"
        )

    return {
        "delivery_id": delivery.id,
        "webhook_id": delivery.webhook_id,
        "status": delivery.status,
        "response_status": delivery.response_status,
        "response_body": delivery.response_body,
        "error_message": delivery.error_message,
        "idempotency_key": delivery.idempotency_key,
        "attempt_count": delivery.attempt_count,
        "max_attempts": delivery.max_attempts,
        "last_attempt_at": (
            delivery.last_attempt_at.isoformat()
            if delivery.last_attempt_at else None
        ),
        "created_at": delivery.created_at.isoformat()
    }


# --------------------------------------------------
# VERIFY WEBHOOK SIGNATURE
# --------------------------------------------------

@router.post("/api/webhooks/{webhook_id}/verify-signature")
def verify_webhook_signature(
    webhook_id: str,
    data: SignatureVerifyRequest,
    signature: str | None = Header(
        default=None,
        alias="X-Webhook-Signature"
    ),
    db: Session = Depends(get_db)
):

    webhook = db.query(Webhook).filter(
        Webhook.id == webhook_id
    ).first()

    if not webhook:
        raise HTTPException(
            status_code=404,
            detail="Webhook not found"
        )

    if not webhook.secret_key:
        raise HTTPException(
            status_code=500,
            detail="Webhook secret key is missing"
        )

    if not signature:
        raise HTTPException(
            status_code=400,
            detail="X-Webhook-Signature header is required"
        )

    payload = {
        "event_type": webhook.event_type,
        "data": data.payload
    }

    payload_bytes = json.dumps(
        payload,
        sort_keys=True
    ).encode("utf-8")

    is_valid = verify_signature(
        webhook.secret_key,
        payload_bytes,
        signature
    )

    return {
        "valid": is_valid,
        "message": (
            "Signature verified successfully"
            if is_valid
            else "Invalid signature"
        )
    }


# --------------------------------------------------
# EVENT REPLAY
# --------------------------------------------------

@router.post("/api/deliveries/{delivery_id}/replay")
async def replay_delivery(
    delivery_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):

    original_delivery = db.query(WebhookDelivery).filter(
        WebhookDelivery.id == delivery_id
    ).first()

    if not original_delivery:
        raise HTTPException(
            status_code=404,
            detail="Original delivery not found"
        )

    webhook = db.query(Webhook).filter(
        Webhook.id == original_delivery.webhook_id
    ).first()

    if not webhook:
        raise HTTPException(
            status_code=404,
            detail="Associated webhook not found"
        )

    validate_endpoint(webhook.endpoint_url)

    if not webhook.secret_key:
        raise HTTPException(
            status_code=500,
            detail="Webhook secret key is missing"
        )

    try:
        payload = json.loads(original_delivery.event_payload)

    except (json.JSONDecodeError, TypeError):
        raise HTTPException(
            status_code=400,
            detail="Original event payload is invalid"
        )

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400,
            detail="Original event payload must be an object"
        )

    replay = WebhookDelivery(
        id=str(uuid4()),
        webhook_id=webhook.id,
        event_payload=original_delivery.event_payload,
        idempotency_key=None,
        attempt_count=0,
        max_attempts=MAX_ATTEMPTS,
        status="pending",
        created_at=datetime.now()
    )

    db.add(replay)
    db.commit()
    db.refresh(replay)

    await send_delivery(
        replay,
        webhook,
        payload
    )

    db.commit()
    db.refresh(replay)

    if (
        replay.status == "failed"
        and replay.attempt_count < replay.max_attempts
    ):
        background_tasks.add_task(
            auto_retry_delivery,
            replay.id
        )

    return {
        "message": "Event replay completed",
        "original_delivery_id": original_delivery.id,
        "replay_delivery_id": replay.id,
        "status": replay.status,
        "attempt_count": replay.attempt_count,
        "max_attempts": replay.max_attempts,
        "response_status": replay.response_status
    }


# --------------------------------------------------
# FEATURE 15: SUBSCRIBE TO AN EVENT
# --------------------------------------------------

@router.post("/api/webhooks/{webhook_id}/subscriptions")
def subscribe_webhook(
    webhook_id: str,
    data: SubscriptionRequest,
    db: Session = Depends(get_db)
):

    event_type = data.event_type.strip()

    if not event_type or len(event_type) > 100:
        raise HTTPException(
            status_code=400,
            detail="event_type must contain 1 to 100 characters"
        )

    webhook = db.query(Webhook).filter(
        Webhook.id == webhook_id
    ).first()

    if not webhook:
        raise HTTPException(
            status_code=404,
            detail="Webhook not found"
        )

    existing = db.query(WebhookSubscription).filter(
        WebhookSubscription.webhook_id == webhook_id,
        WebhookSubscription.event_type == event_type
    ).first()

    if existing:
        return {
            "message": "Already subscribed",
            "webhook_id": webhook_id,
            "event_type": event_type
        }

    subscription = WebhookSubscription(
        id=str(uuid4()),
        webhook_id=webhook_id,
        event_type=event_type,
        created_at=datetime.now()
    )

    db.add(subscription)

    try:
        db.commit()
        db.refresh(subscription)

    except IntegrityError:
        db.rollback()

        return {
            "message": "Already subscribed",
            "webhook_id": webhook_id,
            "event_type": event_type
        }

    return {
        "message": "Subscription created successfully",
        "subscription_id": subscription.id,
        "webhook_id": webhook_id,
        "event_type": event_type
    }


# --------------------------------------------------
# FEATURE 15: UNSUBSCRIBE FROM AN EVENT
# --------------------------------------------------

@router.delete(
    "/api/webhooks/{webhook_id}/subscriptions/{event_type}"
)
def unsubscribe_webhook(
    webhook_id: str,
    event_type: str,
    db: Session = Depends(get_db)
):

    webhook = db.query(Webhook).filter(
        Webhook.id == webhook_id
    ).first()

    if not webhook:
        raise HTTPException(
            status_code=404,
            detail="Webhook not found"
        )

    subscription = db.query(WebhookSubscription).filter(
        WebhookSubscription.webhook_id == webhook_id,
        WebhookSubscription.event_type == event_type
    ).first()

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found"
        )

    db.delete(subscription)
    db.commit()

    return {
        "message": "Unsubscribed successfully",
        "webhook_id": webhook_id,
        "event_type": event_type
    }


# --------------------------------------------------
# FEATURE 15: GET WEBHOOK SUBSCRIPTIONS
# --------------------------------------------------

@router.get("/api/webhooks/{webhook_id}/subscriptions")
def get_webhook_subscriptions(
    webhook_id: str,
    db: Session = Depends(get_db)
):

    webhook = db.query(Webhook).filter(
        Webhook.id == webhook_id
    ).first()

    if not webhook:
        raise HTTPException(
            status_code=404,
            detail="Webhook not found"
        )

    subscriptions = db.query(WebhookSubscription).filter(
        WebhookSubscription.webhook_id == webhook_id
    ).order_by(
        WebhookSubscription.created_at.asc()
    ).all()

    return {
        "webhook_id": webhook_id,
        "webhook_name": webhook.name,
        "total_subscriptions": len(subscriptions),
        "subscriptions": [
            {
                "id": subscription.id,
                "event_type": subscription.event_type,
                "created_at": subscription.created_at.isoformat()
            }
            for subscription in subscriptions
        ]
    }


# --------------------------------------------------
# FEATURE 14 + 15: EVENT PUBLISHING
# --------------------------------------------------

@router.post("/api/events/publish")
async def publish_event(
    data: PublishEventRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Publish an event to active webhooks subscribed
    to the supplied event type.

    Existing webhooks without subscription records
    retain their original event_type behavior.
    """

    event_type = data.event_type.strip()

    if not event_type or len(event_type) > 100:
        raise HTTPException(
            status_code=400,
            detail="event_type must contain 1 to 100 characters"
        )

    # Find webhooks with an explicit subscription.
    matching_subscriptions = (
        db.query(WebhookSubscription)
        .join(
            Webhook,
            Webhook.id == WebhookSubscription.webhook_id
        )
        .filter(
            WebhookSubscription.event_type == event_type,
            Webhook.status == "active"
        )
        .all()
    )

    matching_webhooks = []
    matched_ids = set()

    for subscription in matching_subscriptions:

        webhook = db.query(Webhook).filter(
            Webhook.id == subscription.webhook_id
        ).first()

        if webhook and webhook.id not in matched_ids:
            matching_webhooks.append(webhook)
            matched_ids.add(webhook.id)

    # Backward compatibility:
    # Existing webhooks with no subscription rows still
    # receive their original event_type.
    all_subscription_webhook_ids = {
        row[0]
        for row in db.query(
            WebhookSubscription.webhook_id
        ).distinct().all()
    }

    legacy_webhooks = db.query(Webhook).filter(
        Webhook.event_type == event_type,
        Webhook.status == "active"
    ).all()

    for webhook in legacy_webhooks:

        if (
            webhook.id not in all_subscription_webhook_ids
            and webhook.id not in matched_ids
        ):
            matching_webhooks.append(webhook)
            matched_ids.add(webhook.id)

    if not matching_webhooks:
        return {
            "message": "No active webhooks are subscribed to this event",
            "event_type": event_type,
            "total_webhooks": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "deliveries": []
        }

    event_payload = {
        "event_type": event_type,
        "data": data.payload
    }

    serialized_payload = json.dumps(
        event_payload,
        sort_keys=True
    )

    results = []
    successful = 0
    failed = 0
    skipped = 0

    for webhook in matching_webhooks:

        try:
            validate_endpoint(webhook.endpoint_url)

        except HTTPException:
            skipped += 1

            results.append({
                "webhook_id": webhook.id,
                "webhook_name": webhook.name,
                "status": "skipped",
                "error": (
                    "Webhook endpoint is not an allowed demo endpoint"
                )
            })

            continue

        if not webhook.secret_key:
            skipped += 1

            results.append({
                "webhook_id": webhook.id,
                "webhook_name": webhook.name,
                "status": "skipped",
                "error": "Webhook secret key is missing"
            })

            continue

        delivery = WebhookDelivery(
            id=str(uuid4()),
            webhook_id=webhook.id,
            event_payload=serialized_payload,
            idempotency_key=None,
            attempt_count=0,
            max_attempts=MAX_ATTEMPTS,
            status="pending",
            created_at=datetime.now()
        )

        db.add(delivery)

        try:
            db.commit()
            db.refresh(delivery)

        except IntegrityError:
            db.rollback()
            failed += 1

            results.append({
                "webhook_id": webhook.id,
                "webhook_name": webhook.name,
                "status": "failed",
                "error": "Could not create delivery record"
            })

            continue

        await send_delivery(
            delivery,
            webhook,
            event_payload
        )

        db.commit()
        db.refresh(delivery)

        if delivery.status == "success":
            successful += 1
        else:
            failed += 1

        if (
            delivery.status == "failed"
            and delivery.attempt_count < delivery.max_attempts
        ):
            background_tasks.add_task(
                auto_retry_delivery,
                delivery.id
            )

        results.append({
            "webhook_id": webhook.id,
            "webhook_name": webhook.name,
            "delivery_id": delivery.id,
            "status": delivery.status,
            "response_status": delivery.response_status,
            "attempt_count": delivery.attempt_count,
            "max_attempts": delivery.max_attempts,
            "error": delivery.error_message
        })

    return {
        "message": "Event publishing completed",
        "event_type": event_type,
        "total_webhooks": len(matching_webhooks),
        "successful": successful,
        "failed": failed,
        "skipped": skipped,
        "deliveries": results
    }
