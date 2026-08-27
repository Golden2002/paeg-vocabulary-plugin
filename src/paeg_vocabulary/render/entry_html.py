# -*- coding: utf-8 -*-
"""paeg_vocabulary.render.entry_html — P6 ⭐ 词条 HTML 渲染（FIELD_RENDERERS 驱动）。

L1 完整性门：渲染前校验——不完整词条不渲染（返回空），杜绝空词条污染 HTML。
"""

from __future__ import annotations

from ..core.entry import VocabularyEntry
from .field_renderers import (
    FIELD_RENDERERS, l1_missing_fields, render_entry,
)

# 渲染字段顺序（控制词条内布局）
_RENDER_ORDER = [
    "headword", "ipa", "gloss", "senses", "etymology",
    "morpheme", "phenomena", "examples", "collocations",
]


def entry_to_html(e: VocabularyEntry) -> str:
    """词条 → HTML（L1 完整性门拦截不完整词条）。

    §3.116 ⭐ 修复：headword-only 空词条不进入渲染（此前 6784 headword vs 3819 gloss）。
    """
    if not e.headword:
        return ""
    if l1_missing_fields(e):
        return ""   # L1 门：不完整词条不渲染

    parts = []
    for field in _RENDER_ORDER:
        try:
            html = render_entry(field, e)
        except KeyError:
            continue  # 未注册字段跳过（不阻塞）
        if html:
            parts.append(html)
    return f'<div class="entry">\n  ' + "\n  ".join(parts) + "\n</div>"


def entries_to_html(entries) -> str:
    """条目列表 → HTML（过滤不完整词条）。"""
    return "\n".join(h for h in (entry_to_html(e) for e in entries) if h)
