# -*- coding: utf-8 -*-
"""paeg_vocabulary.normalization — 词形归一化策略（§3.116 ⭐ Oracle 方案）。

形态学双层判断：屈折 vs 派生。
- **屈折归一化**（POS 不变）：-ed/-ing/-s/过去式/复数/比较级 → 安全归一化 lemma
- **派生保留原形**（POS 改变 OR 派生后缀）：-tion/-ment/-ness/-ity 等 → 表面形作为独立词条
  （如 abandonment 是海德格尔学术术语，不是 abandon 的普通变形）
- **学术术语促进**（与上解耦）：定义句/标题/高 TF-IDF → 独立标记术语

避免 §3.108 反模式：按后缀类别写规则（非词表），覆盖整类派生名词术语。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# 派生后缀（高确定性——命中即保留原形）
_DERIVATIONAL_SUFFIXES = (
    # 名词化（-tion/-ment/-ness/-ity 等——学术术语高频）
    "tion", "sion", "ment", "ness", "ity", "ance", "ence", "ization",
    "isation", "ism", "ology", "ship", "hood", "ery",
    # 形容词化
    "able", "ible", "ous", "ive", "ical",
    # 副词化（部分）
    "ness", "ment",
)

# 屈折后缀（安全归一化——POS 不变时）
_INFLECTIONAL_SUFFIXES = ("ed", "ing", "s", "es")

# 学术术语信号阈值
TERM_TFIDF_THRESHOLD = 0.5
TERM_FREQ_THRESHOLD = 5  # 书中出现 ≥5 次视为候选术语


@dataclass
class FormDecision:
    """词形决策结果。"""
    surface: str                      # 书中表面形
    lemma: str                        # 词元（spaCy）
    pos: str                          # 词性
    is_lexically_independent: bool    # 是否独立词条（保留原形，不折叠回 lemma）
    is_book_term: bool                # 是否本书学术术语
    term_evidence: List[str] = field(default_factory=list)
    reason: str = ""                  # 决策理由（可解释）

    def to_dict(self) -> Dict:
        return {
            "surface": self.surface, "lemma": self.lemma, "pos": self.pos,
            "is_lexically_independent": self.is_lexically_independent,
            "is_book_term": self.is_book_term,
            "term_evidence": self.term_evidence, "reason": self.reason,
        }


def _has_derivational_suffix(word: str) -> bool:
    """检测派生后缀（len 阈值防假阳性：fly/try 等）。"""
    low = word.lower()
    for suf in _DERIVATIONAL_SUFFIXES:
        if low.endswith(suf) and len(low) > len(suf) + 3:
            return True
    return False


def _is_inflectional(word: str, lemma: str) -> bool:
    """检测屈折变化（POS 不变时安全归一化）。"""
    if word == lemma:
        return True
    low, lemlow = word.lower(), lemma.lower()
    for suf in _INFLECTIONAL_SUFFIXES:
        if low.endswith(suf) and low.startswith(lemlow):
            return True
    # 不规则屈折（meant/went/children——由 spaCy lemma 判断，这里靠 lemma 一致性）
    return False


def should_preserve_form(surface: str, lemma: str, pos: str,
                         lemma_pos: Optional[str] = None,
                         ctx: Optional[Dict] = None) -> FormDecision:
    """词形归一化决策（Oracle 方案 ⭐）。

    Args:
        surface: 书中表面形（如 abandonment）。
        lemma: spaCy lemma（如 abandon）。
        pos: 表面形词性（如 NOUN）。
        lemma_pos: lemma 词性（如 VERB）。
        ctx: 上下文信号 {in_definition, in_heading, freq, tfidf, italic, capitalized}。

    Returns:
        FormDecision：是否保留原形 + 是否学术术语。
    """
    ctx = ctx or {}
    surface = surface.strip()
    lemma = lemma.strip()
    reason_parts = []
    independent = False

    # ── 判断 1：派生 vs 屈折 ──
    pos_diff = (lemma_pos is not None and pos != lemma_pos)
    has_deriv = _has_derivational_suffix(surface)
    is_inflect = _is_inflectional(surface, lemma)

    if pos_diff:
        # POS 改变（VERB→NOUN 等）→ 可能是独立词条（abandon→abandonment）
        independent = True
        reason_parts.append(f"派生：POS {lemma_pos or '?'}→{pos}")
    elif has_deriv and not is_inflect:
        # 派生后缀 + 非屈折 → 独立词条
        independent = True
        reason_parts.append("派生后缀")
    elif is_inflect:
        # 屈折变化 → 归一化（保留 lemma）
        independent = False
        reason_parts.append("屈折变化")

    # ── 判断 2：学术术语促进（与上解耦）──
    is_term = False
    evidence = []
    if ctx.get("in_definition"):
        is_term = True
        evidence.append("定义句")
    if ctx.get("in_heading"):
        is_term = True
        evidence.append("标题")
    if ctx.get("tfidf", 0) >= TERM_TFIDF_THRESHOLD:
        is_term = True
        evidence.append("高TF-IDF")
    if ctx.get("freq", 0) >= TERM_FREQ_THRESHOLD:
        is_term = True
        evidence.append(f"高频({ctx.get('freq')}次)")
    if ctx.get("italic"):
        is_term = True
        evidence.append("斜体（外来术语）")
    if ctx.get("capitalized") and pos == "NOUN":
        is_term = True
        evidence.append("句中大写（专名）")

    # 若命中学术术语信号 → 即使屈折也保留表面形（重要术语）
    if is_term and not independent:
        independent = True  # 术语提升：表面形作为独立词条
        reason_parts.append("学术术语促进")

    return FormDecision(
        surface=surface, lemma=lemma, pos=pos,
        is_lexically_independent=independent,
        is_book_term=is_term,
        term_evidence=evidence,
        reason="；".join(reason_parts) or "普通词",
    )


def build_term_context(tokens: List[Dict], idx: int) -> Dict:
    """从 token 流构建上下文信号（定义句/标题/频率/斜体/大写）。

    tokens: 带 {text, lemma, pos, in_definition, in_heading, freq, tfidf,
             italic, capitalized} 的列表。
    """
    if idx < 0 or idx >= len(tokens):
        return {}
    t = tokens[idx]
    return {
        "in_definition": t.get("in_definition", False),
        "in_heading": t.get("in_heading", False),
        "freq": t.get("freq", 0),
        "tfidf": t.get("tfidf", 0),
        "italic": t.get("italic", False),
        "capitalized": t.get("capitalized", False),
    }


# ═══════════════════════════════════════════════════════════
# P2 ⭐ 归一化 × 分位联动（用户原则 4：哪些标准化、哪些保留原形）
# ═══════════════════════════════════════════════════════════
def decision_to_entry_key(decision: FormDecision) -> str:
    """归一化决策 → 词条 key（参与分位/筛选的规范形）。

    - 屈折归一化（is_lexically_independent=False）→ lemma（折叠）
    - 派生保留/学术术语（True）→ surface（保留原形）
    """
    if decision.is_lexically_independent:
        return decision.surface.strip().lower()
    return decision.lemma.strip().lower() or decision.surface.strip().lower()


def is_important_decision(decision: FormDecision) -> bool:
    """归一化决策 → 是否"本书重要"（第二标准信号）。

    is_book_term（学术术语：定义句/标题/高TF-IDF/高频/斜体/专名）
    ⊂ is_important。P4 筛选时：Q ≥ U OR is_important。
    """
    return decision.is_book_term


def decision_quantile(decision: FormDecision) -> float:
    """归一化决策词的统一分位 Q（P1 分位引擎联动）。

    独立词条（surface）按 surface 算；折叠词条按 lemma 算。
    Returns: 0-1 分位（越高越难）。
    """
    from .quantile_engine import compute_q
    key = decision_to_entry_key(decision)
    return compute_q(key)
