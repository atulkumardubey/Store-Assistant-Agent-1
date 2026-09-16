import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from agent import run_agent
from batch_tests import run_batch_test

app = FastAPI(title="Store Assistant Agent", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# ── 5 Demo Scenarios ──────────────────────────────────────────────────────────
DEMO_SCENARIOS = [
    {
        "id":    1,
        "tag":   "Happy Path",
        "color": "purple",
        "title": "Bulk Order with Discount",
        "query": "I need 2 blue shirts size M delivered to 560001",
        "desc":  "Stock check → 10% bulk discount → free BlueDart delivery to Bangalore.",
        "expected": "✅ 15 in stock · ₹2,158 (10% off) · FREE Sep 18 via BlueDart",
    },
    {
        "id":    2,
        "tag":   "Out of Stock",
        "color": "red",
        "title": "OOS → Agent Suggests Alternatives",
        "query": "I want 2 blue shirts size L delivered to 400001",
        "desc":  "Blue Shirt L has 0 stock. Agent reports OOS and offers M/S/XL alternatives.",
        "expected": "❌ Out of stock · Agent lists available sizes",
    },
    {
        "id":    3,
        "tag":   "Max Discount",
        "color": "green",
        "title": "Large Order — 20% Bulk Discount",
        "query": "Order 10 white shirts size L delivered to 110001",
        "desc":  "Quantity ≥10 triggers the maximum 20% bulk discount tier.",
        "expected": "✅ In stock · ₹7,992 (20% off) · FREE delivery Delhi",
    },
    {
        "id":    4,
        "tag":   "Error Recovery",
        "color": "orange",
        "title": "Invalid Pincode — Graceful Error",
        "query": "1 red shirt size M delivered to 99999",
        "desc":  "Stock OK, price OK, but delivery_eta fails on 5-digit PIN. Agent handles it.",
        "expected": "✅ Stock OK · ✅ Price OK · ⚠️ Invalid pincode — asks for correction",
    },
    {
        "id":    5,
        "tag":   "Paid Shipping",
        "color": "blue",
        "title": "Kolkata Zone — Paid Shipping",
        "query": "2 black jeans size 30 delivered to 700001",
        "desc":  "Valid order with 10% discount and 4-day delivery to Kolkata for ₹49.",
        "expected": "✅ In stock · 10% discount · 4-day delivery ₹49 to Kolkata",
    },
]


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "Store Assistant Agent", "version": "2.0.0"}


@app.get("/api/demo-scenarios")
async def demo_scenarios():
    return {"scenarios": DEMO_SCENARIOS}


@app.get("/api/batch-test")
async def batch_test():
    return run_batch_test()


@app.websocket("/ws/query")
async def ws_query(websocket: WebSocket):
    await websocket.accept()

    async def send(event: dict):
        try:
            await websocket.send_json(event)
        except Exception:
            pass

    try:
        while True:
            data  = await websocket.receive_json()
            query = (data.get("query") or "").strip()
            if not query:
                await send({"type": "error", "message": "Please enter a query."})
                continue

            await send({"type": "start", "query": query})
            try:
                await run_agent(query, send)
            except Exception as e:
                await send({"type": "error", "message": str(e)})
            await send({"type": "done"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
