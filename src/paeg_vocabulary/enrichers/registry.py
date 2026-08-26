# -*- coding: utf-8 -*-
"""paeg_vocabulary.enrichers.registry — 补全器注册表（§3.116 可扩展 ⭐）。"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional


class EnricherRegistry:
    """词汇补全器注册表（字段 → 补全器，可扩展）。"""

    _enrichers: Dict[str, Callable] = {}

    @classmethod
    def register(cls, field: str, fn: Callable) -> bool:
        cls._enrichers[field] = fn
        return True

    @classmethod
    def get(cls, field: str) -> Optional[Callable]:
        return cls._enrichers.get(field)

    @classmethod
    def all(cls) -> Dict[str, Callable]:
        return dict(cls._enrichers)

    @classmethod
    def fields(cls) -> list:
        return sorted(cls._enrichers.keys())


def register_default_enrichers() -> None:
    """注册默认补全器（ipa/gloss/example/etymology/collocation/cefr/freq）。"""
    from .ipa_enricher import IpaEnricher
    from .llm_enricher import enrich_entry_with_llm

    _ipa = IpaEnricher()
    EnricherRegistry.register("ipa", lambda w: _ipa.enrich(w))

    def _llm_wrapper(entry):
        # LLM 补全：gloss/example/etymology/collocations
        return enrich_entry_with_llm(entry)

    EnricherRegistry.register("llm_batch", _llm_wrapper)


# 导入时注册默认
register_default_enrichers()
