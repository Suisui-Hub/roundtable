"""纪要生成与 Word 导出。"""
import os
import time

from docx import Document
from docx.shared import Pt
from docx.oxml.ns import qn

import llm
import store
from config import BASE_DIR

EXPORT_DIR = os.path.join(BASE_DIR, "data")


async def build(code: str):
    room = store.get_room_by_code(code)
    if not room:
        return None

    messages = store.list_messages(room["id"])
    cards = store.list_cards(room["id"])
    names = {m["id"]: m["name"] for m in store.list_members(room["id"])}

    data = await llm.make_minutes(messages, cards, names)
    store.save_minutes(room["id"], data)
    store.set_status(room["id"], "closed")
    return data


def _set_font(doc) -> None:
    style = doc.styles["Normal"]
    style.font.name = "宋体"
    style.font.size = Pt(11)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")


def export_docx(code: str):
    """生成 Word 并返回文件路径；没有纪要时返回 None。"""
    room = store.get_room_by_code(code)
    if not room:
        return None

    data = store.latest_minutes(room["id"])
    if not data:
        return None

    doc = Document()
    _set_font(doc)

    doc.add_heading("讨论纪要", level=0)
    doc.add_paragraph(f"议题：{room['topic']}")
    doc.add_paragraph(time.strftime("%Y-%m-%d %H:%M", time.localtime(room["created_at"])))

    doc.add_heading("共识 / 决议", level=1)
    if data.get("decisions"):
        for item in data["decisions"]:
            doc.add_paragraph(item, style="List Bullet")
    else:
        doc.add_paragraph("（本次讨论尚未形成明确共识）")

    doc.add_heading("尚未解决的分歧", level=1)
    if data.get("divergences"):
        for item in data["divergences"]:
            doc.add_paragraph(item.get("point", ""), style="List Bullet")
            sides = " / ".join(item.get("sides", []))
            if sides:
                doc.add_paragraph(f"　双方观点：{sides}")
    else:
        doc.add_paragraph("（暂无）")

    doc.add_heading("待办", level=1)
    if data.get("todos"):
        table = doc.add_table(rows=1, cols=3)
        table.style = "Table Grid"
        header = table.rows[0].cells
        header[0].text = "负责人"
        header[1].text = "事项"
        header[2].text = "时间"
        for todo in data["todos"]:
            cells = table.add_row().cells
            cells[0].text = todo.get("owner", "")
            cells[1].text = todo.get("task", "")
            cells[2].text = todo.get("due", "")
    else:
        doc.add_paragraph("（暂无）")

    os.makedirs(EXPORT_DIR, exist_ok=True)
    path = os.path.join(EXPORT_DIR, f"纪要_{code}.docx")
    doc.save(path)
    return path
