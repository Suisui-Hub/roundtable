"""圆桌 RoundTable · 服务入口

启动：uvicorn main:app --reload
然后浏览器打开 http://127.0.0.1:8000
"""
import os
from contextlib import asynccontextmanager

from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import minutes as minutes_mod
import room as room_mod
import store
from config import BASE_DIR, USE_MOCK

STATIC_DIR = os.path.join(BASE_DIR, "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init_db()
    print(f"[启动] 数据库：{store.DB_PATH}")
    print(f"[启动] 模型：{'本地假实现（未配置 RT_API_KEY）' if USE_MOCK else '远程 API'}")
    yield


app = FastAPI(title="圆桌 RoundTable", lifespan=lifespan)


@app.middleware("http")
async def no_store(request, call_next):
    """开发期最快：页面和静态文件都不缓存，改完刷新就生效。"""
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/static") or path in ("/", "/room"):
        response.headers["Cache-Control"] = "no-store"
    return response


class ConnectionManager:
    """房间码 -> WebSocket 集合，只管广播。"""

    def __init__(self):
        self.rooms = {}

    async def connect(self, code: str, ws: WebSocket):
        await ws.accept()
        self.rooms.setdefault(code, set()).add(ws)

    def disconnect(self, code: str, ws: WebSocket):
        self.rooms.get(code, set()).discard(ws)

    async def broadcast(self, code: str, data: dict):
        for ws in list(self.rooms.get(code, set())):
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(code, ws)


manager = ConnectionManager()


# ---------------- 房间 ----------------

@app.post("/api/rooms")
async def api_create_room(payload: dict = Body(...)):
    topic = (payload.get("topic") or "").strip()
    if not topic:
        raise HTTPException(status_code=400, detail="议题不能为空")
    return room_mod.create(topic)


@app.post("/api/rooms/{code}/join")
async def api_join(code: str, payload: dict = Body(...)):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="昵称不能为空")
    member = room_mod.join(code, name)
    if not member:
        raise HTTPException(status_code=404, detail="房间不存在")
    return member


@app.get("/api/rooms/{code}/state")
async def api_state(code: str):
    state = room_mod.get_state(code)
    if not state:
        raise HTTPException(status_code=404, detail="房间不存在")
    return state


# ---------------- 发言 ----------------

@app.post("/api/rooms/{code}/messages")
async def api_message(code: str, payload: dict = Body(...)):
    content = (payload.get("content") or "").strip()
    member_id = payload.get("memberId") or ""
    if not content or not member_id:
        raise HTTPException(status_code=400, detail="缺少发言内容或成员")
    try:
        duration_ms = int(payload.get("durationMs") or 0)
    except (TypeError, ValueError):
        duration_ms = 0
    duration_ms = max(0, min(duration_ms, 120000))

    result = await room_mod.post_message(code, member_id, content, duration_ms)
    if not result:
        raise HTTPException(status_code=404, detail="房间不存在")

    await manager.broadcast(code, {"type": "update", "payload": result})
    return result


# ---------------- 纪要 ----------------

@app.post("/api/rooms/{code}/minutes")
async def api_minutes(code: str):
    data = await minutes_mod.build(code)
    if data is None:
        raise HTTPException(status_code=404, detail="房间不存在")
    await manager.broadcast(code, {"type": "minutes", "payload": data})
    return data


@app.get("/api/rooms/{code}/minutes/export")
async def api_export(code: str):
    path = minutes_mod.export_docx(code)
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="还没有生成纪要")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"圆桌纪要_{code}.docx",
    )


# ---------------- WebSocket ----------------

@app.websocket("/ws/rooms/{code}")
async def ws_room(ws: WebSocket, code: str):
    await manager.connect(code, ws)
    try:
        while True:
            await ws.receive_text()      # 只做心跳，消息走 HTTP
    except WebSocketDisconnect:
        manager.disconnect(code, ws)


# ---------------- 静态页面 ----------------

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/room")
async def room_page():
    return FileResponse(os.path.join(STATIC_DIR, "room.html"))
