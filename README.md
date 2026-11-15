# 圆桌 RoundTable

> 别人做会后总结，我们做会中干预。

一场 3–5 人的小组讨论，AI 不替你说话、不给结论，只在**发言失衡**、**有人沉默**、
**出现真分歧**、**该收敛了**这四个时刻开口，把讨论往前推一点。讨论结束自动出纪要，
可导出 Word。

---

## 一、怎么跑起来（3 分钟）

需要 Python 3.10 以上。

```bash
cd roundtable
pip install -r requirements.txt
python run.py            # 默认 http://127.0.0.1:8000
python run.py 8123       # 也可以指定端口
```

打开 `http://127.0.0.1:8000`：

1. 首页填议题 → 点「创建讨论」，系统给一个 4 位房间号；
2. 把房间号发给同学，他们在首页「加入讨论」里填名字 + 房间号；
3. 上面所有人都进了房间，开始发言（Enter 发送，Shift+Enter 换行）；
4. 聊完点右上角「生成纪要」，可导出 Word。

> 没有 API Key 也能完整跑通：系统会自动进入**本地假实现**（mock）模式，
> 观点卡片、主持人提示、纪要都由规则生成，用来演示和答辩足够了。

## 二、让别人连进来

默认只监听 `127.0.0.1`，也就是**只有这台电脑能打开**。三档需求，对号入座：

| 场景 | 怎么做 | 地址长什么样 |
| --- | --- | --- |
| 本机演示 / 自己调试 | `python run.py` 或双击 `启动.bat` | `http://127.0.0.1:8000` |
| 同一 Wi-Fi 下的同学 | `python run.py 8000 --lan` 或双击 `启动_局域网共享.bat` | `http://10.x.x.x:8000`（第一次会弹防火墙，勾"专用网络"） |
| 不同网络、不同城市 | 先用 `--lan` 起服务，再开一个终端跑内网穿透 | `https://xxx.trycloudflare.com` |

内网穿透（免费、不用注册、自带 HTTPS，WebSocket 也能穿）：

```bash
cloudflared tunnel --url http://127.0.0.1:8000
```

输出里那个 `https://xxx.trycloudflare.com` 发给谁都能打开。`localtunnel`（`npx localtunnel --port 8000`）也行，
但偶尔会给访客加一个密码页，答辩前一定要先自己试一遍。

> 注意：开了 `--lan` 或穿透，等于同一网络里任何人都能进你的房间。
> 演示结束后记得按 Ctrl+C 关掉，不要一直挂着。

## 三、接上真模型（可选）

设置环境变量后重启即可，代码不用改：

```powershell
$env:RT_API_KEY  = "sk-..."                 # DeepSeek 或任何 OpenAI 兼容接口
$env:RT_API_BASE = "https://api.deepseek.com/v1"
$env:RT_MODEL    = "deepseek-chat"
python run.py
```

| 变量 | 作用 | 默认值 |
| --- | --- | --- |
| `RT_API_KEY` | 模型 Key，不填就进 mock 模式 | 空 |
| `RT_API_BASE` | 兼容 OpenAI 的接口地址 | `https://api.deepseek.com/v1` |
| `RT_MODEL` | 模型名 | `deepseek-chat` |

模型只负责**表达**，不负责**决策**：谁该被点名、什么时候该收敛，全部由 `host.py`
的规则判断，模型挂掉或超时就退回 `config.py` 里的兜底文案。所以演示不会抽卡。

## 四、目录结构

```
roundtable/
├── main.py            FastAPI 入口：路由、WebSocket、静态文件
├── run.py             启动脚本（python run.py [端口]）
├── config.py          所有阈值、文案、提示词（改行为先看这里）
├── models.py          Member / Message / Card / HostAction 数据类
├── store.py           SQLite 读写（rooms / members / messages / cards / minutes）
├── room.py            房间状态机：创建、加入、发言、广播
├── host.py            ★ 核心：decide() 五级规则决定 AI 是否开口
├── llm.py             模型调用、JSON 容错解析、mock 实现、纪要生成
├── minutes.py         纪要组装 + Word 导出（python-docx）
├── static/            前端（原生 HTML/CSS/JS，无框架、无构建）
│   ├── index.html     首页：创建 / 加入
│   ├── room.html      房间页：三栏看板
│   ├── style.css
│   ├── app.js
│   └── room.js
├── tests/
│   ├── run_tests.py   不依赖 pytest 的极简测试运行器
│   ├── test_host.py   ★ 8 个用例，主持人规则是产品的全部逻辑
│   └── test_parse.py  JSON 容错、相似度、抽卡兜底
└── data/              SQLite 数据库与导出的纪要（首次运行自动生成）
```

## 五、五个功能点对应到代码

| 功能 | 在哪 |
| --- | --- |
| 发言均衡仪表盘（环形图 + 标准差） | `store.sum_duration` → `room.balance()` → `room.js: renderDonut` |
| 让麦 / 点名 / 标分歧 / 收尾 | `host.py: decide()`，五级规则 + 10 秒冷却 |
| 观点卡片（主张·证据·疑问·共识） | `llm.extract_card()` → `store.add_card()` → `room.js: renderCards` |
| 分歧检测 | 分歧词计数 → `divergence_hint`；纪要里再做一次正反立场比对 |
| 纪要 + Word 导出 | `minutes.build()` / `minutes.export_docx()` |

## 六、接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/rooms` | 创建房间 `{name, topic}` |
| POST | `/api/rooms/{code}/join` | 加入 `{name}` |
| GET | `/api/rooms/{code}/state` | 全量状态（成员、消息、卡片、均衡度） |
| POST | `/api/rooms/{code}/messages` | 发一条发言 `{member_id, content, duration_ms}` |
| GET | `/api/rooms/{code}/minutes` | 取/生成纪要 |
| GET | `/api/rooms/{code}/minutes/export` | 下载 Word |
| WS | `/ws/rooms/{code}` | 实时推送消息、卡片、主持人提示 |

## 七、跑测试

```bash
cd roundtable
python tests/run_tests.py
```

预期：`通过 17 个，失败 0 个`。改 `host.py` 的规则后先跑一遍，别让演示现场翻车。

## 八、常见问题

**端口被占用**：`python run.py 8124` 换个端口。

**页面样式没更新**：服务端已设置 `Cache-Control: no-store`，直接刷新即可。

**中文在 Windows 终端乱码**：`$env:PYTHONIOENCODING="utf-8"`。

**多人不在同一台电脑上测试**：用内网穿透（如 `npx localtunnel --port 8000`），
或先在会议室同一局域网用 `http://本机IP:8000`。

---

西华师范大学第一届「智元杯」创新设计大赛 · 开发赛道参赛作品
