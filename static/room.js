const $ = (s) => document.querySelector(s);

const params = new URLSearchParams(location.search);
const CODE = params.get("code") || "";
let MY_ID = params.get("me") || "";

const S = {
  room: null,
  members: [],
  messages: [],
  cards: [],
  balance: { pct: {}, std: 0, total_ms: 0 },
  seen: new Set(),
  closed: false,
};

/* ---------------- 小工具 ---------------- */

function fmtClock(ts) {
  const d = new Date(ts * 1000);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function fmtDur(ms) {
  const s = Math.round((ms || 0) / 1000);
  if (s < 60) return s + "s";
  return Math.floor(s / 60) + "m" + String(s % 60).padStart(2, "0") + "s";
}

function fmtMMSS(ms) {
  const s = Math.round((ms || 0) / 1000);
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

function esc(text) {
  return String(text == null ? "" : text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function nameOf(memberId) {
  const m = S.members.find((x) => x.id === memberId);
  return m ? m.name : "成员";
}

function colorOf(memberId) {
  const m = S.members.find((x) => x.id === memberId);
  return m ? m.color : "#9AA7BF";
}

/* ---------------- 渲染 ---------------- */

function renderHeader() {
  const room = S.room || {};
  $("#topic").textContent = room.topic || "";
  $("#topic").title = room.topic || "";
  const st = $("#status");
  if (S.closed) {
    st.textContent = "讨论已结束";
    st.classList.add("closed");
  } else {
    st.textContent = "讨论进行中";
    st.classList.remove("closed");
  }
  $("#input").disabled = S.closed;
  $("#send").disabled = S.closed;
  $("#btnMinutes").textContent = S.closed ? "查看纪要" : "生成纪要";
}

function renderMembers() {
  $("#memberCount").textContent = `${S.members.length} 人`;
  const durations = {};
  S.messages.forEach((m) => {
    if (m.role === "user") durations[m.member_id] = (durations[m.member_id] || 0) + (m.duration_ms || 0);
  });

  if (!S.members.length) {
    $("#members").innerHTML = '<div class="empty">还没有人</div>';
    return;
  }

  $("#members").innerHTML = S.members
    .map((m) => {
      const me = m.id === MY_ID ? " me" : "";
      return `<div class="member${me}">
        <div class="dot" style="background:${m.color}">${esc(m.name.slice(0, 1))}</div>
        <div class="name">${esc(m.name)}${m.id === MY_ID ? "（我）" : ""}</div>
        <div class="ms">${fmtDur(durations[m.id] || 0)}</div>
      </div>`;
    })
    .join("");
}

function renderDonut() {
  const pct = S.balance.pct || {};
  const r = 54;
  const c = 70;
  const circ = 2 * Math.PI * r;

  const items = S.members
    .map((m) => ({ m, v: pct[m.id] || 0 }))
    .filter((it) => it.v > 0)
    .sort((a, b) => b.v - a.v);

  let segs = "";
  if (!items.length) {
    segs = `<circle cx="${c}" cy="${c}" r="${r}" fill="none" stroke="#EDF0F6" stroke-width="20"/>`;
  } else {
    let offset = 0;
    items.forEach((it) => {
      const len = (circ * it.v) / 100;
      segs += `<circle cx="${c}" cy="${c}" r="${r}" fill="none" stroke="${it.m.color}"
        stroke-width="20" stroke-linecap="butt"
        stroke-dasharray="${len.toFixed(2)} ${(circ - len).toFixed(2)}"
        stroke-dashoffset="${(-offset).toFixed(2)}"
        transform="rotate(-90 ${c} ${c})"/>`;
      offset += len;
    });
  }
  $("#donut").innerHTML = segs;

  $("#totalTime").textContent = fmtDur(S.balance.total_ms || 0);
  $("#legend").innerHTML = items
    .map(
      (it) => `<div class="legend-row"><i style="background:${it.m.color}"></i>
        <span>${esc(it.m.name)}</span><span>${it.v}%</span></div>`
    )
    .join("");

  const std = S.balance.std || 0;
  $("#std").textContent = std + "%";
  const bar = $("#stdBar");
  bar.style.width = Math.min(100, std * 2.5) + "%";
  bar.style.background = std <= 10 ? "#17A673" : std <= 20 ? "#F0A32A" : "#EA5455";
}

function renderMessages() {
  const box = $("#messages");
  if (!S.messages.length) {
    box.innerHTML = '<div class="empty">还没有人说话，先开个头吧</div>';
    return;
  }
  box.innerHTML = S.messages
    .map((m) => {
      if (m.role === "ai") {
        return `<div class="msg ai">
          <div class="av">AI</div>
          <div class="body">
            <div class="meta">AI 主持人 · ${fmtClock(m.created_at)}</div>
            <div class="bubble">${esc(m.content)}</div>
          </div>
        </div>`;
      }
      const name = nameOf(m.member_id);
      return `<div class="msg">
        <div class="av" style="background:${colorOf(m.member_id)}">${esc(name.slice(0, 1))}</div>
        <div class="body">
          <div class="meta">${esc(name)} · ${fmtClock(m.created_at)}${m.duration_ms ? " · " + fmtDur(m.duration_ms) : ""}</div>
          <div class="bubble">${esc(m.content)}</div>
        </div>
      </div>`;
    })
    .join("");
  box.scrollTop = box.scrollHeight;
}

function renderCards() {
  $("#cardCount").textContent = `${S.cards.length} 张`;
  if (!S.cards.length) {
    $("#cards").innerHTML = '<div class="empty">发言后自动抽取观点</div>';
    return;
  }
  $("#cards").innerHTML = S.cards
    .map((card) => {
      const src = S.messages.find((m) => m.id === card.message_id);
      const from = src ? nameOf(src.member_id) : "AI 主持人";
      return `<div class="pcard c-${esc(card.kind)}">
        <span class="kind k-${esc(card.kind)}">${esc(card.kind)}</span>
        <p>${esc(card.content)}</p>
        <div class="from">来源：${esc(from)}</div>
      </div>`;
    })
    .join("");
}

function renderAll() {
  renderHeader();
  renderMembers();
  renderDonut();
  renderMessages();
  renderCards();
}

/* ---------------- 数据 ---------------- */

function applyUpdate(payload) {
  if (!payload) return;
  const msg = payload.message;
  if (msg && !S.seen.has(msg.id)) {
    S.seen.add(msg.id);
    S.messages.push(msg);
  }
  if (payload.host && payload.host.message && !S.seen.has(payload.host.message.id)) {
    S.seen.add(payload.host.message.id);
    S.messages.push(payload.host.message);
  }
  (payload.cards || []).forEach((card) => {
    if (!S.cards.some((c) => c.id === card.id)) S.cards.push(card);
  });
  if (payload.balance) S.balance = payload.balance;
  renderAll();
}

async function loadState() {
  const res = await fetch(`/api/rooms/${CODE}/state`);
  if (!res.ok) throw new Error("房间不存在");
  const data = await res.json();
  S.room = data.room;
  S.members = data.members || [];
  S.messages = data.messages || [];
  S.messages.forEach((m) => S.seen.add(m.id));
  S.cards = data.cards || [];
  S.balance = data.balance || { pct: {}, std: 0, total_ms: 0 };
  S.closed = (data.room || {}).status === "closed";
  renderAll();
}

function connectWs() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/rooms/${CODE}`);
  ws.onmessage = (ev) => {
    let data;
    try {
      data = JSON.parse(ev.data);
    } catch (e) {
      return;
    }
    if (data.type === "update") applyUpdate(data.payload);
    if (data.type === "minutes") showMinutes(data.payload);
  };
  ws.onclose = () => setTimeout(connectWs, 1500);
}

/* ---------------- 发言 ---------------- */

let speakStart = 0;
const input = $("#input");

// 窄屏换行会挤掉提示语，手机上换成短的
const narrow = window.matchMedia("(max-width: 900px)");
function setPlaceholder() {
  input.placeholder = narrow.matches ? "说点什么……" : "说点什么…… (Enter 发送，Shift+Enter 换行)";
}
setPlaceholder();
narrow.addEventListener("change", setPlaceholder);

input.addEventListener("focus", () => {
  speakStart = Date.now();
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});

$("#send").onclick = send;

async function send() {
  const content = input.value.trim();
  if (!content || S.closed) return;

  const duration = speakStart ? Math.min(Math.max(Date.now() - speakStart, 2000), 120000) : 4000;
  input.value = "";
  speakStart = 0;
  $("#send").disabled = true;

  try {
    const res = await fetch(`/api/rooms/${CODE}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ memberId: MY_ID, content, durationMs: duration }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "发送失败");
    applyUpdate(data);
  } catch (e) {
    console.error(e);
  } finally {
    $("#send").disabled = S.closed;
    input.focus();
  }
}

/* ---------------- 纪要 ---------------- */

function minutesHtml(data) {
  const decisions = (data.decisions || []).map((d) => `<li>${esc(d)}</li>`).join("");
  const divergences = (data.divergences || [])
    .map((d) => {
      const sides = (d.sides || []).filter(Boolean);
      const sideHtml = sides.length
        ? `<div class="sides">${sides.map((s) => `<span class="side">${esc(s)}</span>`).join("")}</div>`
        : "";
      return `<li>${esc(d.point || "")}${sideHtml}</li>`;
    })
    .join("");
  const todos = (data.todos || [])
    .map((t) => `<div class="todo">${esc(t.owner || "")}· ${esc(t.task || "")}${t.due ? `<span class="due">${esc(t.due)}</span>` : ""}</div>`)
    .join("");

  return `<h2>讨论纪要</h2>
    <p class="sub">${esc(S.room ? S.room.topic : "")} · 共 ${S.members.length} 人参与</p>
    <h4>共识 / 决议</h4>${decisions ? `<ul>${decisions}</ul>` : "<p class='empty'>尚未形成明确共识</p>"}
    <h4>尚未解决的分歧</h4>${divergences ? `<ul>${divergences}</ul>` : "<p class='empty'>暂无</p>"}
    <h4>待办</h4>${todos || "<p class='empty'>暂无</p>"}
    <div class="actions">
      <button class="ghost" onclick="document.getElementById('veil').classList.remove('show')">关闭</button>
      <button class="solid" onclick="location.href='/api/rooms/${CODE}/minutes/export'">导出 Word</button>
    </div>`;
}

function showMinutes(data) {
  $("#modal").innerHTML = minutesHtml(data);
  $("#veil").classList.add("show");
  S.closed = true;
  renderHeader();
}

$("#btnMinutes").onclick = async () => {
  const btn = $("#btnMinutes");
  btn.disabled = true;
  btn.textContent = "生成中…";
  try {
    const res = await fetch(`/api/rooms/${CODE}/minutes`, { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "生成失败");
    showMinutes(data);
  } catch (e) {
    alert(e.message);
  } finally {
    btn.disabled = false;
    renderHeader();
  }
};

/* ---------------- 加入 ---------------- */

async function joinGate() {
  const name = $("#gateName").value.trim();
  const err = $("#gateErr");
  err.textContent = "";
  if (!name) {
    err.textContent = "先给自己起个昵称";
    return;
  }
  try {
    const res = await fetch(`/api/rooms/${CODE}/join`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "加入失败");
    MY_ID = data.id;
    localStorage.setItem("rt_name", name);
    history.replaceState(null, "", `/room?code=${CODE}&me=${MY_ID}`);
    $("#gate").classList.remove("show");
    boot();
  } catch (e) {
    err.textContent = e.message;
  }
}

/* ---------------- 启动 ---------------- */

async function boot() {
  try {
    await loadState();
    connectWs();
  } catch (e) {
    $("#messages").innerHTML = `<div class="empty">${esc(e.message)}</div>`;
  }
}

(function init() {
  $("#gateCode").textContent = CODE;
  const saved = localStorage.getItem("rt_name");
  if (saved) $("#gateName").value = saved;
  $("#gateGo").onclick = joinGate;
  $("#gateName").addEventListener("keydown", (e) => {
    if (e.key === "Enter") joinGate();
  });

  if (!CODE) {
    location.href = "/";
    return;
  }
  if (MY_ID) {
    $("#gate").classList.remove("show");
    boot();
  }
})();
