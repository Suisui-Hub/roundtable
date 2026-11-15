"""模型适配层。

四个能力：抽卡、润色、纪要、通用补全。
全部带超时和降级：没有 Key 时走本地假实现，接口挂了也不会让界面崩。
"""
import json
import re
from typing import Optional

import httpx

from config import (
    API_BASE, API_KEY, MODEL, USE_MOCK, LLM_TIMEOUT,
    PROMPT_EXTRACT, PROMPT_POLISH, PROMPT_MINUTES,
)


# ---------------- 基础：调模型 ----------------

async def complete(prompt: str, temperature: float = 0.3, max_tokens: int = 300) -> Optional[str]:
    """发一次请求，拿一段文本。失败一律返回 None，由上层降级。"""
    if USE_MOCK or not API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            resp = await client.post(
                f"{API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as exc:  # 网络、超时、格式，全部吞掉
        print(f"[llm] 调用失败：{exc}")
        return None


def parse_json(text: Optional[str]) -> Optional[dict]:
    """容错解析：剥掉 ``` 围栏，截取第一个 { 到最后一个 }。"""
    if not text:
        return None
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


# ---------------- 观点抽取 ----------------

def mock_card(text: str) -> dict:
    """无 Key 时的规则版抽卡：按关键词判断类型，够演示用。"""
    t = (text or "").strip()
    if len(t) < 5:
        return {"kind": "", "content": "", "confidence": 0}

    if any(k in t for k in ("?", "？", "吗", "怎么", "为什么", "是不是", "什么")):
        kind = "疑问"
    elif any(k in t for k in ("数据", "调查", "报告", "统计", "%", "研究", "去年", "查过", "听说", "比例")):
        kind = "证据"
    elif any(k in t for k in ("都同意", "共识", "一致", "统一", "达成")):
        kind = "共识"
    else:
        kind = "主张"

    return {"kind": kind, "content": t[:25], "confidence": 0.8}


async def extract_card(text: str) -> Optional[dict]:
    """一条发言 -> 一张卡片。失败返回 None，宁可少一张卡，不可崩一次会。"""
    data = None
    if not USE_MOCK:
        raw = await complete(PROMPT_EXTRACT.format(text=text), temperature=0.2, max_tokens=120)
        data = parse_json(raw)

    if not data:
        data = mock_card(text)

    kind = str(data.get("kind", "")).strip()
    content = str(data.get("content", "")).strip()
    try:
        confidence = float(data.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0

    if not kind or not content or confidence < 0.5:
        return None
    if kind not in ("主张", "证据", "疑问", "共识"):
        return None
    return {"kind": kind, "content": content, "confidence": confidence}


# ---------------- 主持人润色 ----------------

async def polish(action_type: str, reason: str, context: str) -> Optional[str]:
    """把规则动作说得像人话。失败返回 None，上层用兜底文案。"""
    if USE_MOCK:
        return None
    raw = await complete(
        PROMPT_POLISH.format(action_type=action_type, reason=reason, context=context),
        temperature=0.7,
        max_tokens=100,
    )
    if not raw:
        return None
    text = raw.strip().strip('"“”').replace("\n", "")
    return text[:80] or None


# ---------------- 纪要 ----------------

def _bigrams(text: str) -> set:
    text = re.sub(r"\s+", "", text)
    return {text[i:i + 2] for i in range(len(text) - 1)}


def similarity(a: str, b: str) -> float:
    """字符二元组 Jaccard，零依赖，够判断“是不是在说同一件事”。"""
    sa, sb = _bigrams(a), _bigrams(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def mock_minutes(messages: list, cards: list, names: dict) -> dict:
    """无 Key 时的规则版纪要：只从卡片和消息里摘，不编造内容。"""
    decisions, divergences, todos = [], [], []

    # 共识：先取标为“共识”的卡片，再补“主张”里带推进口吻的，去重后最多 3 条
    ordered = [c for c in cards if c["kind"] == "共识"] + [
        c for c in cards if c["kind"] == "主张"
        and any(k in c["content"] for k in ("同意", "支持", "可以", "建议", "应该", "试点"))
    ]
    for card in ordered:
        text = card["content"].strip()
        if not text:
            continue
        # 转折句是异议，不算共识
        if text[:2] in ("但是", "不过", "可是", "然而", "反对", "不行"):
            continue
        if any(similarity(text, d) > 0.5 for d in decisions):
            continue
        decisions.append(text)
        if len(decisions) >= 3:
            break

    # 分歧：一正一反两种立场 → 真分歧；两段几乎一样 → 只是措辞不同
    pos = ("推广", "支持", "可以", "应该", "建议", "同意", "试点")
    neg = ("禁止", "反对", "不应该", "不行", "担心", "隐患", "风险", "事故", "负责")
    claims = [c["content"].strip() for c in cards if c["kind"] == "主张" and c["content"].strip()]
    pro = [c for c in claims if any(k in c for k in pos) and not any(k in c for k in neg)]
    con = [c for c in claims if any(k in c for k in neg)]
    if pro and con:
        divergences.append({
            "point": "一方想往前推，一方担心风险——先确认争的是“要不要”还是“怎么推”",
            "sides": [pro[0][:40], con[0][:40]],
        })
    else:
        for i in range(len(claims)):
            merged = False
            for j in range(i + 1, len(claims)):
                if similarity(claims[i], claims[j]) > 0.6:
                    divergences.append({
                        "point": "两段表述很接近，可能只是在说同一件事的不同说法",
                        "sides": [claims[i][:40], claims[j][:40]],
                    })
                    merged = True
                    break
            if merged:
                break

    # 还没答上来的疑问，也进分歧区（它是下次讨论的入口）
    for card in cards:
        if card["kind"] == "疑问":
            divergences.append({
                "point": "还没答上来：" + card["content"][:36],
                "sides": [],
            })
            break

    seen_tasks = set()
    for msg in messages:
        if msg["role"] != "user":
            continue
        if any(k in msg["content"] for k in ("去查", "联系", "确认", "负责", "下次", "统计一下", "要有")):
            task = msg["content"].strip()
            if task in seen_tasks:
                continue
            seen_tasks.add(task)
            todos.append({
                "owner": names.get(msg["member_id"], "成员"),
                "task": task if len(task) <= 30 else task[:30] + "…",
                "due": "下次讨论前",
            })

    return {
        "decisions": decisions[:5],
        "divergences": divergences[:3],
        "todos": todos[:5],
    }


def _normalize(data: dict) -> dict:
    return {
        "decisions": [str(x) for x in data.get("decisions", []) if str(x).strip()][:8],
        "divergences": [
            {
                "point": str(d.get("point", "")).strip(),
                "sides": [str(s) for s in d.get("sides", [])][:2],
            }
            for d in data.get("divergences", []) if isinstance(d, dict)
        ][:5],
        "todos": [
            {
                "owner": str(t.get("owner", "")).strip(),
                "task": str(t.get("task", "")).strip(),
                "due": str(t.get("due", "")).strip(),
            }
            for t in data.get("todos", []) if isinstance(t, dict)
        ][:8],
    }


async def make_minutes(messages: list, cards: list, names: dict) -> dict:
    """生成纪要：模型优先，失败走规则版。"""
    if not USE_MOCK:
        transcript = "\n".join(
            f'{names.get(m["member_id"], "AI")}：{m["content"]}'
            for m in messages if m["role"] == "user"
        )
        card_text = "\n".join(f'{c["kind"]}：{c["content"]}' for c in cards)
        raw = await complete(
            PROMPT_MINUTES.format(transcript=transcript[:2500], cards=card_text[:1200]),
            temperature=0.3,
            max_tokens=700,
        )
        data = parse_json(raw)
        if data:
            return _normalize(data)

    return mock_minutes(messages, cards, names)
