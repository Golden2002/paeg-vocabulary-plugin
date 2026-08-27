# -*- coding: utf-8 -*-
"""paeg_vocabulary.tools — 标准化工具层（MCP 风格 schema 驱动）。"""
from .schema import (
    TOOL_SCHEMAS, list_tool_schemas, get_tool_schema, call_tool,
)

__all__ = ["TOOL_SCHEMAS", "list_tool_schemas", "get_tool_schema", "call_tool"]
