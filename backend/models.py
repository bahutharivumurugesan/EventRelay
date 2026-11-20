
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey
from datetime import datetime
import secrets
from database import Base


def generate_webhook_secret():
    return secrets.token_urlsafe(32)


class Webhook(Base):
    __tablename__ = "webhooks"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    endpoint_url = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    secret_key = Column(
        String,
        nullable=True,
        default=generate_webhook_secret
    )
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.now)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id = Column(String, primary_key=True, index=True)
    webhook_id = Column(String, nullable=False, index=True)
    event_payload = Column(String, nullable=False)
    idempotency_key = Column(String, nullable=True, unique=True, index=True)
    attempt_count = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    last_attempt_at = Column(DateTime, nullable=True)
    status = Column(String, default="pending")
    response_status = Column(String, nullable=True)
    response_body = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"

    id = Column(String, primary_key=True, index=True)

    webhook_id = Column(
        String,
        ForeignKey("webhooks.id"),
        nullable=False,
        index=True
    )

    event_type = Column(String, nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        # Prevent duplicate subscriptions for the same event.
        # SQLite enforces this unique combination.
        __import__("sqlalchemy").UniqueConstraint(
            "webhook_id",
            "event_type",
            name="uq_webhook_event_subscription"
        ),
    )
