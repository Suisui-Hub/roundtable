"""数据结构：只用 dataclass，零依赖。"""
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class Member:
    id: str
    room_id: str
    name: str
    color: str
    joined_at: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Message:
    id: str
    room_id: str
    member_id: str
    role: str            # "user" 或 "ai"
    content: str
    duration_ms: int
    created_at: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Card:
    id: str
    room_id: str
    message_id: str
    kind: str            # 主张 / 证据 / 疑问 / 共识
    content: str
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class HostAction:
    type: str            # balance_hint / invite / divergence_hint / converge_hint
    target: Optional[str]
    reason: str
    text: str = ""
    fallback_text: str = ""

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "target": self.target,
            "reason": self.reason,
            "text": self.text or self.fallback_text,
        }
