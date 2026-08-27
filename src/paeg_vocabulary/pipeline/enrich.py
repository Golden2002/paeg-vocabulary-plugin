# -*- coding: utf-8 -*-
"""paeg_vocabulary.pipeline.enrich — 阶段4：信息补全（P5 ⭐ 重构）。

P5 架构（Oracle）：
1. **wordbank 离线优先**：音标（CMU 12.6万词）/ 释义 / CEFR 等级——确定性数据源直接查
2. **batch_llm 批量补全**：20 词/批 + JSON schema + 断点续跑（替代逐词调用）
3. **collocations 原著提取**：N-gram + PMI 从书中提取固定搭配
4. 逐词 LLM 仅作兜底（wordbank 无数据时）

词条 12 字段：headword/pos/ipa/gloss_bilingual/examples/lemma +
etymology/morpheme/senses/collocations + cefr_level/freq_rank + phenomena + book_sense
"""

from __future__ import annotations

from typing import List, Optional

from ..core.context import VocabularyContext
from ..core.entry import VocabularyEntry
from ..enrichers.ipa_enricher import IpaEnricher
# §3.116 ⭐ 语言现象识别（熟词生义/固定搭配/俚语）
from ..enrichers.idiom_enricher import detect_phenomena
# P5 ⭐ 本地专业词库（离线音标/释义/等级）
from ..wordbank import WordBank
# P5 ⭐ LLM 批量补全（20 词/批）
from ..enrichers.batch_llm import batch_enrich
# P5 ⭐ 原著搭配提取（N-gram + PMI）
from ..collocations import extract_collocations, collocations_for_word


def enrich_entries(ctx: VocabularyContext,
                   chat_fn: Optional[object] = None,
                   book_title: str = "",
                   book_author: str = "",
                   domains: Optional[List[str]] = None) -> VocabularyContext:
    """阶段 4：candidates → entries（12 字段补全，P5 离线优先 + 批量 LLM）。

    §3.116 ⭐ book_title/book_author：LLM 生成"本书含义"义项标注。
    §3.116 ⭐ domains：学科术语辞典（现象学/分子生物/物理/化学等）。
    """
    if not ctx.candidates:
        ctx.errors.append("无候选词（阶段3未执行）")
        return ctx

    # ── 0. 原著搭配提取（全书级——一次提取，按词检索）──
    corpus = getattr(ctx, "clean_sentences", None)
    if not corpus and getattr(ctx, "clean_corpus", None):
        # 从清洗词流重建句子（退化：按词流整体）
        try:
            corpus = [" ".join(t.text for t in ctx.clean_corpus[:200])]
        except Exception:
            corpus = []
    all_colls = extract_collocations(corpus or [], n=2, min_count=2, top_n=60) if corpus else []

    wb = WordBank(domains=domains)
    _ipa_fallback = IpaEnricher()

    # ── 1. 构建词条（wordbank 离线数据优先）──
    entries: List[VocabularyEntry] = []
    max_entries = getattr(ctx, "max_entries", 0) or len(ctx.candidates)
    for cand in ctx.candidates[:max_entries if max_entries > 0 else None]:
        wb_r = wb.lookup(cand.headword)

        entry = VocabularyEntry(
            headword=cand.headword,
            pos=cand.pos or wb_r.get("pos") or "",
            lemma=cand.lemma,
            freq_rank=cand.freq_count,
            cefr_level=cand.cefr_guess or wb_r.get("cefr") or "",
            source_book=book_title or str(ctx.pdf_path or ""),
        )
        # 音标：CMU 离线优先 → IpaEnricher 兜底
        entry.ipa = {}
        if wb_r.get("ipa"):
            entry.ipa["en_us"] = wb_r["ipa"]
        else:
            _fb = _ipa_fallback.enrich(cand.headword)
            if _fb:
                entry.ipa.update(_fb)
        # 释义：CEFR 词库离线优先（en），zh 由 LLM 补
        if wb_r.get("gloss_en"):
            entry.gloss_bilingual = {"en": wb_r["gloss_en"], "zh": ""}
        # 学科术语：domain 命中 → 标记术语（筛选豁免信号）
        if wb_r.get("domain_term"):
            entry.phenomena.setdefault("domain_term", [wb_r["domain_term"].get("gloss_zh", "")])
        # 原书例句（上下文优先）
        if cand.contexts:
            entry.examples = [{"en": c[:200], "zh": ""} for c in cand.contexts[:2]]
        # 语言现象识别
        _ctx_text = " ".join(cand.contexts[:3])
        entry.phenomena.update(detect_phenomena(cand.headword, _ctx_text))
        # 搭配：原著提取结果按词检索
        entry.collocations = [c["phrase"] for c in collocations_for_word(all_colls, cand.headword)][:4]

        entries.append(entry)

    # ── 2. LLM 批量补全（6 词/批——完整字段 JSON 防截断；断点续跑）──
    # P7 ⭐ 实测：10 词/批 max_tokens 4000 截断（completion_tokens=4000 达上限）
    # 6 词/批 × 每词 ~600 token ≈ 3600 < 4000 安全
    if chat_fn is not None and entries:
        entries = batch_enrich(entries, chat_fn, batch_size=6,
                               book_title=book_title, book_author=book_author)

    ctx.entries = entries
    ctx.mark_completed("enrich")
    return ctx
