
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///./eventbridge.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def init_db():
    """
    Create missing tables and safely migrate existing databases.
    Existing webhook and delivery records are preserved.
    """
    import models

    # Creates only missing tables, including webhook_subscriptions.
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    # Webhook signature migration
    if "webhooks" in tables:
        columns = [
            column["name"]
            for column in inspector.get_columns("webhooks")
        ]

        if "secret_key" not in columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE webhooks "
                        "ADD COLUMN secret_key VARCHAR"
                    )
                )

        from models import generate_webhook_secret

        with engine.begin() as connection:
            result = connection.execute(
                text(
                    "SELECT id FROM webhooks "
                    "WHERE secret_key IS NULL OR secret_key = ''"
                )
            )

            webhook_ids = [row[0] for row in result]

            for webhook_id in webhook_ids:
                connection.execute(
                    text(
                        "UPDATE webhooks SET secret_key = :secret "
                        "WHERE id = :webhook_id"
                    ),
                    {
                        "secret": generate_webhook_secret(),
                        "webhook_id": webhook_id
                    }
                )

    # Delivery migrations
    if "webhook_deliveries" in tables:
        columns = [
            column["name"]
            for column in inspector.get_columns(
                "webhook_deliveries"
            )
        ]

        migrations = {
            "idempotency_key": "VARCHAR",
            "attempt_count": "INTEGER NOT NULL DEFAULT 0",
            "max_attempts": "INTEGER NOT NULL DEFAULT 3",
            "last_attempt_at": "DATETIME"
        }

        for column_name, column_type in migrations.items():
            if column_name not in columns:
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            f"ALTER TABLE webhook_deliveries "
                            f"ADD COLUMN {column_name} {column_type}"
                        )
                    )

        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "ix_webhook_deliveries_idempotency_key "
                    "ON webhook_deliveries (idempotency_key)"
                )
            )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
