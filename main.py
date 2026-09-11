import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from agent import run_agent

app = FastAPI(title="Store Assistant Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
async def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "Store Assistant Agent"}


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
            data = await websocket.receive_json()
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
