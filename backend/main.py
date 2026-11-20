
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
import time

from database import init_db
from webhooks import router

init_db()

app = FastAPI(
    title="EventBridge Lite API",
    description=(
        "A webhook delivery tracking system with "
        "idempotency, signature verification, "
        "automatic retry, event replay and rate limiting"
    ),
    version="1.3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# RATE LIMITING
# -----------------------------

RATE_LIMIT = 60
TIME_WINDOW = 60

request_records = {}


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Apply rate limiting only to API routes
    if not request.url.path.startswith("/api/"):
        return await call_next(request)

    client_ip = (
        request.client.host
        if request.client
        else "unknown"
    )

    current_time = time.monotonic()

    # Keep only requests inside the current time window
    timestamps = request_records.get(client_ip, [])

    timestamps = [
        timestamp
        for timestamp in timestamps
        if current_time - timestamp < TIME_WINDOW
    ]

    if len(timestamps) >= RATE_LIMIT:
        retry_after = max(
            1,
            int(TIME_WINDOW - (current_time - timestamps[0]))
        )

        request_records[client_ip] = timestamps

        return JSONResponse(
            status_code=429,
            content={
                "detail": "Rate limit exceeded. Please try again later.",
                "limit": RATE_LIMIT,
                "window_seconds": TIME_WINDOW
            },
            headers={
                "Retry-After": str(retry_after)
            }
        )

    timestamps.append(current_time)
    request_records[client_ip] = timestamps

    return await call_next(request)


app.include_router(router)


@app.get("/")
def home():
    return {
        "message": "Welcome to EventBridge Lite!",
        "status": "running",
        "version": "1.3.0"
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }
