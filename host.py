"""主持策略引擎。

全项目最核心的 80 行：给状态和新消息，返回一个动作或 None。
纯函数，不查库、不调模型，所以可以被单元测试穷举。

规则优先级：冷却 -> 连说 -> 沉默 -> 分歧 -> 收敛
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from config import (
    COOLDOWN, STREAK_LIMIT, SILENCE_SECONDS, CONVERGE_SECONDS,
    CONVERGE_MIN_MESSAGES, DIVERGENCE_WORDS, DIVERGENCE_HIT_LIMIT, FALLBACK,
)
from models import HostAction


@dataclass
class HostState:
    started_at: float
    last_action_at: float = 0.0
    streak: Dict[str, int] = field(default_factory=dict)      # member_id -> 连续条数
    last_spoke: Dict[str, float] = field(default_factory=dict)  # member_id -> 上次发言时间
    divergence_hits: int = 0
    message_count: int = 0


def update_state(state: HostState, member_id: str, content: str, now: float) -> None:
    """每条用户消息进来时更新计数。"""
    state.message_count += 1
    for mid in list(state.streak):
        if mid != member_id:
            state.streak[mid] = 0
    state.streak[member_id] = state.streak.get(member_id, 0) + 1
    state.last_spoke[member_id] = now

    if any(word in content for word in DIVERGENCE_WORDS):
        state.divergence_hits += 1


def decide(state: HostState, member_id: str, content: str, now: float,
           member_ids: List[str], names: Dict[str, str]) -> Optional[HostAction]:
    """核心：决定这一次要不要干预、干预什么。"""
    name = names.get(member_id, "同学")

    # 0. 冷却：10 秒内不重复干预，避免刷屏
    if now - state.last_action_at < COOLDOWN:
        return None

    # 1. 有人连说 3 条 -> 让麦
    streak = state.streak.get(member_id, 0)
    if streak >= STREAK_LIMIT:
        return HostAction(
            type="balance_hint",
            target=member_id,
            reason="连续发言",
            fallback_text=FALLBACK["balance_hint"].format(name=name, streak=streak),
        )

    # 2. 有人沉默超过 180 秒 -> 点名（房间至少 2 人）
    silent = [
        mid for mid in member_ids
        if mid != member_id and now - state.last_spoke.get(mid, state.started_at) >= SILENCE_SECONDS
    ]
    if silent and len(member_ids) >= 2:
        target = silent[0]
        return HostAction(
            type="invite",
            target=target,
            reason="沉默超时",
            fallback_text=FALLBACK["invite"].format(name=names.get(target, "同学")),
        )

    # 3. 分歧候选累计 2 次 -> 亮红
    if state.divergence_hits >= DIVERGENCE_HIT_LIMIT:
        return HostAction(
            type="divergence_hint",
            target=None,
            reason="分歧候选",
            fallback_text=FALLBACK["divergence_hint"],
        )

    # 4. 讨论满 8 分钟且消息够多 -> 提示收敛
    if now - state.started_at >= CONVERGE_SECONDS and state.message_count >= CONVERGE_MIN_MESSAGES:
        return HostAction(
            type="converge_hint",
            target=None,
            reason="到时收敛",
            fallback_text=FALLBACK["converge_hint"],
        )

    return None


def apply_action(state: HostState, action: HostAction, now: float) -> None:
    """动作发出后更新状态：记冷却时间，分歧提示发过就清零。"""
    state.last_action_at = now
    if action.type == "divergence_hint":
        state.divergence_hits = 0
