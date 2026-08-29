# -*- coding: utf-8 -*-
"""paeg_vocabulary — PAEG 词汇表生成插件（§3.116 ⭐ 工具生态可插拔插件）。

功能：书籍 PDF → 结构化语言学习词汇表（英语/德语/法语等）：
- 模块1 全流程工作流引擎（PDF提取→清洗→筛选→补全→渲染）
- 模块2 词汇条目强制信息标准（12 字段：音标/双语释义/词源/例句/短语）
- 模块3 渲染模板（完整复用 Bell Jar 精美 CSS——禁止简化版）
- 模块4 附件产物（学习价值/词频报告/风格分析）
- 模块5 污染处理（OCR 断裂修复 + 例句污染清洗）

生态：独立可插拔 tool 插件 + 主 Agent 可调用 + 可扩展语种/字段/数据源。
"""

from __future__ import annotations

from .registry import VocabularyRegistry
from .executor import execute
from .core.entry import VocabularyEntry, Sense, CandidateWord, validate_entry
from .core.context import VocabularyContext
from .protocols import LLMCallable, PDFReader, NullLLM, NullPDFReader
from .llm_client import chat, EnvLLM, available
from .enrichers import EnricherRegistry, register_default_enrichers
from .cleaners import OCRRepairPipeline, ExampleSanitizer
from .level_matrix import (
    select_cefr_max, filter_by_level, guess_cefr_from_zipf,
    resolve_preset, user_presets, level_matrix_table,
)
# §3.116 ⭐ 语言规范 L0 校对（复用 paeg_lang_style 14.1，缺失优雅降级）
from .lang_style import has_lang_style, apply_l0, apply_l0_to_entry

__version__ = "0.1.0"

# §3.116 ⭐ 导入即注册默认生成器（生态可扩展）
from .registry import VocabularyRegistry
VocabularyRegistry.register_defaults()

__all__ = [
    "VocabularyRegistry", "execute",
    "VocabularyEntry", "Sense", "CandidateWord", "validate_entry",
    "VocabularyContext",
    "LLMCallable", "PDFReader", "NullLLM", "NullPDFReader",
    "chat", "EnvLLM", "available",
    "EnricherRegistry", "register_default_enrichers",
    "OCRRepairPipeline", "ExampleSanitizer",
    "select_cefr_max", "filter_by_level", "guess_cefr_from_zipf",
    "resolve_preset", "user_presets", "level_matrix_table",
    # §3.116 ⭐ 语言规范 L0 校对（复用 paeg_lang_style 14.1）
    "has_lang_style", "apply_l0", "apply_l0_to_entry",
    "__version__",
]
