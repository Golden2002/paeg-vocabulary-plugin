# -*- coding: utf-8 -*-
"""paeg_vocabulary.pipeline.enrich — 阶段4：信息补全（§3.116 ⭐）。

对候选词逐个补全 12 字段（EnricherRegistry 路由 + LLM sub-agent）。
"""

from __future__ import annotations

from typing import Optional

from ..core.context import VocabularyContext
from ..core.entry import VocabularyEntry
from ..enrichers.registry import EnricherRegistry
from ..enrichers.ipa_enricher import IpaEnricher
from ..enrichers.llm_enricher import enrich_entry_with_llm
# §3.116 ⭐ 语言现象识别（熟词生义/固定搭配/俚语）
from ..enrichers.idiom_enricher import detect_phenomena


def enrich_entries(ctx: VocabularyContext,
                   chat_fn: Optional[object] = None,
                   book_title: str = "",
                   book_author: str = "") -> VocabularyContext:
    """阶段 4：candidates → entries（12 字段补全）。

    §3.116 ⭐ book_title/book_author：传入 LLM 生成"本书含义"义项标注。
    """
    if not ctx.candidates:
        ctx.errors.append("无候选词（阶段3未执行）")
        return ctx

    _ipa = IpaEnricher()
    entries = []
    # §3.116 ⭐ 长词汇表：默认全部候选补全（可配置 max_entries 上限）
    max_entries = getattr(ctx, "max_entries", 0) or len(ctx.candidates)
    for cand in ctx.candidates[:max_entries if max_entries > 0 else None]:
        entry = VocabularyEntry(
            headword=cand.headword,
            pos=cand.pos,
            lemma=cand.lemma,
            freq_rank=cand.freq_count,
            cefr_level=cand.cefr_guess,
            source_book=book_title or str(ctx.pdf_path or ""),
        )
        # 1. 音标（确定性）
        entry.ipa = _ipa.enrich(cand.headword)
        # 2. 原书例句（从上下文提取——此处简化：标记待补）
        if cand.contexts:
            entry.examples = [{"en": c[:200], "zh": ""} for c in cand.contexts[:2]]
        # 3. §3.116 ⭐ 语言现象识别（熟词生义/固定搭配/俚语 → 筛选豁免信号）
        _ctx_text = " ".join(cand.contexts[:3])
        entry.phenomena = detect_phenomena(cand.headword, _ctx_text)
        # 4. LLM 补全（双语释义/词源/词根词缀/义项/本书含义/短语）
        if chat_fn is not None:
            entry = enrich_entry_with_llm(entry, chat_fn,
                                          book_title=book_title, book_author=book_author)
        entries.append(entry)

    ctx.entries = entries
    ctx.mark_completed("enrich")
    return ctx
