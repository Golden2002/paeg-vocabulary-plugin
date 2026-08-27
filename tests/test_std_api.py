# -*- coding: utf-8 -*-
"""P7 ⭐ 标准化接口测试（MCP 风格：工具 schema + 统一调用）。"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from paeg_vocabulary.tools.schema import (
    TOOL_SCHEMAS, list_tool_schemas, get_tool_schema, call_tool,
)
from paeg_vocabulary.executor import execute


# ── R1: 工具 schema 完整性 ──
def test_schemas_exist():
    """核心工具 schema 声明齐全。"""
    names = list_tool_schemas()
    assert len(names) >= 6
    assert any(t["name"] == "generate_vocabulary" for t in names)
    assert any(t["name"] == "lookup_word" for t in names)


def test_schema_structure():
    """每工具含 name/description/inputs/outputs（MCP 标准）。"""
    for t in list_tool_schemas():
        assert t["name"], "工具名必填"
        assert t["description"], "描述必填"
        assert "inputs" in t, "inputs schema 必填"
        assert "outputs" in t, "outputs schema 必填"


def test_generate_schema_required():
    """generate_vocabulary 要求 pdf_path。"""
    g = get_tool_schema("generate_vocabulary")
    assert "pdf_path" in g["inputs"]["required"]


# ── R2: 统一工具调用（JSON 契约不抛异常）──
def test_call_tool_unknown():
    """未知工具 → 返回 ok=False 而非抛异常。"""
    r = call_tool("nonexistent_tool", {})
    assert r["ok"] is False


def test_call_tool_lookup():
    """lookup_word 调用（离线词库）。"""
    r = call_tool("lookup_word", {"word": "life"})
    assert r["ok"] is True


def test_call_tool_quantile():
    """quantile_of 调用（难度分位——result 已解析 dict）。"""
    r = call_tool("quantile_of", {"word": "life"})
    assert r["ok"] is True
    d = r["result"]
    assert 0 <= d["q"] <= 1


def test_call_tool_collocations():
    """extract_collocations 调用。"""
    r = call_tool("extract_collocations", {"corpus": ["cell membrane regulates",
                                                       "cell membrane is essential"]})
    assert r["ok"] is True


def test_call_tool_bank_coverage():
    """bank_coverage 调用。"""
    r = call_tool("bank_coverage", {})
    assert r["ok"] is True


# ── R3: executor 新工具直调 ──
def test_executor_lookup_word():
    """executor 直调 lookup_word。"""
    import json as _json
    r = _json.loads(execute("lookup_word", {"word": "phenomenology"}))
    assert r["ok"] is True
    assert r.get("ipa") or r.get("gloss_en") or r.get("domain_term")
