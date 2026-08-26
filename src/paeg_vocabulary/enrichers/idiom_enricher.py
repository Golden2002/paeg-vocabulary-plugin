# -*- coding: utf-8 -*-
"""paeg_vocabulary.enrichers.idiom_enricher — 熟词生义/固定搭配/俚语识别（§3.116 ⭐ 用户新增）。

词汇筛选不能只看难度——以下语言现象也是"重要"信号：
1. **熟词生义**：常见词在材料中的特殊义项（如 spring 教材中作"弹簧"而非"春天"）
2. **固定搭配**：材料中的常用搭配（break down / look forward to）
3. **俚语/惯用语**：材料中的口语化表达

识别后标记 entry.phenomena，供筛选豁免（与 MIS 重要性结合）。
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

# 常见熟词生义（常用词 → 特殊义项语境线索）
_POLYSEMY_HINTS: Dict[str, List[str]] = {
    "spring": ["弹簧", "泉水", "spring"],
    "mine": ["矿井", "地雷", "mine"],
    "current": ["电流", "水流", "current"],
    "pound": ["英镑", "敲打", "pound"],
    "bark": ["树皮", "狗叫", "bark"],
    "watch": ["手表", "看守", "watch"],
    "right": ["权利", "右边", "right"],
    "kind": ["种类", "仁慈的", "kind"],
    "mean": ["平均数", "意味着", "mean"],
    "round": ["回合", "圆的", "round"],
    "book": ["预定", "书", "book"],
    "plant": ["工厂", "植物", "plant"],
}

# 常见固定搭配
_COLLOCATIONS: List[str] = [
    "break down", "look forward to", "give up", "take off", "carry out",
    "come across", "figure out", "point out", "turn out", "set up",
    "bring up", "call off", "put off", "run out of", "make up",
    "look up", "give in", "work out", "turn on", "turn off",
]

# 常见俚语/惯用语
_SLANG: List[str] = [
    "a piece of cake", "break a leg", "hit the road", "under the weather",
    "once in a blue moon", "cost an arm and a leg", "let the cat out of the bag",
    "raining cats and dogs", "spill the beans", "on cloud nine",
]


def detect_polysemy(word: str) -> Optional[str]:
    """检测熟词生义（词在熟词生义表中）。返回特殊义项说明。"""
    hints = _POLYSEMY_HINTS.get(word.lower())
    if hints and len(hints) > 1:
        return "熟词生义：常见词在本材料中可能作特殊义项（" + " / ".join(hints) + "）"
    return None


def detect_collocation(text: str) -> List[str]:
    """检测固定搭配（文本中的搭配短语）。"""
    hits = []
    low = text.lower()
    for coll in _COLLOCATIONS:
        if coll in low:
            hits.append(coll)
    return hits


def detect_slang(text: str) -> List[str]:
    """检测俚语/惯用语。"""
    hits = []
    low = text.lower()
    for s in _SLANG:
        if s in low:
            hits.append(s)
    return hits


def detect_phenomena(word: str, context: str = "") -> Dict[str, List[str]]:
    """综合检测词的语言现象（熟词生义/固定搭配/俚语）。

    Returns:
        {"polysemy": [...], "collocations": [...], "slang": [...]}
    """
    out: Dict[str, List[str]] = {"polysemy": [], "collocations": [], "slang": []}
    # 熟词生义（按词检测）
    p = detect_polysemy(word)
    if p:
        out["polysemy"].append(p)
    # 固定搭配 / 俚语（按上下文检测）
    if context:
        out["collocations"] = detect_collocation(context)
        out["slang"] = detect_slang(context)
    return out


def is_important_phenomenon(word: str, context: str = "") -> bool:
    """判定词是否因语言现象而"重要"（用于筛选豁免）。"""
    phen = detect_phenomena(word, context)
    return any(bool(v) for v in phen.values())
