# -*- coding: utf-8 -*-
"""paeg_vocabulary.enrichers.book_term_gate — 本书关键术语识别（LLM 职责 ⭐）。

设计（用户 2026-08-28）：
- 词库（WordBank/CEFR/Zipf）负责"分级提取"——按水平筛选生词
- LLM 负责"本书重要性判断"——哪些词在本书中承担重要作用（核心术语）
- 这些词进入"必定保留库"：无论什么阶段、什么水平的学生都必须呈现

工作流位置：filter 之前（对候选词判断），must_keep 集合传给 filter 豁免。
无 LLM 兜底：domain_term 命中 + 高频（freq ≥ 3 且 zipf ≥ 3）作为弱 must_keep。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set


def judge_book_terms(
    book_title: str,
    candidates: List[Dict[str, Any]],
    chat_fn: Callable,
    top_n: int = 150,
    batch_size: int = 15,
) -> Dict[str, List[str]]:
    """LLM 批量判断本书关键术语。

    candidates: [{headword, freq_count, contexts: [...]}]
    返回：{headword: [理由, ...]}（must_keep 集合 + 理由）
    """
    if not chat_fn or not candidates:
        return {}

    # 只判断词频 Top N（其余低频词不值得 LLM 判断）
    ranked = sorted(candidates, key=lambda c: -(c.get("freq_count", 0)))[:top_n]
    must_keep: Dict[str, List[str]] = {}

    sys_p = (
        "你是一本书的术语分析助手。给定书的标题、候选词及其在书中的出现次数和上下文，"
        "判断哪些词是【本书关键术语】——即在本书中承担核心概念、反复出现的专业术语、"
        "作者论述的关键词。这些词对理解本书至关重要，无论读者水平如何都必须呈现。\n"
        "判定标准：\n"
        "1. 本书学科的核心概念术语（如遗传学书的 allele/phenotype/genotype）\n"
        "2. 作者反复使用的框架性词汇（出现次数高 + 上下文承载论证）\n"
        "3. 普通高频词（the/and/one）和非本书特有词不算\n"
        "输出 JSON：{\"must_keep\": [{\"word\": \"...\", \"reason\": \"一句话理由\"}]}"
    )

    for i in range(0, len(ranked), batch_size):
        batch = ranked[i:i + batch_size]
        usr_p = f"书名：{book_title}\n候选词：\n"
        for c in batch:
            ctx = (c.get("contexts") or [""])[0][:80]
            usr_p += f"- {c.get('headword')}（出现 {c.get('freq_count')} 次）{ctx}\n"
        raw = chat_fn(sys_p, usr_p)
        if not raw:
            continue
        try:
            import json as _json
            import re
            m = re.search(r"\{.*\}", raw, re.S)
            data = _json.loads(m.group(0)) if m else {}
            for item in data.get("must_keep", []):
                w = (item.get("word") or "").strip().lower()
                reason = (item.get("reason") or "").strip()
                if w:
                    must_keep.setdefault(w, []).append(reason[:200])
        except Exception:
            continue

    return must_keep


def fallback_must_keep(candidates: List[Dict[str, Any]],
                       domain_terms: Optional[Set[str]] = None) -> Dict[str, List[str]]:
    """无 LLM 兜底：domain_term 命中 + 高频词（freq≥3 且 zipf≥3）作为弱 must_keep。"""
    out: Dict[str, List[str]] = {}
    domain_terms = domain_terms or set()
    for c in candidates:
        w = (c.get("headword") or "").lower()
        if not w:
            continue
        if w in domain_terms:
            out.setdefault(w, []).append("学科术语（词典命中）")
        elif c.get("freq_count", 0) >= 3 and c.get("global_zipf", 0) >= 3:
            out.setdefault(w, []).append("高频词（启发式保留）")
    return out
