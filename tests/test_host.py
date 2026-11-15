"""主持策略单测：这是全项目最该被测的部分。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import COOLDOWN, CONVERGE_MIN_MESSAGES, DIVERGENCE_HIT_LIMIT, DIVERGENCE_WORDS
from host import HostState, apply_action, decide, update_state

NAMES = {"a": "小林", "b": "阿哲", "c": "诗雨"}
IDS = ["a", "b", "c"]


def fresh(started_at=0.0):
    return HostState(started_at=started_at)


def test_quiet_when_nothing_happens():
    state = fresh(now_start := 1000.0)
    update_state(state, "a", "我觉得应该推广", now_start)
    assert decide(state, "a", "我觉得应该推广", now_start, IDS, NAMES) is None


def test_streak_hint_after_three_messages():
    state = fresh(0.0)
    now = 1000.0
    for i in range(3):
        now += 1
        update_state(state, "a", f"第{i}条", now)
    action = decide(state, "a", "第3条", now, IDS, NAMES)
    assert action is not None
    assert action.type == "balance_hint"
    assert action.target == "a"
    assert "小林" in action.fallback_text


def test_cooldown_blocks_repeat():
    state = fresh(0.0)
    now = 1000.0
    for i in range(3):
        now += 1
        update_state(state, "a", f"第{i}条", now)
    action = decide(state, "a", "第3条", now, IDS, NAMES)
    assert action is not None
    apply_action(state, action, now)

    update_state(state, "a", "又说一句", now + 1)
    assert decide(state, "a", "又说一句", now + 1, IDS, NAMES) is None

    later = now + COOLDOWN + 1
    update_state(state, "a", "再说一句", later)
    assert decide(state, "a", "再说一句", later, IDS, NAMES) is not None


def test_invite_silent_member():
    state = fresh(0.0)
    now = 1000.0
    update_state(state, "a", "我先说一句", now - 400)
    update_state(state, "b", "我也说", now - 300)
    update_state(state, "c", "嗯", now - 300)
    action = decide(state, "a", "继续", now, IDS, NAMES)
    assert action is not None
    assert action.type == "invite"
    assert action.target in ("b", "c")


def test_no_invite_in_single_member_room():
    state = fresh(0.0)
    now = 1000.0
    update_state(state, "a", "一个人", now - 400)
    assert decide(state, "a", "再说", now, ["a"], {"a": "小林"}) is None


def test_divergence_hint():
    now = 1000.0
    state = fresh(now)
    word = DIVERGENCE_WORDS[0]
    for i in range(DIVERGENCE_HIT_LIMIT):
        now += 1
        update_state(state, "a", f"我{word}这个做法", now)
        update_state(state, "b", f"我{word}你的说法", now)
    state.last_spoke = {mid: now for mid in IDS}   # 排除沉默规则干扰
    action = decide(state, "c", "我想问问", now + 1, IDS, NAMES)
    assert action is not None
    assert action.type == "divergence_hint"
    apply_action(state, action, now + 1)
    assert state.divergence_hits == 0


def test_converge_when_time_is_up():
    now = 600.0
    state = fresh(now - 500)
    update_state(state, "a", "开始", now - 1)
    update_state(state, "b", "我说两句", now - 1)
    update_state(state, "c", "嗯", now - 1)
    state.message_count = CONVERGE_MIN_MESSAGES
    action = decide(state, "b", "我同意", now, IDS, NAMES)
    assert action is not None
    assert action.type == "converge_hint"


def test_converge_needs_enough_messages():
    now = 600.0
    state = fresh(now - 500)
    update_state(state, "a", "开始", now - 1)
    update_state(state, "c", "嗯", now - 1)
    state.message_count = CONVERGE_MIN_MESSAGES - 2   # 再过一条也还没到阈值
    update_state(state, "b", "我同意", now)
    assert decide(state, "b", "我同意", now, IDS, NAMES) is None
