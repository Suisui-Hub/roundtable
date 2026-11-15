"""解析与相似度的单测：模型输出永远是脏的。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm import mock_card, mock_minutes, parse_json, similarity


def test_parse_plain_json():
    assert parse_json('{"kind": "主张", "content": "应该试点"}')["kind"] == "主张"


def test_parse_fenced_json():
    raw = '```json\n{"kind": "证据", "content": "去年出过事故"}\n```'
    assert parse_json(raw)["content"] == "去年出过事故"


def test_parse_with_chatter():
    raw = '好的，结果如下：{"kind": "疑问", "content": "谁负责"} 以上。'
    assert parse_json(raw)["kind"] == "疑问"


def test_parse_garbage_returns_none():
    assert parse_json("模型今天不想干活") is None
    assert parse_json("") is None
    assert parse_json(None) is None


def test_similarity_same_meaning():
    a = "应该先在教室区试点"
    b = "先在教室区试点比较好"
    assert similarity(a, b) > 0.3


def test_similarity_unrelated():
    assert similarity("应该推广", "食堂太挤") < 0.2


def test_mock_card_kinds():
    assert mock_card("是不是应该先试点？")["kind"] == "疑问"
    assert mock_card("我查过数据，去年有 3 起事故")["kind"] == "证据"
    assert mock_card("大家一致认为要先试点")["kind"] == "共识"
    assert mock_card("我觉得应该推广电动车")["kind"] == "主张"
    assert mock_card("嗯")["kind"] == ""


def test_mock_minutes_finds_real_divergence():
    cards = [
        {"kind": "主张", "content": "我觉得应该推广，走路太耽误事"},
        {"kind": "主张", "content": "我还是倾向于禁止，真出事故谁来负责"},
        {"kind": "疑问", "content": "事故的具体类型是什么"},
    ]
    messages = [
        {"role": "user", "member_id": "m1", "content": "你们去查一下去年的事故报告"},
    ]
    data = mock_minutes(messages, cards, {"m1": "小林"})
    assert len(data["divergences"]) == 2          # 一条立场分歧 + 一条未答疑问
    assert len(data["divergences"][0]["sides"]) == 2
    assert data["todos"][0]["owner"] == "小林"
    assert all("但是" not in d for d in data["decisions"])


def test_mock_minutes_skips_turning_points():
    cards = [
        {"kind": "主张", "content": "但是不试点就不知道问题在哪"},
        {"kind": "主张", "content": "那可以先试点再推广"},
    ]
    data = mock_minutes([], cards, {})
    assert data["decisions"] == ["那可以先试点再推广"]
