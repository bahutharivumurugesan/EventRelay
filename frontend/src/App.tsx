
import { useEffect, useState, type FormEvent } from "react";
import {
  Activity,
  Plus,
  RefreshCw,
  Send,
  Webhook,
  CheckCircle2,
  XCircle,
  Search,
  Filter,
  Eye,
  Copy,
  X,
  Download,
  BarChart3,
  TrendingUp,
  Trash2,
} from "lucide-react";
import "./App.css";

const API = "http://127.0.0.1:8000";
const SAFE_DEMO_ENDPOINT = "https://httpbin.org/post";
const ITEMS_PER_PAGE = 10;

type WebhookItem = {
  id: string;
  name: string;
  endpoint_url: string;
  event_type: string;
  status: string;
  created_at?: string;
};

type Delivery = {
  id: string;
  webhook_id: string;
  status: string;
  response_status: string | null;
  error_message?: string | null;
  created_at: string;
  attempt_count?: number;
  max_attempts?: number;
  last_attempt_at?: string | null;
  idempotency_key?: string | null;
};

type WebhookSubscription = {
  id: string;
  event_type: string;
  created_at?: string;
};

function App() {
  const [webhooks, setWebhooks] = useState<WebhookItem[]>([]);
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);

  const [name, setName] = useState("");
  const [endpoint, setEndpoint] = useState(SAFE_DEMO_ENDPOINT);
  const [eventType, setEventType] = useState("order.created");

  const [searchTerm, setSearchTerm] = useState("");
  const [eventFilter, setEventFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  const [currentPage, setCurrentPage] = useState(1);

  const [selectedWebhook, setSelectedWebhook] =
    useState<WebhookItem | null>(null);

  const [selectedDelivery, setSelectedDelivery] =
    useState<Delivery | null>(null);

  const [copiedItem, setCopiedItem] = useState("");
  const [loading, setLoading] = useState(false);
  const [retryingDeliveryId, setRetryingDeliveryId] = useState("");
  const [testingWebhookId, setTestingWebhookId] = useState("");

  const [message, setMessage] = useState("");

  const [subscriptions, setSubscriptions] = useState<
    WebhookSubscription[]
  >([]);

  const [subscriptionEventType, setSubscriptionEventType] =
    useState("");

  const [subscriptionLoading, setSubscriptionLoading] =
    useState(false);

  const [subscriptionActionLoading, setSubscriptionActionLoading] =
    useState(false);

  const [subscriptionMessage, setSubscriptionMessage] =
    useState("");

  // LOAD DASHBOARD DATA

  const loadData = async () => {
    setLoading(true);

    try {
      const [webhookResponse, deliveryResponse] = await Promise.all([
        fetch(`${API}/api/webhooks`),
        fetch(`${API}/api/deliveries`),
      ]);

      if (!webhookResponse.ok || !deliveryResponse.ok) {
        throw new Error("Unable to load dashboard data.");
      }

      const webhookData = await webhookResponse.json();
      const deliveryData = await deliveryResponse.json();

      setWebhooks(webhookData.webhooks || []);
      setDeliveries(deliveryData.deliveries || []);
    } catch (error) {
      console.error("Dashboard loading error:", error);

      setMessage(
        "Backend connection failed. Please check whether FastAPI is running."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // LOAD SUBSCRIPTIONS WHEN WEBHOOK DETAILS OPENS

  useEffect(() => {
    if (!selectedWebhook) {
      setSubscriptions([]);
      setSubscriptionMessage("");
      return;
    }

    let cancelled = false;

    const fetchSubscriptions = async () => {
      setSubscriptionLoading(true);
      setSubscriptionMessage("");

      try {
        const response = await fetch(
          `${API}/api/webhooks/${selectedWebhook.id}/subscriptions`
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            data.detail || "Unable to load subscriptions."
          );
        }

        if (!cancelled) {
          setSubscriptions(data.subscriptions || []);
        }
      } catch (error) {
        if (!cancelled) {
          setSubscriptionMessage(
            error instanceof Error
              ? error.message
              : "Failed to load subscriptions."
          );
        }
      } finally {
        if (!cancelled) {
          setSubscriptionLoading(false);
        }
      }
    };

    fetchSubscriptions();

    return () => {
      cancelled = true;
    };
  }, [selectedWebhook]);

  // CREATE WEBHOOK

  const createWebhook = async (
    e: FormEvent<HTMLFormElement>
  ) => {
    e.preventDefault();

    if (!name.trim()) {
      setMessage("Please enter a webhook name.");
      return;
    }

    if (endpoint.trim() !== SAFE_DEMO_ENDPOINT) {
      setMessage(
        "For this demo, only the approved HTTPS endpoint is allowed."
      );
      return;
    }

    try {
      setLoading(true);

      const response = await fetch(`${API}/api/webhooks`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: name.trim(),
          endpoint_url: endpoint.trim(),
          event_type: eventType,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Webhook creation failed."
        );
      }

      setMessage("Webhook created successfully!");

      setName("");
      setEndpoint(SAFE_DEMO_ENDPOINT);
      setEventType("order.created");

      await loadData();
    } catch (error) {
      console.error("Webhook creation error:", error);

      setMessage(
        error instanceof Error
          ? error.message
          : "Something went wrong."
      );
    } finally {
      setLoading(false);
    }
  };

  // SEND TEST EVENT

  const deliverEvent = async (id: string) => {
    if (testingWebhookId) return;

    const webhook = webhooks.find((item) => item.id === id);

    if (!webhook) {
      setMessage(
        "Webhook not found. Please refresh the dashboard."
      );
      return;
    }

    if (
      webhook.endpoint_url.trim() !== SAFE_DEMO_ENDPOINT
    ) {
      setMessage(
        "Test delivery blocked: this webhook does not use the approved demo endpoint."
      );
      return;
    }

    try {
      setTestingWebhookId(id);
      setMessage("Sending test event...");

      const response = await fetch(
        `${API}/api/webhooks/${id}/deliver`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            payload: {
              order_id: `ORD-${Date.now()}`,
              amount: 499,
              currency: "INR",
            },
          }),
        }
      );

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          result.detail ||
            `Delivery failed (${response.status}).`
        );
      }

      setMessage(
        `Test delivery completed: ${result.status || "success"}`
      );

      await loadData();
    } catch (error) {
      console.error("Test delivery error:", error);

      setMessage(
        error instanceof Error
          ? error.message
          : "Test delivery failed. Check the backend terminal."
      );
    } finally {
      setTestingWebhookId("");
    }
  };

  // RETRY FAILED DELIVERY

  const retryDelivery = async (delivery: Delivery) => {
    if (retryingDeliveryId) return;

    const webhook = webhooks.find(
      (item) => item.id === delivery.webhook_id
    );

    if (!webhook) {
      setMessage("Associated webhook was not found.");
      return;
    }

    if (
      webhook.endpoint_url.trim() !== SAFE_DEMO_ENDPOINT
    ) {
      setMessage(
        "This webhook endpoint is not approved for retry."
      );
      return;
    }

    try {
      setRetryingDeliveryId(delivery.id);

      const response = await fetch(
        `${API}/api/deliveries/${delivery.id}/retry`,
        {
          method: "POST",
        }
      );

      const result = await response.json();

      if (!response.ok) {
        throw new Error(
          result.detail || "Retry failed."
        );
      }

      setMessage(`Retry completed: ${result.status}`);

      await loadData();

      if (selectedDelivery?.id === delivery.id) {
        setSelectedDelivery({
          ...delivery,
          status: result.status || delivery.status,
          response_status:
            result.response_status ?? delivery.response_status,
          attempt_count:
            result.attempt_count ?? delivery.attempt_count,
        });
      }
    } catch (error) {
      console.error("Retry error:", error);

      setMessage(
        error instanceof Error
          ? error.message
          : "Retry request failed."
      );
    } finally {
      setRetryingDeliveryId("");
    }
  };

  // SUBSCRIPTION FUNCTIONS

  const loadSubscriptions = async (webhookId: string) => {
    try {
      setSubscriptionLoading(true);

      const response = await fetch(
        `${API}/api/webhooks/${webhookId}/subscriptions`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to load subscriptions."
        );
      }

      setSubscriptions(data.subscriptions || []);
    } catch (error) {
      setSubscriptionMessage(
        error instanceof Error
          ? error.message
          : "Subscription loading failed."
      );
    } finally {
      setSubscriptionLoading(false);
    }
  };

  const addSubscription = async () => {
    if (!selectedWebhook) return;

    const event = subscriptionEventType.trim();

    if (!event) {
      setSubscriptionMessage("Enter an event type first.");
      return;
    }

    try {
      setSubscriptionActionLoading(true);
      setSubscriptionMessage("");

      const response = await fetch(
        `${API}/api/webhooks/${selectedWebhook.id}/subscriptions`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            event_type: event,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Could not create subscription."
        );
      }

      setSubscriptionEventType("");

      setSubscriptionMessage(
        "Subscription created successfully!"
      );

      await loadSubscriptions(selectedWebhook.id);
    } catch (error) {
      setSubscriptionMessage(
        error instanceof Error
          ? error.message
          : "Subscription creation failed."
      );
    } finally {
      setSubscriptionActionLoading(false);
    }
  };

  const removeSubscription = async (event: string) => {
    if (!selectedWebhook) return;

    try {
      setSubscriptionActionLoading(true);
      setSubscriptionMessage("");

      const response = await fetch(
        `${API}/api/webhooks/${selectedWebhook.id}/subscriptions/${encodeURIComponent(
          event
        )}`,
        {
          method: "DELETE",
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Could not remove subscription."
        );
      }

      setSubscriptionMessage(
        "Unsubscribed successfully!"
      );

      await loadSubscriptions(selectedWebhook.id);
    } catch (error) {
      setSubscriptionMessage(
        error instanceof Error
          ? error.message
          : "Unsubscribe failed."
      );
    } finally {
      setSubscriptionActionLoading(false);
    }
  };

  // COPY TO CLIPBOARD

  const copyText = async (
    value: string,
    type: string
  ) => {
    try {
      await navigator.clipboard.writeText(value);

      setCopiedItem(type);

      window.setTimeout(() => {
        setCopiedItem("");
      }, 2000);
    } catch {
      setMessage("Unable to copy to clipboard.");
    }
  };

  // CSV EXPORT

  const csvCell = (value: unknown) => {
    const text = String(value ?? "");
    return `"${text.replace(/"/g, '""')}"`;
  };

  const exportDeliveries = () => {
    const rows = [
      [
        "Delivery ID",
        "Webhook ID",
        "Status",
        "HTTP Response",
        "Attempts",
        "Idempotency Key",
        "Created At",
      ],
      ...filteredDeliveries.map((delivery) => [
        delivery.id,
        delivery.webhook_id,
        delivery.status,
        delivery.response_status || "",
        `${delivery.attempt_count ?? 0}/${delivery.max_attempts ?? 3}`,
        delivery.idempotency_key || "",
        delivery.created_at,
      ]),
    ];

    const csv = rows
      .map((row) => row.map(csvCell).join(","))
      .join("\n");

    const blob = new Blob([csv], {
      type: "text/csv;charset=utf-8;",
    });

    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");

    anchor.href = url;
    anchor.download = "eventbridge-deliveries.csv";

    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();

    URL.revokeObjectURL(url);

    setMessage("CSV exported successfully!");
  };

  // FILTER WEBHOOKS

  const filteredWebhooks = webhooks.filter((webhook) => {
    const matchesSearch =
      webhook.name
        .toLowerCase()
        .includes(searchTerm.toLowerCase()) ||
      webhook.event_type
        .toLowerCase()
        .includes(searchTerm.toLowerCase());

    const matchesEvent =
      eventFilter === "all" ||
      webhook.event_type === eventFilter;

    return matchesSearch && matchesEvent;
  });

  // FILTER DELIVERIES

  const filteredDeliveries = deliveries.filter((delivery) => {
    return (
      statusFilter === "all" ||
      delivery.status === statusFilter
    );
  });

  // PAGINATION

  const totalPages = Math.max(
    1,
    Math.ceil(filteredDeliveries.length / ITEMS_PER_PAGE)
  );

  const safeCurrentPage = Math.min(
    currentPage,
    totalPages
  );

  const paginatedDeliveries = filteredDeliveries.slice(
    (safeCurrentPage - 1) * ITEMS_PER_PAGE,
    safeCurrentPage * ITEMS_PER_PAGE
  );

  // DASHBOARD STATISTICS

  const successCount = deliveries.filter(
    (item) => item.status === "success"
  ).length;

  const failedCount = deliveries.filter(
    (item) => item.status === "failed"
  ).length;

  const selectedDeliveries = selectedWebhook
    ? deliveries.filter(
        (item) => item.webhook_id === selectedWebhook.id
      )
    : [];

  const selectedSuccess = selectedDeliveries.filter(
    (item) => item.status === "success"
  ).length;

  const selectedFailed = selectedDeliveries.filter(
    (item) => item.status === "failed"
  ).length;

  const selectedTotal = selectedDeliveries.length;

  const successRate =
    selectedTotal > 0
      ? Math.round(
          (selectedSuccess / selectedTotal) * 100
        )
      : 0;

  // RENDER

  return (
    <main className="app-container">
      {/* TOPBAR */}

      <header className="topbar">
        <div className="brand">
          <div className="brand-icon">
            <Webhook size={24} />
          </div>

          <div>
            <h2>EventBridge Lite</h2>
            <span>Webhook Management Platform</span>
          </div>
        </div>

        <button
          type="button"
          className="refresh-btn"
          onClick={loadData}
          disabled={loading}
        >
          <RefreshCw
            size={16}
            className={loading ? "spin" : ""}
          />
          Refresh
        </button>
      </header>

      {/* WELCOME */}

      <section className="welcome-section">
        <div>
          <p className="eyebrow">DEVELOPER DASHBOARD</p>
          <h1>Webhook Control Center</h1>

          <p>
            Manage webhooks, monitor event deliveries and
            control subscriptions from one place.
          </p>
        </div>

        <div className="welcome-icon">
          <Activity size={48} />
        </div>
      </section>

      {/* GLOBAL MESSAGE */}

      {message && (
        <div className="notice">
          <span>{message}</span>

          <button
            type="button"
            onClick={() => setMessage("")}
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* STATISTICS */}

      <section className="stats-grid">
        <article className="stat-card">
          <Webhook />
          <p>Total Webhooks</p>
          <h3>{webhooks.length}</h3>
        </article>

        <article className="stat-card">
          <Activity />
          <p>Total Deliveries</p>
          <h3>{deliveries.length}</h3>
        </article>

        <article className="stat-card">
          <CheckCircle2 />
          <p>Successful</p>
          <h3>{successCount}</h3>
        </article>

        <article className="stat-card">
          <XCircle />
          <p>Failed</p>
          <h3>{failedCount}</h3>
        </article>
      </section>

      {/* CREATE WEBHOOK */}

      <section className="panel create-panel">
        <div className="section-heading">
          <div>
            <h2>Create Webhook</h2>
            <p>Register a new webhook endpoint.</p>
          </div>

          <Plus size={22} />
        </div>

        <form
          onSubmit={createWebhook}
          className="webhook-form"
        >
          <div className="form-group">
            <label>Webhook Name</label>

            <input
              type="text"
              placeholder="Example: Order Notifications"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label>Endpoint URL</label>

            <input
              type="url"
              value={endpoint}
              onChange={(e) => setEndpoint(e.target.value)}
              required
            />

            <small>
              Demo mode accepts only the approved HTTPS endpoint.
            </small>
          </div>

          <div className="form-group">
            <label>Event Type</label>

            <select
              value={eventType}
              onChange={(e) => setEventType(e.target.value)}
            >
              <option value="order.created">
                order.created
              </option>
              <option value="payment.completed">
                payment.completed
              </option>
              <option value="user.registered">
                user.registered
              </option>
            </select>
          </div>

          <button
            className="primary-btn"
            type="submit"
            disabled={loading}
          >
            <Plus size={17} />
            Create Webhook
          </button>
        </form>
      </section>

      {/* REGISTERED WEBHOOKS */}

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Registered Webhooks</h2>
            <p>View and manage your registered endpoints.</p>
          </div>

          <Webhook size={22} />
        </div>

        <div className="toolbar">
          <div className="search-box">
            <Search size={17} />

            <input
              type="text"
              placeholder="Search webhooks..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>

          <div className="filter-box">
            <Filter size={16} />

            <select
              value={eventFilter}
              onChange={(e) => setEventFilter(e.target.value)}
            >
              <option value="all">All Events</option>
              <option value="order.created">
                order.created
              </option>
              <option value="payment.completed">
                payment.completed
              </option>
              <option value="user.registered">
                user.registered
              </option>
            </select>
          </div>
        </div>

        <div className="webhook-list">
          {filteredWebhooks.length === 0 ? (
            <div className="empty-state">
              No webhooks found.
            </div>
          ) : (
            filteredWebhooks.map((webhook) => (
              <article
                className="webhook-card"
                key={webhook.id}
              >
                <div className="webhook-card-info">
                  <div className="webhook-card-icon">
                    <Webhook size={20} />
                  </div>

                  <div>
                    <h3>{webhook.name}</h3>
                    <p>{webhook.event_type}</p>
                    <small>{webhook.endpoint_url}</small>
                  </div>
                </div>

                <div className="webhook-card-actions">
                  <button
                    type="button"
                    className="secondary-btn"
                    onClick={() => setSelectedWebhook(webhook)}
                  >
                    <Eye size={15} />
                    Details
                  </button>

                  <button
                    type="button"
                    className="primary-btn"
                    disabled={
                      testingWebhookId !== "" ||
                      webhook.endpoint_url.trim() !==
                        SAFE_DEMO_ENDPOINT
                    }
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      deliverEvent(webhook.id);
                    }}
                  >
                    {testingWebhookId === webhook.id ? (
                      <RefreshCw
                        size={15}
                        className="spin"
                      />
                    ) : (
                      <Send size={15} />
                    )}
                    {testingWebhookId === webhook.id
                      ? "Testing..."
                      : "Test"}
                  </button>
                </div>
              </article>
            ))
          )}
        </div>
      </section>

      {/* DELIVERY HISTORY */}

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Delivery History</h2>
            <p>Track webhook delivery attempts and responses.</p>
          </div>

          <Activity size={22} />
        </div>

        <div className="toolbar">
          <div className="filter-box">
            <Filter size={16} />

            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setCurrentPage(1);
              }}
            >
              <option value="all">All Statuses</option>
              <option value="success">Success</option>
              <option value="failed">Failed</option>
              <option value="pending">Pending</option>
            </select>
          </div>

          <button
            type="button"
            className="secondary-btn"
            onClick={exportDeliveries}
          >
            <Download size={16} />
            Export CSV
          </button>
        </div>

        <div className="table-wrapper">
          <table className="delivery-table">
            <thead>
              <tr>
                <th>Delivery ID</th>
                <th>Webhook ID</th>
                <th>Status</th>
                <th>HTTP Code</th>
                <th>Attempts</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>

            <tbody>
              {paginatedDeliveries.length === 0 ? (
                <tr>
                  <td colSpan={7} className="empty-cell">
                    No deliveries found.
                  </td>
                </tr>
              ) : (
                paginatedDeliveries.map((delivery) => {
                  const webhook = webhooks.find(
                    (item) =>
                      item.id === delivery.webhook_id
                  );

                  const canRetry =
                    delivery.status === "failed" &&
                    webhook?.endpoint_url.trim() ===
                      SAFE_DEMO_ENDPOINT;

                  return (
                    <tr key={delivery.id}>
                      <td>
                        <code>
                          {delivery.id.slice(0, 8)}...
                        </code>
                      </td>

                      <td>
                        <code>
                          {delivery.webhook_id.slice(0, 8)}...
                        </code>
                      </td>

                      <td>
                        <span
                          className={`status ${delivery.status}`}
                        >
                          {delivery.status}
                        </span>
                      </td>

                      <td>
                        {delivery.response_status || "—"}
                      </td>

                      <td>
                        {delivery.attempt_count ?? 0}/
                        {delivery.max_attempts ?? 3}
                      </td>

                      <td>
                        {new Date(
                          delivery.created_at
                        ).toLocaleString()}
                      </td>

                      <td>
                        <div className="table-actions">
                          <button
                            type="button"
                            className="icon-btn"
                            title="View details"
                            onClick={() =>
                              setSelectedDelivery(delivery)
                            }
                          >
                            <Eye size={16} />
                          </button>

                          {canRetry && (
                            <button
                              type="button"
                              className="icon-btn"
                              title="Retry delivery"
                              disabled={
                                retryingDeliveryId === delivery.id
                              }
                              onClick={() =>
                                retryDelivery(delivery)
                              }
                            >
                              <RefreshCw
                                size={16}
                                className={
                                  retryingDeliveryId === delivery.id
                                    ? "spin"
                                    : ""
                                }
                              />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        <div className="pagination">
          <span>
            Page {safeCurrentPage} of {totalPages}
          </span>

          <div>
            <button
              type="button"
              className="secondary-btn"
              disabled={safeCurrentPage <= 1}
              onClick={() =>
                setCurrentPage((page) =>
                  Math.max(1, page - 1)
                )
              }
            >
              Previous
            </button>

            <button
              type="button"
              className="secondary-btn"
              disabled={safeCurrentPage >= totalPages}
              onClick={() =>
                setCurrentPage((page) =>
                  Math.min(totalPages, page + 1)
                )
              }
            >
              Next
            </button>
          </div>
        </div>
      </section>

      {/* WEBHOOK DETAILS MODAL */}

      {selectedWebhook && (
        <div
          className="modal-overlay"
          onClick={() => setSelectedWebhook(null)}
        >
          <section
            className="modal-content"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <h2>Webhook Details</h2>
                <p>
                  Manage webhook information and subscriptions.
                </p>
              </div>

              <button
                type="button"
                className="icon-btn"
                onClick={() => setSelectedWebhook(null)}
              >
                <X size={20} />
              </button>
            </div>

            <div className="details-grid">
              <div className="detail-field">
                <span>Webhook Name</span>
                <strong>{selectedWebhook.name}</strong>
              </div>

              <div className="detail-field">
                <span>Webhook ID</span>

                <div className="copy-row">
                  <code>{selectedWebhook.id}</code>

                  <button
                    type="button"
                    className="copy-btn"
                    onClick={() =>
                      copyText(
                        selectedWebhook.id,
                        "Webhook ID"
                      )
                    }
                  >
                    <Copy size={15} />
                    {copiedItem === "Webhook ID"
                      ? "Copied"
                      : "Copy ID"}
                  </button>
                </div>
              </div>

              <div className="detail-field">
                <span>Endpoint URL</span>

                <div className="copy-row">
                  <code>
                    {selectedWebhook.endpoint_url}
                  </code>

                  <button
                    type="button"
                    className="copy-btn"
                    onClick={() =>
                      copyText(
                        selectedWebhook.endpoint_url,
                        "Endpoint"
                      )
                    }
                  >
                    <Copy size={15} />
                    {copiedItem === "Endpoint"
                      ? "Copied"
                      : "Copy URL"}
                  </button>
                </div>
              </div>

              <div className="detail-field">
                <span>Event Type</span>
                <strong>{selectedWebhook.event_type}</strong>
              </div>

              <div className="detail-field">
                <span>Status</span>
                <strong>
                  <span
                    className={`status ${selectedWebhook.status}`}
                  >
                    {selectedWebhook.status}
                  </span>
                </strong>
              </div>

              <div className="detail-field">
                <span>Created Date</span>
                <strong>
                  {selectedWebhook.created_at
                    ? new Date(
                        selectedWebhook.created_at
                      ).toLocaleString()
                    : "Not available"}
                </strong>
              </div>
            </div>

            {/* WEBHOOK ANALYTICS */}

            <div className="analytics-section">
              <div className="section-heading">
                <div>
                  <h3>Webhook Analytics</h3>
                  <p>
                    Delivery performance for this webhook.
                  </p>
                </div>

                <BarChart3 size={21} />
              </div>

              <div className="analytics-grid">
                <article className="analytics-card">
                  <Activity size={18} />
                  <span>Total</span>
                  <strong>{selectedTotal}</strong>
                </article>

                <article className="analytics-card">
                  <CheckCircle2 size={18} />
                  <span>Successful</span>
                  <strong>{selectedSuccess}</strong>
                </article>

                <article className="analytics-card">
                  <XCircle size={18} />
                  <span>Failed</span>
                  <strong>{selectedFailed}</strong>
                </article>
              </div>

              <div className="success-rate">
                <div className="success-rate-heading">
                  <span>
                    <TrendingUp size={16} />
                    Success Rate
                  </span>

                  <strong>{successRate}%</strong>
                </div>

                <div className="progress-track">
                  <div
                    className="progress-fill"
                    style={{
                      width: `${successRate}%`,
                    }}
                  />
                </div>
              </div>
            </div>

            {/* SUBSCRIPTION MANAGEMENT */}

            <div className="subscription-section">
              <div className="section-heading">
                <div>
                  <h3>Webhook Subscriptions</h3>
                  <p>
                    Choose which events this webhook should receive.
                  </p>
                </div>

                <Activity size={21} />
              </div>

              <div className="subscription-form">
                <input
                  type="text"
                  placeholder="Example: payment.completed"
                  value={subscriptionEventType}
                  onChange={(e) =>
                    setSubscriptionEventType(e.target.value)
                  }
                />

                <button
                  type="button"
                  className="primary-btn"
                  onClick={addSubscription}
                  disabled={subscriptionActionLoading}
                >
                  <Plus size={16} />
                  Subscribe
                </button>
              </div>

              {subscriptionMessage && (
                <div className="subscription-notice">
                  {subscriptionMessage}
                </div>
              )}

              <div className="subscription-list">
                <div className="subscription-list-heading">
                  <strong>Active Subscriptions</strong>

                  <span>
                    {subscriptions.length} total
                  </span>
                </div>

                {subscriptionLoading ? (
                  <div className="empty-state">
                    Loading subscriptions...
                  </div>
                ) : subscriptions.length === 0 ? (
                  <div className="empty-state">
                    No subscriptions found.
                  </div>
                ) : (
                  subscriptions.map((subscription) => (
                    <div
                      className="subscription-item"
                      key={subscription.id}
                    >
                      <div>
                        <span className="subscription-dot" />
                        <strong>
                          {subscription.event_type}
                        </strong>
                      </div>

                      <button
                        type="button"
                        className="unsubscribe-btn"
                        disabled={subscriptionActionLoading}
                        onClick={() =>
                          removeSubscription(
                            subscription.event_type
                          )
                        }
                      >
                        <Trash2 size={15} />
                        Unsubscribe
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>

            <button
              type="button"
              className="modal-done-btn"
              onClick={() => setSelectedWebhook(null)}
            >
              Close
            </button>
          </section>
        </div>
      )}

      {/* DELIVERY DETAILS MODAL */}

      {selectedDelivery && (
        <div
          className="modal-overlay"
          onClick={() => setSelectedDelivery(null)}
        >
          <section
            className="modal-content"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <div>
                <h2>Delivery Details</h2>
                <p>Complete delivery information.</p>
              </div>

              <button
                type="button"
                className="icon-btn"
                onClick={() => setSelectedDelivery(null)}
              >
                <X size={20} />
              </button>
            </div>

            <div className="details-grid">
              <div className="detail-field">
                <span>Delivery ID</span>

                <div className="copy-row">
                  <code>{selectedDelivery.id}</code>

                  <button
                    type="button"
                    className="copy-btn"
                    onClick={() =>
                      copyText(
                        selectedDelivery.id,
                        "Delivery ID"
                      )
                    }
                  >
                    <Copy size={15} />
                    {copiedItem === "Delivery ID"
                      ? "Copied"
                      : "Copy ID"}
                  </button>
                </div>
              </div>

              <div className="detail-field">
                <span>Webhook ID</span>

                <div className="copy-row">
                  <code>
                    {selectedDelivery.webhook_id}
                  </code>

                  <button
                    type="button"
                    className="copy-btn"
                    onClick={() =>
                      copyText(
                        selectedDelivery.webhook_id,
                        "Delivery Webhook ID"
                      )
                    }
                  >
                    <Copy size={15} />
                    {copiedItem === "Delivery Webhook ID"
                      ? "Copied"
                      : "Copy ID"}
                  </button>
                </div>
              </div>

              <div className="detail-field">
                <span>Delivery Status</span>

                <strong>
                  <span
                    className={`status ${selectedDelivery.status}`}
                  >
                    {selectedDelivery.status}
                  </span>
                </strong>
              </div>

              <div className="detail-field">
                <span>HTTP Response Code</span>

                <strong>
                  {selectedDelivery.response_status ||
                    "Not available"}
                </strong>
              </div>

              <div className="detail-field">
                <span>Attempt Count</span>

                <strong>
                  {selectedDelivery.attempt_count ?? 0} /{" "}
                  {selectedDelivery.max_attempts ?? 3}
                </strong>
              </div>

              <div className="detail-field">
                <span>Last Attempt</span>

                <strong>
                  {selectedDelivery.last_attempt_at
                    ? new Date(
                        selectedDelivery.last_attempt_at
                      ).toLocaleString()
                    : "Not available"}
                </strong>
              </div>

              <div className="detail-field">
                <span>Idempotency Key</span>

                <strong>
                  {selectedDelivery.idempotency_key ||
                    "Not provided"}
                </strong>
              </div>

              <div className="detail-field">
                <span>Error Message</span>

                <strong>
                  {selectedDelivery.error_message ||
                    "No error recorded."}
                </strong>
              </div>

              <div className="detail-field">
                <span>Created Date</span>

                <strong>
                  {new Date(
                    selectedDelivery.created_at
                  ).toLocaleString()}
                </strong>
              </div>
            </div>

            <button
              type="button"
              className="modal-done-btn"
              onClick={() => setSelectedDelivery(null)}
            >
              Close
            </button>
          </section>
        </div>
      )}

      {/* FOOTER */}

      <footer>
        EventBridge Lite · Built with React, FastAPI & SQLite
      </footer>
    </main>
  );
}

export default App;
