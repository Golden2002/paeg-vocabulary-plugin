# -*- coding: utf-8 -*-
"""paeg_vocabulary.protocols — 宿主依赖抽象（§3.116 生态可扩展 ⭐）。

镜像 paeg-teaching-materials protocols——零宿主依赖：
- LLMCallable：LLM 调用抽象（词汇补全）
- PDFReader：PDF 提取抽象（宿主可注入 lib/ingest/readers）
"""

from __future__ import annotations

from typing import Any, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class LLMCallable(Protocol):
    """LLM 调用抽象。"""

    def __call__(self, system: str, user: str, *, max_tokens: int = 2000,
                 temperature: float = 0.7) -> str:
        ...


class NullLLM:
    """Null 实现（弱模式：不调用 LLM，保留规则层）。"""

    def __call__(self, system: str, user: str, *, max_tokens: int = 2000,
                 temperature: float = 0.7) -> str:
        return ""


@runtime_checkable
class PDFReader(Protocol):
    """PDF 提取抽象。"""

    def read(self, pdf_path: str) -> str:
        ...


class NullPDFReader:
    """Null 实现（返回空）。"""

    def read(self, pdf_path: str) -> str:
        return ""


# 默认 Null 单例
DEFAULT_LLM: LLMCallable = NullLLM()
DEFAULT_READER: PDFReader = NullPDFReader()
