"""圆桌 RoundTable · 全局配置

所有阈值、文案、模型参数都放这里，改行为不用动逻辑代码。
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "roundtable.db")

# ---------------- 模型 ----------------
API_BASE = os.getenv("RT_API_BASE", "https://api.deepseek.com/v1")
API_KEY = os.getenv("RT_API_KEY", "")
MODEL = os.getenv("RT_MODEL", "deepseek-chat")
USE_MOCK = not API_KEY          # 没填 Key 就用本地假实现，保证随时能跑
LLM_TIMEOUT = 8.0               # 单次请求超时（秒）
CARD_TIMEOUT = 3.0               # 抽卡最多等 3 秒，超时就跳过

# ---------------- 主持策略 ----------------
COOLDOWN = 10.0                 # 两次干预的最小间隔（秒）
STREAK_LIMIT = 3                # 连续发言几条触发让麦
SILENCE_SECONDS = 180           # 沉默多少秒触发点名
CONVERGE_SECONDS = 480          # 讨论多少秒提示收敛
CONVERGE_MIN_MESSAGES = 12      # 收敛还要求消息数够
DIVERGENCE_WORDS = ["但是", "不过", "我不同意", "反对", "不一定", "可是", "然而", "未必"]
DIVERGENCE_HIT_LIMIT = 2        # 命中几次后提示分歧

# ---------------- 均衡度配色 ----------------
BALANCE_GREEN = 8               # 标准差 < 8 算均衡
BALANCE_YELLOW = 15             # 8~15 一般，超过 15 失衡

COLORS = ["#3B6CF6", "#17A673", "#F0A32A", "#8B5CF6", "#EA5455"]

# ---------------- 兜底文案（模型挂了就用这些） ----------------
FALLBACK = {
    "balance_hint": "{name}已经连说{streak}次了，把时间让一点给还没说话的人。",
    "invite": "{name}，你还没说，怎么看？不同意也可以说。",
    "divergence_hint": "这里好像出现了分歧，先停一下，确认你们是不是在说同一件事。",
    "converge_hint": "已经聊了一会儿，要收一下吗？现在生成纪要，还是再讨论五分钟？",
}

# ---------------- 提示词 ----------------
PROMPT_EXTRACT = """你是讨论记录员。从下面这句发言中抽取一个观点，只输出 JSON，不要任何解释。

字段：
- kind：只能是 主张 / 证据 / 疑问 / 共识 之一
- content：不超过 25 字，保留发言人的原话风格
- confidence：0 到 1 的置信度

如果这句话没有实质观点（比如“嗯”“好”“我先想想”），返回 {{"kind":"","content":"","confidence":0}}。

发言：{text}"""

PROMPT_POLISH = """你是一场 3 到 5 人小组讨论的主持人。你只做四件事：追问、点人、标分歧、收尾。
硬性要求：
1. 绝对不给结论、不站队、不替人回答问题。
2. 一次只说一件事，不超过 60 字。
3. 口语化，像同学之间说话，不用“首先其次最后”。

本次动作：{action_type}
原因：{reason}
最近三轮对话：{context}

只输出主持人要说的那一句话。"""

PROMPT_MINUTES = """根据下面的讨论记录，输出讨论纪要，只输出 JSON，不要解释：
{{"decisions": ["已达成的共识"], "divergences": [{{"point": "分歧点", "sides": ["一方观点", "另一方观点"]}}], "todos": [{{"owner": "负责人姓名", "task": "具体待办", "due": "时间"}}]}}
没有对应内容就给空数组，不要编造。

讨论记录：
{transcript}

观点卡片：
{cards}"""
