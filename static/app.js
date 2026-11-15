const $ = (s) => document.querySelector(s);

let mode = "create";

document.querySelectorAll(".tabs button").forEach((btn) => {
  btn.onclick = () => {
    mode = btn.dataset.mode;
    document.querySelectorAll(".tabs button").forEach((x) => x.classList.toggle("on", x === btn));
    $("#topicField").style.display = mode === "create" ? "" : "none";
    $("#codeField").style.display = mode === "join" ? "" : "none";
    $("#err").textContent = "";
    (mode === "create" ? $("#topic") : $("#code")).focus();
  };
});

const savedName = localStorage.getItem("rt_name");
if (savedName) $("#name").value = savedName;

async function post(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "请求失败，检查服务是否在运行");
  return data;
}

async function go() {
  const err = $("#err");
  const name = $("#name").value.trim();
  err.textContent = "";
  if (!name) {
    err.textContent = "先给自己起个昵称";
    return;
  }
  localStorage.setItem("rt_name", name);

  const btn = $("#go");
  btn.disabled = true;
  btn.textContent = "正在进入…";

  try {
    let code;
    if (mode === "create") {
      const topic = $("#topic").value.trim();
      if (!topic) throw new Error("议题不能为空");
      const room = await post("/api/rooms", { topic });
      code = room.code;
    } else {
      code = $("#code").value.trim();
      if (!code) throw new Error("房间号不能为空");
    }
    const member = await post(`/api/rooms/${code}/join`, { name });
    location.href = `/room?code=${code}&me=${member.id}`;
  } catch (e) {
    err.textContent = e.message;
    btn.disabled = false;
    btn.textContent = "开始";
  }
}

$("#go").onclick = go;

["name", "topic", "code"].forEach((id) => {
  $("#" + id).addEventListener("keydown", (e) => {
    if (e.key === "Enter") go();
  });
});
