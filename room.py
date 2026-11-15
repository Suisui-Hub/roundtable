"""编排层：把一次发言串成完整流程。

顺序：落库 -> 抽卡 -> 规则判定 -> 润色 -> 返回给前端广播。
"""
import asyncio
import time
from typing import Dict, Optional

import store
from config import CARD_TIMEOUT, COLORS
from host import HostState, apply_action, decide, update_state
from llm import extract_card, polish

# 房间状态放内存：演示规模足够，重启即重置
STATES: Dict[str, HostState] = {}


def _state(room_id: str, now: float) -> HostState:
    if room_id not in STATES:
        STATES[room_id] = HostState(started_at=now)
    return STATES[room_id]


def balance(room_id: str) -> dict:
    """发言均衡度：各成员时长的占比标准差。"""
    durations = store.sum_duration(room_id)
    if not durations:
        return {"pct": {}, "std": 0, "total_ms": 0}

    total = sum(durations.values()) or 1
    pct = {mid: round(ms / total * 100) for mid, ms in durations.items()}
    mean = sum(pct.values()) / len(pct)
    std = (sum((v - mean) ** 2 for v in pct.values()) / len(pct)) ** 0.5
    return {"pct": pct, "std": round(std), "total_ms": total}


def create(topic: str) -> dict:
    return store.create_room(topic)


def join(code: str, name: str) -> Optional[dict]:
    room = store.get_room_by_code(code)
    if not room:
        return None
    count = len(store.list_members(room["id"]))
    color = COLORS[count % len(COLORS)]
    return store.add_member(room["id"], name, color)


def get_state(code: str) -> Optional[dict]:
    room = store.get_room_by_code(code)
    if not room:
        return None
    return {
        "room": room,
        "members": store.list_members(room["id"]),
        "messages": store.list_messages(room["id"]),
        "cards": store.list_cards(room["id"]),
        "balance": balance(room["id"]),
    }


def _context(room_id: str, names: dict, limit: int = 6) -> str:
    msgs = store.list_messages(room_id)[-limit:]
    lines = []
    for m in msgs:
        who = names.get(m["member_id"], "AI 主持人")
        lines.append(f"{who}：{m['content']}")
    return "\n".join(lines)


async def post_message(code: str, member_id: str, content: str, duration_ms: int) -> Optional[dict]:
    room = store.get_room_by_code(code)
    if not room:
        return None

    now = time.time()
    msg = store.add_message(room["id"], member_id, "user", content, duration_ms)

    state = _state(room["id"], now)
    update_state(state, member_id, content, now)

    # 1. 抽卡（超时就跳过，不阻塞主流程）
    cards = []
    try:
        card = await asyncio.wait_for(extract_card(content), timeout=CARD_TIMEOUT)
    except asyncio.TimeoutError:
        card = None
    if card:
        cards.append(store.add_card(
            room["id"], msg["id"], card["kind"], card["content"], card["confidence"]
        ))

    # 2. 规则判定
    members = store.list_members(room["id"])
    names = {m["id"]: m["name"] for m in members}
    action = decide(state, member_id, content, now, [m["id"] for m in members], names)

    # 3. 有动作就润色，失败用兜底文案
    host_payload = None
    if action:
        try:
            text = await asyncio.wait_for(
                polish(action.type, action.reason, _context(room["id"], names)),
                timeout=CARD_TIMEOUT,
            )
        except asyncio.TimeoutError:
            text = None
        action.text = text or action.fallback_text
        host_msg = store.add_message(room["id"], "ai", "ai", action.text, 0)
        apply_action(state, action, now)
        host_payload = {"type": action.type, "text": action.text,
                        "target": action.target, "message": host_msg}

    return {
        "message": msg,
        "cards": cards,
        "host": host_payload,
        "balance": balance(room["id"]),
    }
