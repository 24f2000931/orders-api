from fastapi import FastAPI, Header, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import uuid
import base64

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TOTAL_ORDERS = 53
RATE_LIMIT = 19
WINDOW = 10

catalog = [
    {"id": i, "item": f"Item {i}"}
    for i in range(1, TOTAL_ORDERS + 1)
]

orders_created = {}
client_requests = {}


def encode_cursor(index: int) -> str:
    return base64.b64encode(str(index).encode()).decode()


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    return int(base64.b64decode(cursor).decode())


@app.post("/orders")
def create_order(
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    client_id: str = Header(..., alias="X-Client-Id"),
):
    now = time.time()
    print(f"Client={client_id} Time={now}")
    # Get this client's requests within the last 10 seconds
    history = client_requests.get(client_id, [])
    history = [t for t in history if now - t < WINDOW]

    # Save cleaned history
    client_requests[client_id] = history

    # Rate limit check
    if len(history) >= RATE_LIMIT:
        retry_after = max(1, int(WINDOW - (now - history[0])) + 1)

        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers={
                "Retry-After": str(retry_after)
            }
        )

    # Record this request
    history.append(now)
    client_requests[client_id] = history

    # Idempotency
    if idempotency_key in orders_created:
        response.status_code = 201
        return orders_created[idempotency_key]

    order = {
        "id": str(uuid.uuid4()),
        "status": "created"
    }

    orders_created[idempotency_key] = order
    response.status_code = 201
    return order


@app.get("/orders")
def list_orders(limit: int = 10, cursor: str | None = None):
    if limit < 1:
        limit = 1

    start = decode_cursor(cursor)
    end = min(start + limit, TOTAL_ORDERS)

    items = catalog[start:end]

    next_cursor = None
    if end < TOTAL_ORDERS:
        next_cursor = encode_cursor(end)

    return {
        "items": items,
        "next_cursor": next_cursor
    }
