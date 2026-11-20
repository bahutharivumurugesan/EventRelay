# EventBridge Lite

**A Webhook Management and Event Delivery Platform**

Built with FastAPI, React, TypeScript, and SQLite.

---

## Overview

EventBridge Lite is a centralized webhook management platform designed to simplify event communication between applications.

It enables developers to create and manage webhook endpoints, publish events, configure event subscriptions, monitor delivery attempts, and handle failed deliveries through retry and replay mechanisms.

The platform combines a modern dashboard with a REST API to provide a structured and developer-friendly webhook management experience.

## Features

| Feature | Description |
|---|---|
| Webhook Management | Create and manage webhook endpoints. |
| Test Delivery | Trigger test webhook requests. |
| Delivery Monitoring | Track delivery status, response codes, and attempts. |
| Automatic Retry | Retry failed webhook deliveries. |
| Event Replay | Replay previously processed events. |
| HMAC Signature Verification | Verify webhook message authenticity. |
| Rate Limiting | Control API request frequency. |
| Event Publishing | Publish events through a centralized API. |
| Subscription Management | Subscribe and unsubscribe from event types. |
| Analytics Dashboard | Monitor delivery statistics and success rates. |
| CSV Export | Export delivery records for reporting. |

## Architecture

```text
                  EventBridge Lite
                         |
              +----------+----------+
              |                     |
          Frontend                Backend
              |                     |
       React + TypeScript         FastAPI
              |                     |
        Dashboard UI           REST API
                                    |
                             Webhook Engine
                                    |
              +---------------------+------------------+
              |          |          |         |         |
           Delivery    Retry     Event     Signature  Rate
           Tracking   Handling  Publishing Verification Limiting
              |          |          |         |         |
              +----------+----------+---------+---------+
                                    |
                              SQLite Database
```

## Technology Stack

### Frontend
- React
- TypeScript
- Vite
- CSS
- Lucide React

### Backend
- Python
- FastAPI
- SQLAlchemy
- HTTPX

### Database
- SQLite

## Project Structure

```text
eventbridge-lite/
│
├── backend/
│   ├── main.py
│   ├── models.py
│   ├── database.py
│   ├── webhooks.py
│   └── requirements.txt
│
├── frontend/
│   ├── public/
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
│
├── docs/
│   └── screenshots/
│
├── .gitignore
└── README.md
```

## Installation and Setup

### Prerequisites

- Python 3.13 or later
- Node.js and npm
- Git

### 1. Clone the Repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd eventbridge-lite
```

### 2. Backend Setup

```powershell
cd backend
python -m venv venv
```

Install dependencies:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Start the backend:

```powershell
.\venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Backend URL: `http://127.0.0.1:8000`

API Documentation: `http://127.0.0.1:8000/docs`

### 3. Frontend Setup

Open a second terminal:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open the local development URL displayed in the terminal.

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Check backend health |
| POST | `/api/events/publish` | Publish an event |
| POST | `/api/webhooks/{webhook_id}/subscriptions` | Create an event subscription |
| GET | `/api/webhooks/{webhook_id}/subscriptions` | Retrieve subscriptions |
| DELETE | `/api/webhooks/{webhook_id}/subscriptions/{event_type}` | Remove a subscription |

For the complete API reference, visit `/docs` while the backend is running.

## Security Considerations

- Never commit credentials, API keys, or secret values.
- Keep environment variables in local configuration files.
- Use HTTPS for production webhook endpoints.
- Validate webhook destinations before sending requests.
- Verify webhook signatures before trusting incoming messages.
- Use persistent background job processing for production retry workflows.

## Future Improvements

- Persistent background job processing
- Authentication and role-based access control
- Advanced monitoring and observability
- Additional webhook integrations
- Production deployment support

## License

A license has not yet been selected. Add an appropriate license before distributing this project publicly.

---

**EventBridge Lite**  
A developer-focused platform for managing webhooks and event-driven communication.