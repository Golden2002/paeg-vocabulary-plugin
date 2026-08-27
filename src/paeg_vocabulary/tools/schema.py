# -*- coding: utf-8 -*-
"""paeg_vocabulary.tools.schema — 标准化工具契约（MCP 风格 JSON Schema）。

用户需求（§3.116 ⭐）："要用标准化接口，便于不同开发者接入自己的项目（参考mcp标准化）"

每个工具声明：name/description/inputs(schema)/outputs(schema)——
开发者可自动发现工具能力（类似 MCP tools/list + tools/call）。
"""

from __future__ import annotations

from typing import Any, Dict, List

# ═══════════════════════════════════════════════════════════
# 工具 schema 声明表
# ═══════════════════════════════════════════════════════════
TOOL_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "generate_vocabulary": {
        "name": "generate_vocabulary",
        "description": "生成词汇表：书籍 PDF → 结构化词汇表（音标/释义/词源/例句/短语/搭配/难度分级）。完整工作流：提取→清洗→分位筛选→多字段补全→渲染。",
        "inputs": {
            "type": "object",
            "properties": {
                "pdf_path": {"type": "string", "description": "书籍 PDF 路径"},
                "lang": {"type": "string", "default": "en", "description": "目标语言（en/de/fr/es）"},
                "user_filter": {
                    "type": "object",
                    "description": "筛选规则（用户水平档位）",
                    "properties": {
                        "preset": {"type": "string", "description": "预设档位：ielts-6.5/7.5/8.0、toefl-100、kaoyan-70 等"},
                        "exam": {"type": "string", "description": "考试体系：ielts/toefl/cet4/cet6/kaoyan/tem4/tem8/gaokao"},
                        "score": {"type": "number", "description": "考试分数"},
                        "vocab_size": {"type": "number", "description": "自述词汇量"},
                        "domains": {"type": "array", "items": {"type": "string"},
                                    "description": "学科辞典：philosophy/biology/physics/chemistry 等"},
                        "max_entries": {"type": "integer", "default": 2500, "description": "词条上限"},
                    },
                },
            },
            "required": ["pdf_path"],
        },
        "outputs": {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "html_path": {"type": "string", "description": "词汇表 HTML 路径"},
                "pdf_path": {"type": "string", "description": "词汇表 PDF 路径"},
                "entries_count": {"type": "integer"},
                "candidates_count": {"type": "integer"},
                "accessories": {"type": "object", "description": "附件（学习价值/词频/风格分析/高明词）"},
                "u_level": {"type": "number", "description": "用户水平分位"},
                "errors": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    "lookup_word": {
        "name": "lookup_word",
        "description": "离线词库查询：音标（CMU）/释义（CEFR 词表）/CEFR 等级（Oxford）/学科术语（kaikki）——多源整合消歧。",
        "inputs": {
            "type": "object",
            "properties": {
                "word": {"type": "string", "description": "查询词"},
                "domains": {"type": "array", "items": {"type": "string"},
                            "description": "学科范围（默认全学科）"},
            },
            "required": ["word"],
        },
        "outputs": {
            "type": "object",
            "properties": {
                "word": {"type": "string"},
                "ipa": {"type": "string", "description": "IPA 音标"},
                "gloss_en": {"type": "string", "description": "英文释义"},
                "cefr": {"type": "string", "description": "CEFR 等级"},
                "domain_term": {"type": "object", "description": "学科术语（含 gloss/domain）"},
                "sources": {"type": "object", "description": "数据来源追踪"},
            },
        },
    },
    "extract_collocations": {
        "name": "extract_collocations",
        "description": "从文本提取固定搭配/短语（N-gram + PMI 显著性）。",
        "inputs": {
            "type": "object",
            "properties": {
                "corpus": {"type": "array", "items": {"type": "string"},
                           "description": "语料句子列表"},
                "n": {"type": "integer", "default": 2, "description": "n-gram 阶"},
                "min_count": {"type": "integer", "default": 2, "description": "最低频次"},
                "top_n": {"type": "integer", "default": 30},
            },
            "required": ["corpus"],
        },
        "outputs": {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "collocations": {"type": "array", "items": {"type": "object"}},
            },
        },
    },
    "quantile_of": {
        "name": "quantile_of",
        "description": "查询词的难度分位 Q（0-1，统一分位空间——考试/词频映射）。",
        "inputs": {
            "type": "object",
            "properties": {
                "word": {"type": "string"},
                "cefr_hint": {"type": "string", "description": "已知 CEFR 等级（可选）"},
            },
            "required": ["word"],
        },
        "outputs": {
            "type": "object",
            "properties": {
                "q": {"type": "number", "description": "难度分位 0-1"},
                "meta": {"type": "object", "description": "分量信号（zipf_q/family_q/cefr_q）"},
            },
        },
    },
    "list_languages": {
        "name": "list_languages",
        "description": "支持的目标语言列表（可扩展）。",
        "inputs": {"type": "object", "properties": {}},
        "outputs": {"type": "object", "properties": {"ok": {"type": "boolean"}, "languages": {"type": "array"}}},
    },
    "list_generators": {
        "name": "list_generators",
        "description": "可用生成器清单（可扩展）。",
        "inputs": {"type": "object", "properties": {}},
        "outputs": {"type": "object", "properties": {"ok": {"type": "boolean"}, "generators": {"type": "array"}}},
    },
    "validate_entry": {
        "name": "validate_entry",
        "description": "校验词汇条目 L1 必填字段。",
        "inputs": {
            "type": "object",
            "properties": {
                "headword": {"type": "string"},
                "pos": {"type": "string"},
                "ipa_json": {"type": "string", "default": "{}"},
                "gloss_json": {"type": "string", "default": "{}"},
            },
            "required": ["headword"],
        },
        "outputs": {"type": "object", "properties": {"ok": {"type": "boolean"}, "missing": {"type": "array"}}},
    },
    "clean_examples": {
        "name": "clean_examples",
        "description": "例句污染清洗（参考文献/脚注/页码/页眉页脚剔除）。",
        "inputs": {
            "type": "object",
            "properties": {"examples_json": {"type": "string", "default": "[]"}},
        },
        "outputs": {"type": "object", "properties": {"ok": {"type": "boolean"}, "cleaned": {"type": "array"}}},
    },
    "bank_coverage": {
        "name": "bank_coverage",
        "description": "本地词库覆盖统计（自检）。",
        "inputs": {"type": "object", "properties": {}},
        "outputs": {"type": "object", "properties": {"ok": {"type": "boolean"}, "coverage": {"type": "object"}}},
    },
}


def list_tool_schemas() -> List[Dict[str, Any]]:
    """全部工具 schema（MCP tools/list 等价）。"""
    return list(TOOL_SCHEMAS.values())


def get_tool_schema(name: str) -> Dict[str, Any]:
    """单个工具 schema。"""
    return TOOL_SCHEMAS.get(name, {})


def call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """统一工具调用（MCP tools/call 等价——JSON 契约，绝不抛异常）。"""
    from ..executor import execute
    import json as _json
    try:
        raw = execute(name, arguments)
        try:
            parsed = _json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            parsed = {"ok": True, "result": raw}
        # executor 返回 ok=False（未知工具/参数错误）→ 透传
        if isinstance(parsed, dict) and parsed.get("ok") is False:
            return {"ok": False, "tool": name, "error": parsed.get("error", "调用失败")}
        return {"ok": True, "tool": name, "result": parsed}
    except Exception as e:
        return {"ok": False, "tool": name, "error": str(e)[:300]}
