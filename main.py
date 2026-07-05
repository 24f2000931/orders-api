from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
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

catalog = [{"id": i, "item": f"Item {i}"} for i in range(1, TOTAL_ORDERS + 1)]
orders_created = {}
client_requests = {}


def encode_cursor(index):
    return base64.b64encode(str(index).encode()).decode()


def decode_cursor(cursor):
    if cursor is None:
        return 0
    return int(base64.b64decode(cursor).decode())


@app.post("/orders", status_code=201)
def create_order(
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    client_id: str = Header(..., alias="X-Client-Id"),
):
    now = time.time()

    history = client_requests.get(client_id, [])
    history = [t for t in history if now - t < WINDOW]

    if len(history) >= RATE_LIMIT:
        retry = WINDOW - (now - history[0])
        response.headers["Retry-After"] = str(int(retry) + 1)
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    history.append(now)
    client_requests[client_id] = history

    if idempotency_key in orders_created:
        return orders_created[idempotency_key]

    order = {
        "id": str(uuid.uuid4()),
        "status": "created"
    }

    orders_created[idempotency_key] = order
    return order


@app.get("/orders")
def list_orders(limit: int = 10, cursor: str = None):
    start = decode_cursor(cursor)
    end = min(start + limit, TOTAL_ORDERS)

    items = catalog[start:end]

    next_cursor = encode_cursor(end) if end < TOTAL_ORDERS else None

    return {
        "items": items,
        "next_cursor": next_cursor
    }