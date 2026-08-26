# -*- coding: utf-8 -*-
"""paeg_vocabulary.enrichers — 词汇信息补全（§3.116 模块2 ⭐）。

EnricherRegistry 可扩展注册表（生态要求：新增字段/数据源即注册）。

字段补全（12 字段）：
- headword/pos/lemma：spaCy 解析（阶段2/3 已得）
- ipa：CMU dict + espeak-ng 兜底（多口音）
- gloss_bilingual：LLM 生成双语释义
- examples：原书上下文优先（+ LLM 补全多义项例句）
- etymology：LLM 生成词源（etymonline 风格）
- collocations：LLM 生成短语搭配
- cefr_level/freq_rank：wordfreq 计算

补全方式：LLM 注入（chat_fn）+ 确定性数据源（CMU/wordfreq）混合。
"""

from .registry import EnricherRegistry, register_default_enrichers
from .ipa_enricher import IpaEnricher
from .llm_enricher import LLMEnricher, enrich_entry_with_llm

__all__ = ["EnricherRegistry", "register_default_enrichers",
           "IpaEnricher", "LLMEnricher", "enrich_entry_with_llm"]
